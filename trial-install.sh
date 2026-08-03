#!/usr/bin/env bash
# 8-BALL public trial installer entrypoint.
set -euo pipefail

VERSION="8-BALL trial-install 1.0.0"
DEFAULT_RAW_BASE="https://raw.githubusercontent.com/terminal-glass/8-ball/main"
LOG_FILE="/opt/philosopher/trial-log.txt"

MODEL=""
NO_MOTD=0
RAW_BASE="$DEFAULT_RAW_BASE"

usage() {
  cat <<'EOF'
8-BALL public trial installer

Usage:
  sudo ./trial-install.sh [options]

Options:
  --model <tag>     Request a specific Ollama model tag (example: qwen3:4b)
  --no-motd         Skip 8.3 MOTD and remember helper installation
  --raw-base <url>  HTTPS raw base for public script downloads
  -h, --help        Show this help text

Example:
  sudo ./trial-install.sh
  sudo ./trial-install.sh --model qwen3:4b
  sudo ./trial-install.sh --no-motd
EOF
}

log() {
  local message="$1"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message"
  if [[ -f "$LOG_FILE" ]]; then
    printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message" >>"$LOG_FILE"
  fi
}

die() {
  echo "ERROR: $*" >&2
  if [[ -f "$LOG_FILE" ]]; then
    echo "See log: $LOG_FILE" >&2
  fi
  exit 1
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root: sudo ./trial-install.sh"
  fi
}

validate_raw_base() {
  case "$RAW_BASE" in
    https://*) ;;
    *)
      die "--raw-base must use HTTPS"
      ;;
  esac
}

script_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

stage_script() {
  local name="$1"
  local source_dir="$2"
  local dest="$3"

  if [[ -f "${source_dir}/${name}" ]]; then
    install -m 0755 "${source_dir}/${name}" "$dest"
    return 0
  fi

  local url="${RAW_BASE%/}/${name}"
  if ! curl -fsSL "$url" -o "$dest"; then
    die "Failed to download ${name} from ${url}"
  fi
  chmod 0755 "$dest"
  if ! bash -n "$dest"; then
    rm -f "$dest"
    die "Downloaded ${name} failed bash -n syntax check"
  fi
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model)
        [[ $# -ge 2 ]] || die "--model requires a value"
        MODEL="$2"
        shift 2
        ;;
      --no-motd)
        NO_MOTD=1
        shift
        ;;
      --raw-base)
        [[ $# -ge 2 ]] || die "--raw-base requires a value"
        RAW_BASE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done

  require_root
  validate_raw_base

  mkdir -p /opt/philosopher
  touch "$LOG_FILE"
  chmod 0644 "$LOG_FILE"

  echo "============================================================"
  echo "  terminal.glass / 8-BALL public trial installer"
  echo "  ${VERSION}"
  echo "============================================================"

  log "Starting ${VERSION}"

  local bundled_dir
  bundled_dir="$(script_dir)"
  local work_dir
  work_dir="$(mktemp -d /tmp/8ball-install.XXXXXX)"
  trap 'rm -rf "$work_dir"' EXIT

  echo
  echo "[1/4] Loading the public 8-BALL components"
  stage_script "8.1.sh" "$bundled_dir" "${work_dir}/8.1.sh"
  stage_script "8.2.sh" "$bundled_dir" "${work_dir}/8.2.sh"
  if [[ "$NO_MOTD" -eq 0 ]]; then
    stage_script "8.3.sh" "$bundled_dir" "${work_dir}/8.3.sh"
  fi

  echo
  echo "[2/4] Preparing Ubuntu/Debian and installing Ollama"
  bash "${work_dir}/8.1.sh"

  echo
  echo "[3/4] Selecting and testing the local model"
  if [[ -n "$MODEL" ]]; then
    bash "${work_dir}/8.2.sh" --model "$MODEL"
  else
    bash "${work_dir}/8.2.sh"
  fi

  if [[ "$NO_MOTD" -eq 0 ]]; then
    echo
    echo "[4/4] Installing the terminal.glass login experience"
    bash "${work_dir}/8.3.sh"
  else
    echo
    echo "[4/4] Skipped MOTD installation (--no-motd)"
  fi

  echo
  echo "8-BALL trial install complete."
  echo "Result file: /opt/philosopher/8ball-result.txt"
  echo "Log file:    ${LOG_FILE}"
  if [[ -f /opt/philosopher/8ball-result.txt ]]; then
    echo
    cat /opt/philosopher/8ball-result.txt
  fi
  log "Completed ${VERSION}"
}

main "$@"
