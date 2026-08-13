#!/usr/bin/env bash
# Enforce Ollama localhost-only binding for 8.1.sh (INST-50B).
set -euo pipefail

OLLAMA_LOCAL_HOST="${OLLAMA_LOCAL_HOST:-127.0.0.1}"
OLLAMA_LOCAL_PORT="${OLLAMA_LOCAL_PORT:-11434}"
OLLAMA_API="${OLLAMA_API:-http://${OLLAMA_LOCAL_HOST}:${OLLAMA_LOCAL_PORT}}"
OLLAMA_LOCALHOST_DROPIN_NAME="8ball-localhost.conf"

ollama_dropin_dir() {
  printf '%s' "${OLLAMA_DROPIN_DIR:-/etc/systemd/system/ollama.service.d}"
}

ollama_dropin_path() {
  printf '%s/%s' "$(ollama_dropin_dir)" "${OLLAMA_LOCALHOST_DROPIN_NAME}"
}

ollama_dropin_content() {
  cat <<EOF
[Service]
Environment="OLLAMA_HOST=${OLLAMA_LOCAL_HOST}:${OLLAMA_LOCAL_PORT}"
Environment="OLLAMA_ORIGINS="
EOF
}

ollama_is_public_host_value() {
  local value="${1:-}"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  [[ -z "${value}" ]] && return 1
  if [[ "${value}" == :* ]]; then
    return 0
  fi
  if [[ "${value}" == *"0.0.0.0"* ]]; then
    return 0
  fi
  if [[ "${value}" == *"[::]"* ]]; then
    return 0
  fi
  return 1
}

ollama_scan_file_for_public_bind() {
  local file="$1"
  [[ -f "${file}" ]] || return 1
  local line key value
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "${line}" ]] && continue
    if [[ "${line}" =~ ^Environment(File)?= ]]; then
      if [[ "${line}" =~ ^EnvironmentFile= ]]; then
        local env_ref="${line#EnvironmentFile=}"
        env_ref="${env_ref#-}"
        env_ref="${env_ref//\"/}"
        if [[ "${env_ref}" != /* ]]; then
          env_ref="/etc/ollama/${env_ref}"
        fi
        ollama_scan_file_for_public_bind "${env_ref}" && return 0
        continue
      fi
      if [[ "${line}" =~ OLLAMA_HOST= ]]; then
        value="${line#*OLLAMA_HOST=}"
        value="${value%% *}"
        value="${value%;*}"
        if ollama_is_public_host_value "${value}"; then
          return 0
        fi
      fi
    fi
    if [[ "${line}" =~ ^OLLAMA_HOST= ]]; then
      value="${line#OLLAMA_HOST=}"
      value="${value%%#*}"
      value="${value//\"/}"
      if ollama_is_public_host_value "${value}"; then
        return 0
      fi
    fi
  done <"${file}"
  return 1
}

ollama_existing_bind_is_public() {
  local env_file dropin unit
  for env_file in /etc/default/ollama /etc/sysconfig/ollama; do
    if ollama_scan_file_for_public_bind "${env_file}"; then
      return 0
    fi
  done
  dropin="$(ollama_dropin_dir)"
  if [[ -d "${dropin}" ]]; then
    local conf
    for conf in "${dropin}"/*.conf; do
      [[ -f "${conf}" ]] || continue
      [[ "${conf}" == "$(ollama_dropin_path)" ]] && continue
      if ollama_scan_file_for_public_bind "${conf}"; then
        return 0
      fi
    done
  fi
  for unit in ${OLLAMA_UNIT_PATHS:-/etc/systemd/system/ollama.service /usr/lib/systemd/system/ollama.service}; do
    if ollama_scan_file_for_public_bind "${unit}"; then
      return 0
    fi
  done
  return 1
}

ollama_configure_localhost() {
  local dropin tmp
  dropin="$(ollama_dropin_path)"
  tmp="$(mktemp)"
  ollama_dropin_content >"${tmp}"
  install -d -m 0755 "$(ollama_dropin_dir)"
  if [[ -f "${dropin}" ]] && cmp -s "${tmp}" "${dropin}"; then
    rm -f "${tmp}"
    return 1
  fi
  mv "${tmp}" "${dropin}"
  chmod 0644 "${dropin}"
  return 0
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

ollama_service_active() {
  if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
    systemctl is-active --quiet ollama 2>/dev/null
    return $?
  fi
  pgrep -x ollama >/dev/null 2>&1
}

ollama_listener_lines() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null || ss -ltn 2>/dev/null
    return 0
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null
    return 0
  fi
  return 1
}

ollama_listener_has_public_bind() {
  local port="${OLLAMA_LOCAL_PORT}"
  local lines="$1"
  echo "${lines}" | grep -qE "(^|[[:space:]])0\.0\.0\.0:${port}([[:space:]]|$)|\[::\]:${port}([[:space:]]|$)|(^|[[:space:]])\\*:${port}([[:space:]]|$)"
}

ollama_listener_has_loopback_bind() {
  local port="${OLLAMA_LOCAL_PORT}"
  local lines="$1"
  echo "${lines}" | grep -qE "127\.0\.0\.1:${port}([[:space:]]|$)|\[::1\]:${port}([[:space:]]|$)"
}

ollama_verify_exclusive_listener() {
  local lines
  if ! lines="$(ollama_listener_lines)"; then
    echo "ss or netstat is required to verify Ollama localhost-only binding." >&2
    return 1
  fi
  if ollama_listener_has_public_bind "${lines}"; then
    echo "Ollama is listening on a public or wildcard address (port ${OLLAMA_LOCAL_PORT})." >&2
    return 1
  fi
  if ! ollama_listener_has_loopback_bind "${lines}"; then
    echo "Ollama is not listening on localhost (127.0.0.1:${OLLAMA_LOCAL_PORT})." >&2
    return 1
  fi
  return 0
}

ollama_verify_api() {
  if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    return 0
  fi
  echo "Ollama API is not responding at ${OLLAMA_API}." >&2
  return 1
}

ollama_ensure_localhost_config() {
  local changed=0
  if ollama_existing_bind_is_public; then
    printf '[8.1] Correcting public Ollama bind configuration to localhost-only\n'
  fi
  if ollama_configure_localhost; then
    changed=1
    printf '[8.1] Applied Ollama localhost systemd drop-in\n'
  else
    printf '[8.1] Ollama localhost configuration already correct\n'
  fi
  if [[ "${changed}" -eq 1 ]] || ollama_existing_bind_is_public; then
    if ! ollama_reload_service; then
      echo "Could not reload Ollama after applying localhost-only configuration." >&2
      exit 1
    fi
    printf '[8.1] Ollama service restarted after localhost configuration\n'
  fi
  printf '%s' "${changed}"
}

ollama_verify_foundation() {
  if ollama_service_active; then
    printf '[8.1] Ollama service active\n'
  else
    echo "Ollama service is not active." >&2
    return 1
  fi
  if ! ollama_verify_exclusive_listener; then
    return 1
  fi
  printf '[8.1] Ollama listener verified: exclusive localhost bind on %s:%s\n' \
    "${OLLAMA_LOCAL_HOST}" "${OLLAMA_LOCAL_PORT}"
  if ! ollama_verify_api; then
    return 1
  fi
  printf '[8.1] Ollama API verified at %s\n' "${OLLAMA_API}"
  return 0
}

# Backward-compatible entry used by earlier PR #50 integration.
ollama_ensure_localhost() {
  ollama_ensure_localhost_config >/dev/null
}
