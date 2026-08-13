#!/usr/bin/env bash
# Enforce Ollama localhost-only binding for 8.1.sh
set -euo pipefail

OLLAMA_LOCAL_HOST="${OLLAMA_LOCAL_HOST:-127.0.0.1}"
OLLAMA_LOCAL_PORT="${OLLAMA_LOCAL_PORT:-11434}"
OLLAMA_API="${OLLAMA_API:-http://${OLLAMA_LOCAL_HOST}:${OLLAMA_LOCAL_PORT}}"

ollama_dropin_dir() {
  printf '%s' "/etc/systemd/system/ollama.service.d"
}

ollama_configure_localhost() {
  local dropin dir
  dropin="$(ollama_dropin_dir)"
  dir="${dropin}"
  install -d -m 0755 "${dir}"
  cat >"${dir}/8ball-localhost.conf" <<EOF
[Service]
Environment="OLLAMA_HOST=${OLLAMA_LOCAL_HOST}:${OLLAMA_LOCAL_PORT}"
Environment="OLLAMA_ORIGINS="
EOF
  chmod 0644 "${dir}/8ball-localhost.conf"
}

ollama_existing_bind_is_public() {
  local env_file dropin
  for env_file in /etc/default/ollama /etc/sysconfig/ollama; do
    if [[ -f "${env_file}" ]] && grep -qE 'OLLAMA_HOST=.*(0\.0\.0\.0|\[::\])' "${env_file}"; then
      return 0
    fi
  done
  dropin="$(ollama_dropin_dir)"
  if [[ -d "${dropin}" ]]; then
    if grep -rE 'OLLAMA_HOST=.*(0\.0\.0\.0|\[::\])' "${dropin}" >/dev/null 2>&1; then
      return 0
    fi
  fi
  if [[ -f /etc/systemd/system/ollama.service ]] && \
     grep -qE 'OLLAMA_HOST=.*(0\.0\.0\.0|\[::\])' /etc/systemd/system/ollama.service; then
    return 0
  fi
  return 1
}

ollama_reload_service() {
  if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
    systemctl daemon-reload
    systemctl enable ollama >/dev/null 2>&1 || true
    systemctl restart ollama
    return 0
  fi
  return 1
}

ollama_verify_listener() {
  local addr port pattern
  addr="${OLLAMA_LOCAL_HOST}"
  port="${OLLAMA_LOCAL_PORT}"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn 2>/dev/null | grep -qE "LISTEN.*${addr}:${port}\b"; then
      return 0
    fi
    if [[ "${addr}" == "127.0.0.1" ]] && ss -ltn 2>/dev/null | grep -qE "LISTEN.*127\.0\.0\.1:${port}\b"; then
      return 0
    fi
    if ss -ltn 2>/dev/null | grep -qE "LISTEN.*0\.0\.0\.0:${port}\b|\[::\]:${port}\b"; then
      echo "Ollama is listening on a non-loopback address (port ${port})." >&2
      return 1
    fi
    return 1
  fi
  if command -v netstat >/dev/null 2>&1; then
    if netstat -ltn 2>/dev/null | grep -qE "${addr}:${port}\b"; then
      return 0
    fi
  fi
  # Fall back to API probe when socket tools are unavailable.
  if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

ollama_ensure_localhost() {
  local binary=""
  if command -v ollama >/dev/null 2>&1; then
    binary="$(command -v ollama)"
    printf '[8.1] Ollama binary discovered: %s\n' "${binary}"
  fi

  if ollama_existing_bind_is_public; then
    printf '[8.1] Correcting public Ollama bind to localhost-only\n'
    ollama_configure_localhost
    if ! ollama_reload_service; then
      echo "Could not safely correct a public Ollama bind configuration." >&2
      exit 1
    fi
  else
    ollama_configure_localhost
    ollama_reload_service || true
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ollama 2>/dev/null; then
    printf '[8.1] Ollama service active\n'
  fi

  if ! ollama_verify_listener; then
    echo "Ollama bind address could not be verified on ${OLLAMA_LOCAL_HOST}:${OLLAMA_LOCAL_PORT}." >&2
    exit 1
  fi
  printf '[8.1] Ollama bind address verified: %s:%s\n' "${OLLAMA_LOCAL_HOST}" "${OLLAMA_LOCAL_PORT}"
}
