#!/usr/bin/env bash
# 8.1 — public 8-BALL foundation: Ollama install and local API verification.
set -euo pipefail

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
  apt-get install -y --no-install-recommends ca-certificates curl python3
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
  curl -fsSL https://ollama.com/install.sh | sh
}

start_ollama() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable ollama >/dev/null 2>&1 || true
    systemctl restart ollama
  else
    log "systemd unavailable; assuming Ollama is already running"
  fi
}

wait_for_ollama() {
  local attempt
  for attempt in $(seq 1 30); do
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
