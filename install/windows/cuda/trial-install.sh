#!/usr/bin/env bash
# trial-install.sh — public 8-BALL free/trial installer entrypoint.
# Install profile: windows
set -euo pipefail

EIGHTBALL_INSTALL_LANE="windows/cuda"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/windows-cuda.json"

EIGHTBALL_INSTALL_PROFILE="windows/cuda"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
LOG_FILE="${PHILOSOPHER_ROOT}/8ball-trial.log"
RAW_BASE="${EIGHTBALL_RAW_BASE:-https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/windows/cuda}"
REQUESTED_MODEL=""
SKIP_MOTD=0
MANIFEST="${EIGHTBALL_MANIFEST:-}"

usage() {
  cat <<'EOF'
Usage: trial-install.sh [options]

Public free/trial 8-BALL installer for Ubuntu/Debian hosts.

Options:
  --model TAG         Request a specific Ollama tag (passed to 8.2.sh)
  --no-motd           Run 8.1 and 8.2 only
  --manifest PATH     Override install-manifest.json path
  --raw-base URL      Download helper scripts when local copies are missing
  -h, --help          Show this help

Catalog data is read from data/generated/pages/install-manifest.json in this repo.
Paid activation, Passport, Stripe, S3 bundles, and private customer logic are out of scope.
EOF
}

log() {
  printf '[trial-install] %s\n' "$*"
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "trial-install.sh requires root. Re-run with sudo." >&2
    exit 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model)
        REQUESTED_MODEL="$2"
        shift 2
        ;;
      --no-motd)
        SKIP_MOTD=1
        shift
        ;;
      --manifest)
        MANIFEST="$2"
        shift 2
        ;;
      --raw-base)
        RAW_BASE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

validate_raw_base() {
  case "${RAW_BASE}" in
    https://*) ;;
    *)
      echo "--raw-base must use HTTPS." >&2
      exit 1
      ;;
  esac
}

resolve_script() {
  local name="$1"
  local local_path="${SCRIPT_DIR}/${name}"
  if [[ -f "${local_path}" ]]; then
    printf '%s' "${local_path}"
    return 0
  fi
  validate_raw_base
  local tmp
  tmp="$(mktemp)"
  curl -fsSL "${RAW_BASE}/${name}" -o "${tmp}"
  bash -n "${tmp}"
  install -m 0755 "${tmp}" "${local_path}"
  rm -f "${tmp}"
  printf '%s' "${local_path}"
}

run_step() {
  local label="$1"
  shift
  log "${label}"
  if ! "$@" >>"${LOG_FILE}" 2>&1; then
    echo "Step failed: ${label}" >&2
    tail -n 30 "${LOG_FILE}" >&2 || true
    exit 1
  fi
}

main() {
  parse_args "$@"
  require_root
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  touch "${LOG_FILE}"
  chmod 0644 "${LOG_FILE}"

  local script_81 script_82 script_83
  script_81="$(resolve_script "8.1.sh")"
  script_82="$(resolve_script "8.2.sh")"
  script_83="$(resolve_script "8.3.sh")"

  local -a manifest_args=()
  if [[ -n "${MANIFEST}" ]]; then
    manifest_args=(--manifest "${MANIFEST}")
  fi
  local -a model_args=()
  if [[ -n "${REQUESTED_MODEL}" ]]; then
    model_args=(--model "${REQUESTED_MODEL}")
  fi

  log "[1/4] Loading the public 8-BALL components (profile=${EIGHTBALL_INSTALL_PROFILE})"
  log "[2/4] Preparing Ubuntu/Debian and installing Ollama"
  run_step "running 8.1.sh" "${script_81}"

  log "[3/4] Selecting and testing the local model"
  run_step "running 8.2.sh" "${script_82}" "${manifest_args[@]}" "${model_args[@]}"

  if [[ "${SKIP_MOTD}" -eq 0 ]]; then
    log "[4/4] Installing the terminal.glass login experience"
    run_step "running 8.3.sh" "${script_83}"
  else
    log "[4/4] Skipping MOTD (--no-motd)"
  fi

  log "Trial install complete. Log: ${LOG_FILE}"
  log "Result: ${PHILOSOPHER_ROOT}/8ball-result.txt"
}

main "$@"
