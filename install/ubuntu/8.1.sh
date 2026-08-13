#!/usr/bin/env bash
# 8.1 — public 8-BALL foundation: Ollama install and local API verification.
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_SCRIPT_VERSION="0.8.0"
EIGHTBALL_INSTALL_PROFILE="ubuntu"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_DIR="${SCRIPT_DIR}/../shared"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
LOG_FILE="${PHILOSOPHER_ROOT}/8ball-trial.log"
OLLAMA_API="${OLLAMA_API:-http://127.0.0.1:11434}"

# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-version.sh"
# shellcheck source=/dev/null
source "${SHARED_DIR}/ollama-localhost.sh"

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

ensure_optional_swap() {
  if swapon --show 2>/dev/null | grep -q .; then
    log "Swap already present; leaving unchanged"
    return 0
  fi
  local ram_mb swapfile="/swapfile"
  ram_mb="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
  if [[ "${ram_mb}" -ge 8192 ]]; then
    log "RAM >= 8 GB; skipping optional swap"
    return 0
  fi
  if [[ -f "${swapfile}" ]]; then
    log "Swap file exists; enabling if inactive"
    chmod 600 "${swapfile}"
    mkswap "${swapfile}" >/dev/null 2>&1 || true
    swapon "${swapfile}" 2>/dev/null || true
    return 0
  fi
  log "Creating conservative 2G swap file"
  if fallocate -l 2G "${swapfile}" 2>/dev/null || dd if=/dev/zero of="${swapfile}" bs=1M count=2048 status=none; then
    chmod 600 "${swapfile}"
    mkswap "${swapfile}" >/dev/null
    swapon "${swapfile}"
    if ! grep -q "^${swapfile} " /etc/fstab 2>/dev/null; then
      echo "${swapfile} none swap sw 0 0" >>/etc/fstab
    fi
  else
    log "Swap creation skipped (non-fatal)"
  fi
}

install_ollama_if_missing() {
  if command -v ollama >/dev/null 2>&1; then
    log "Ollama binary discovered: $(command -v ollama)"
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
  log "Ollama binary discovered: $(command -v ollama)"
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

  OLLAMA_HOST="${OLLAMA_LOCAL_HOST:-127.0.0.1}:${OLLAMA_LOCAL_PORT:-11434}" \
    nohup ollama serve >>"${LOG_FILE}" 2>&1 &
  sleep 2
}

wait_for_ollama() {
  for _ in $(seq 1 30); do
    if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
      log "Ollama API responding"
      return 0
    fi
    sleep 2
  done
  echo "Ollama did not become ready at ${OLLAMA_API}" >&2
  exit 1
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<EOF
Usage: 8.1.sh [options]

Suite: ${EIGHTBALL_SCRIPT_FAMILY:-8-BALL} ${EIGHTBALL_SUITE_VERSION}
Lane: ${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE}}

Options:
  -h, --help    Show this help without mutating the host
EOF
    exit 0
  fi
  require_root
  eightball_verify_script_version "${BASH_SOURCE[0]}" "8.1.sh"
  require_debian_family
  ensure_philosopher_root
  install_packages
  ensure_optional_swap
  install_ollama_if_missing
  ollama_ensure_localhost
  start_ollama
  wait_for_ollama
  log "Foundation step complete"
}

main "$@"
