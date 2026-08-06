#!/usr/bin/env bash
# 8.1 — public 8-BALL foundation: Ollama install and local API verification.
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_INSTALL_LANE="ubuntu/cpu"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/ubuntu-cpu.json"

PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
LOG_FILE="${PHILOSOPHER_ROOT}/8ball-trial.log"
OLLAMA_API="${OLLAMA_API:-http://127.0.0.1:11434}"

log() {
  printf '[8.1] %s\n' "$*"
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "8.1 requires root. Re-run with sudo." >&2
    exit 1
  fi
}

require_debian_family() {
  if [[ ! -f /etc/os-release ]]; then
    echo "8.1 supports Ubuntu/Debian hosts with /etc/os-release." >&2
    exit 1
  fi
  # shellcheck source=/dev/null
  source /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ;;
    *)
      echo "8.1 supports Ubuntu/Debian. Detected ID=${ID:-unknown}." >&2
      exit 1
      ;;
  esac
}

install_packages() {
  log "Installing minimal prerequisites"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y --no-install-recommends ca-certificates curl python3 zstd
}

ensure_philosopher_root() {
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  touch "${LOG_FILE}"
  chmod 0644 "${LOG_FILE}"
}

install_ollama_if_missing() {
  if command -v ollama >/dev/null 2>&1; then
    log "Ollama already installed; reusing existing binary"
    return 0
  fi
  log "Installing Ollama"
  if ! curl -fsSL https://ollama.com/install.sh | sh; then
    echo "Ollama installation failed." >&2
    exit 1
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama install script finished but ollama was not found in PATH." >&2
    exit 1
  fi
}

start_ollama() {
  if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    log "Ollama API already responding on ${OLLAMA_API}"
    return 0
  fi

  if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
    systemctl enable ollama >/dev/null 2>&1 || true
    if systemctl restart ollama; then
      return 0
    fi
    log "systemctl restart ollama failed; trying ollama serve"
  else
    log "systemd unavailable; starting ollama serve in background"
  fi

  if pgrep -x ollama >/dev/null 2>&1; then
    return 0
  fi

  nohup ollama serve >>"${LOG_FILE}" 2>&1 &
  sleep 2
}

wait_for_ollama() {
  for _ in $(seq 1 30); do
    if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
      log "Ollama API is responding on ${OLLAMA_API}"
      return 0
    fi
    sleep 2
  done
  echo "Ollama did not become ready at ${OLLAMA_API}" >&2
  exit 1
}

main() {
  require_root
  require_debian_family
  ensure_philosopher_root
  install_packages
  install_ollama_if_missing
  start_ollama
  wait_for_ollama
  log "Foundation step complete"
}

main "$@"
