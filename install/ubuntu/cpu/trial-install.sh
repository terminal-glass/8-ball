#!/usr/bin/env bash
# trial-install.sh — public 8-BALL free/trial installer entrypoint.
# Install lane: ubuntu/cpu
set -euo pipefail

EIGHTBALL_INSTALL_LANE="ubuntu/cpu"
EIGHTBALL_INSTALL_PROFILE="ubuntu/cpu"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/ubuntu-cpu.json"
UBUNTU_LOG_PREFIX="trial-install"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/ubuntu-common.sh
source "${SCRIPT_DIR}/../lib/ubuntu-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="trial-install.sh"
INSTALLER_SMOKE_PLATFORM="linux"
INSTALLER_SMOKE_CHECKS="- Verify Debian-family host identity
- Would orchestrate foundation (8.1), model ladder (8.2), and MOTD (8.3) during a real install (requires root)"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

REQUESTED_MODEL=""
MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-}"
SKIP_MOTD=0
NONINTERACTIVE_CONFIRM=0

usage() {
  cat <<'EOF'
Usage: trial-install.sh [options]

Public free/trial 8-BALL installer for Ubuntu/Debian hosts (ubuntu/cpu lane).

Options:
  --model TAG                         Request a specific Ollama tag (validated against profiles)
  --model-slug SLUG                   Select from committed profile lane data (required without --model)
  --no-motd                           Run 8.1 and 8.2 only
  --yes                               Non-interactive confirmation for planned system changes
  --accept-ollama-install-risk        Development-only opt-in for unverified ollama.com/install.sh
  --i-understand-disable-integrity-checks --dev-raw-base URL
                                      DEVELOPMENT ONLY: fetch lane scripts from a custom base URL
  -h, --help                          Show this help

Release-pinned remote downloads use terminal-glass/8-ball at the commit recorded in
install/ubuntu/lib/ubuntu-common.sh. Profile sizing uses profiles/<slug>/ubuntu/cpu/.
EOF
}

log() {
  ubuntu_log "$*"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model)
        REQUESTED_MODEL="$2"
        ubuntu_validate_model_tag "${REQUESTED_MODEL}"
        shift 2
        ;;
      --model-slug)
        REQUESTED_MODEL=""
        MODEL_SLUG="$2"
        shift 2
        ;;
      --no-motd)
        SKIP_MOTD=1
        shift
        ;;
      --yes)
        NONINTERACTIVE_CONFIRM=1
        shift
        ;;
      --accept-ollama-install-risk)
        export EIGHTBALL_ACCEPT_OLLAMA_INSTALL_RISK=1
        shift
        ;;
      --i-understand-disable-integrity-checks)
        export EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS=1
        shift
        ;;
      --dev-raw-base)
        export EIGHTBALL_DEV_RAW_BASE="$2"
        shift 2
        ;;
      --raw-base)
        echo "--raw-base is not supported on the public installer path." >&2
        echo "Use a local checkout or the development flags documented in --help." >&2
        exit 1
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

run_step() {
  local label="$1"
  shift
  log "${label}"
  if ! "$@" >>"${TRIAL_LOG}" 2>&1; then
    echo "Step failed: ${label}" >&2
    tail -n 30 "${TRIAL_LOG}" >&2 || true
    exit 1
  fi
}

main() {
  installer_smoke_prologue "$@"
  parse_args "$@"
  if [[ "${NONINTERACTIVE_CONFIRM}" == "1" ]]; then
    export EIGHTBALL_NONINTERACTIVE_CONFIRM=1
  fi
  ubuntu_require_root
  ubuntu_ensure_state_root
  ubuntu_resolve_profile_dir
  ubuntu_show_planned_changes
  ubuntu_require_noninteractive_confirm

  local script_81 script_82 script_83
  script_81="$(ubuntu_resolve_lane_script "8.1.sh")"
  script_82="$(ubuntu_resolve_lane_script "8.2.sh")"
  script_83="$(ubuntu_resolve_lane_script "8.3.sh")"

  local -a model_args=()
  if [[ -n "${REQUESTED_MODEL}" ]]; then
    model_args=(--model "${REQUESTED_MODEL}")
  elif [[ -n "${MODEL_SLUG}" ]]; then
    model_args=(--model-slug "${MODEL_SLUG}")
  fi

  log "[1/4] Loading the public 8-BALL components (lane=${EIGHTBALL_INSTALL_LANE}, suite=${SUITE_VERSION})"
  log "[2/4] Preparing Ubuntu/Debian and installing Ollama"
  run_step "running 8.1.sh" "${script_81}"

  log "[3/4] Selecting and testing the local model from profile data"
  run_step "running 8.2.sh" "${script_82}" "${model_args[@]}"

  if [[ "${SKIP_MOTD}" -eq 0 ]]; then
    log "[4/4] Installing the terminal.glass login experience"
    run_step "running 8.3.sh" "${script_83}"
  else
    log "[4/4] Skipping MOTD (--no-motd)"
  fi

  log "Trial install complete. Log: ${TRIAL_LOG}"
  log "Result: ${RESULT_FILE}"
}

main "$@"
