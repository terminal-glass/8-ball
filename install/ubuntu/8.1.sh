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
SWAPFILE="/swapfile"
SWAP_SIZE_GB=2

# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-version.sh"
# shellcheck source=/dev/null
source "${SHARED_DIR}/ollama-localhost.sh"

log() {
  printf '[8.1] %s\n' "$*"
  if [[ -n "${LOG_FILE:-}" ]]; then
    printf '[8.1] %s\n' "$*" >>"${LOG_FILE}" 2>/dev/null || true
  fi
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
    ubuntu|debian)
      log "OS validated: ${PRETTY_NAME:-${ID}}"
      ;;
    *)
      echo "8.1 supports Ubuntu/Debian. Detected ID=${ID:-unknown}." >&2
      exit 1
      ;;
  esac
}

install_packages() {
  local missing=()
  for pkg in ca-certificates curl python3 zstd; do
    if ! dpkg -s "${pkg}" >/dev/null 2>&1; then
      missing+=("${pkg}")
    fi
  done
  if [[ "${#missing[@]}" -eq 0 ]]; then
    log "HTTPS prerequisites already installed"
    return 0
  fi
  log "Installing minimal prerequisites: ${missing[*]}"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y --no-install-recommends "${missing[@]}"
  log "HTTPS prerequisites ready"
}

ensure_philosopher_root() {
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  touch "${LOG_FILE}"
  chmod 0644 "${LOG_FILE}"
}

swap_is_active() {
  swapon --show 2>/dev/null | grep -q .
}

swapfile_is_ours() {
  [[ -f "${SWAPFILE}" ]] || return 1
  grep -qE "^${SWAPFILE}[[:space:]]" /etc/fstab 2>/dev/null
}

ensure_optional_swap() {
  if swap_is_active; then
    log "Swap detected; leaving existing swap unchanged"
    return 0
  fi
  local ram_mb free_mb
  ram_mb="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
  if [[ "${ram_mb}" -ge 8192 ]]; then
    log "RAM >= 8 GB; skipping optional swap"
    return 0
  fi
  if [[ -f "${SWAPFILE}" ]]; then
    if swapfile_is_ours; then
      log "Existing 8-BALL swap file found; enabling if inactive"
      chmod 600 "${SWAPFILE}"
      mkswap "${SWAPFILE}" >/dev/null 2>&1 || true
      if swapon "${SWAPFILE}" 2>/dev/null; then
        log "Existing swap file enabled"
      else
        log "Existing swap file present but could not be enabled (non-fatal)"
      fi
    else
      log "Unrelated /swapfile present; not modifying it"
    fi
    return 0
  fi
  free_mb="$(df -Pm / | awk 'NR==2 {print $4}')"
  if [[ "${free_mb}" -lt $((SWAP_SIZE_GB * 1024 + 512)) ]]; then
    log "Insufficient disk for optional ${SWAP_SIZE_GB}G swap; skipping"
    return 0
  fi
  log "Creating conservative ${SWAP_SIZE_GB}G swap file"
  if fallocate -l "${SWAP_SIZE_GB}G" "${SWAPFILE}" 2>/dev/null || \
     dd if=/dev/zero of="${SWAPFILE}" bs=1M count=$((SWAP_SIZE_GB * 1024)) status=none; then
    chmod 600 "${SWAPFILE}"
    mkswap "${SWAPFILE}" >/dev/null
    swapon "${SWAPFILE}"
    if ! grep -qE "^${SWAPFILE}[[:space:]]" /etc/fstab 2>/dev/null; then
      echo "${SWAPFILE} none swap sw 0 0" >>/etc/fstab
    fi
    log "Optional swap created and enabled"
  else
    log "Swap creation skipped (non-fatal)"
  fi
}

install_ollama_if_missing() {
  if command -v ollama >/dev/null 2>&1; then
    log "Ollama binary found: $(command -v ollama)"
    log "Reusing existing Ollama installation"
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
  log "Ollama binary installed: $(command -v ollama)"
}

start_ollama() {
  if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
    systemctl enable ollama >/dev/null 2>&1 || true
    if systemctl restart ollama; then
      log "Ollama service restarted"
      return 0
    fi
    log "systemctl restart ollama failed; trying ollama serve"
  else
    log "systemd unavailable; starting ollama serve in background"
  fi

  if pgrep -x ollama >/dev/null 2>&1; then
    log "Ollama process already running"
    return 0
  fi

  OLLAMA_HOST="${OLLAMA_LOCAL_HOST:-127.0.0.1}:${OLLAMA_LOCAL_PORT:-11434}" \
    nohup ollama serve >>"${LOG_FILE}" 2>&1 &
  sleep 2
  log "Started ollama serve in background"
}

wait_for_ollama_api() {
  for _ in $(seq 1 30); do
    if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
      log "Ollama API responding"
      return 0
    fi
    sleep 2
  done
  echo "Ollama API did not become ready at ${OLLAMA_API}" >&2
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
  ollama_ensure_localhost_config >/dev/null
  start_ollama
  wait_for_ollama_api
  if ! ollama_verify_foundation; then
    echo "8.1 foundation verification failed; refusing to continue to 8.2." >&2
    exit 1
  fi
  log "8.1 completed"
}

main "$@"
