#!/usr/bin/env bash
# 8-BALL foundation: host prep, minimal packages, Ollama install/verify.
set -euo pipefail

VERSION="8.1 foundation 1.0.0"
LOG_FILE="/opt/philosopher/trial-log.txt"
PHILOSOPHER_ROOT="/opt/philosopher"

log() {
  local message="$1"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message" >>"$LOG_FILE"
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "8.1 must run as root"
}

detect_os() {
  if [[ ! -f /etc/os-release ]]; then
    die "Unsupported host: missing /etc/os-release"
  fi
  # shellcheck disable=SC1091
  source /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ;;
    *)
      die "Unsupported OS: ${PRETTY_NAME:-unknown}. Ubuntu/Debian required."
      ;;
  esac
}

ensure_apt_prereqs() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    jq
}

ensure_philosopher_root() {
  install -d -m 0755 "$PHILOSOPHER_ROOT"
  touch "$LOG_FILE"
  chmod 0644 "$LOG_FILE"
  log "Ensured ${PHILOSOPHER_ROOT} and ${LOG_FILE}"
}

maybe_add_swap() {
  local ram_mb swap_mb
  ram_mb="$(awk '/MemTotal:/ {print int($2/1024)}' /proc/meminfo)"
  swap_mb="$(awk '/SwapTotal:/ {print int($2/1024)}' /proc/meminfo)"

  if [[ "$ram_mb" -ge 8192 ]]; then
    log "Skipping swap creation (${ram_mb} MB RAM detected)"
    return 0
  fi
  if [[ "$swap_mb" -ge 1024 ]]; then
    log "Swap already present (${swap_mb} MB); not creating more"
    return 0
  fi
  if [[ -f /swapfile ]]; then
    log "Swap file already exists; not recreating"
    return 0
  fi

  log "Creating conservative 2G swap for low-RAM host (${ram_mb} MB RAM)"
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  if ! grep -q '^/swapfile ' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' >>/etc/fstab
  fi
}

install_ollama_if_missing() {
  if command -v ollama >/dev/null 2>&1; then
    log "Reusing existing Ollama install: $(command -v ollama)"
    return 0
  fi

  log "Installing Ollama from official installer"
  curl -fsSL https://ollama.com/install.sh | sh
}

start_ollama() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    systemctl enable ollama >/dev/null 2>&1 || true
    systemctl restart ollama
    systemctl is-active --quiet ollama || die "Ollama systemd service is not active"
  else
    pgrep -x ollama >/dev/null 2>&1 || (ollama serve >/var/log/ollama-8ball.log 2>&1 &)
    sleep 3
  fi
}

verify_ollama_api() {
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then
      log "Ollama API verified at http://127.0.0.1:11434/api/tags"
      return 0
    fi
    sleep 2
  done
  die "Ollama API did not respond on http://127.0.0.1:11434/api/tags"
}

main() {
  require_root
  detect_os
  ensure_philosopher_root
  log "Starting ${VERSION}"
  ensure_apt_prereqs
  maybe_add_swap
  install_ollama_if_missing
  start_ollama
  verify_ollama_api
  log "Completed ${VERSION}"
  echo "8.1 complete: Ollama is installed and responding locally."
}

main "$@"
