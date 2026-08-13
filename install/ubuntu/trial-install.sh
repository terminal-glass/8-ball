#!/usr/bin/env bash
# trial-install.sh — public 8-BALL free/trial installer entrypoint.
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_SCRIPT_VERSION="0.8.0"
EIGHTBALL_INSTALL_PROFILE="ubuntu"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_DIR="${SCRIPT_DIR}/../shared"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
LOG_FILE="${PHILOSOPHER_ROOT}/8ball-trial.log"
TRIAL_MARKER="${PHILOSOPHER_ROOT}/trial-installed"
RAW_BASE="${EIGHTBALL_RAW_BASE:-}"
REQUESTED_MODEL=""
MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-}"
SKIP_MOTD=0
MANIFEST="${EIGHTBALL_MANIFEST:-}"
INSTALL_SUCCEEDED=0

# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-version.sh"
# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-release.sh"

usage() {
  cat <<EOF
Usage: trial-install.sh [options]

Public free/trial 8-BALL installer for Ubuntu/Debian hosts.
Suite: ${EIGHTBALL_SCRIPT_FAMILY} ${EIGHTBALL_SUITE_VERSION}

Options:
  --model TAG         Request a specific Ollama tag (passed to 8.2.sh)
  --model-slug SLUG   Select via profiles/<slug>/ lane mapping
  --no-motd           Run 8.1 and 8.2 only
  --manifest PATH     Override install-manifest.json path
  --raw-base URL      Download helper scripts when local copies are missing
  -h, --help          Show this help

Environment:
  EIGHTBALL_RELEASE   Tagged release (default: v0.8.0) or "main" for development
  EIGHTBALL_RAW_BASE  Explicit raw script base URL override
  EIGHTBALL_REPO_ROOT Full checkout override for local development bundles
EOF
}

log() {
  printf '[trial-install] %s\n' "$*"
}

require_root() {
  if [[ "${EIGHTBALL_TEST_SKIP_ROOT:-0}" == "1" ]]; then
    return 0
  fi
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
      --model-slug)
        MODEL_SLUG="$2"
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

clear_completion_marker() {
  rm -f "${TRIAL_MARKER}"
}

write_completion_marker() {
  cat >"${TRIAL_MARKER}" <<EOF
suite_version=${EIGHTBALL_SUITE_VERSION}
script_family=${EIGHTBALL_SCRIPT_FAMILY}
installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
install_profile=${EIGHTBALL_INSTALL_PROFILE}
install_lane=${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE}}
release_tag=${EIGHTBALL_RELEASE}
EOF
  chmod 0644 "${TRIAL_MARKER}"
}

on_exit() {
  local status=$?
  if [[ "${status}" -ne 0 && "${INSTALL_SUCCEEDED}" -eq 0 ]]; then
    clear_completion_marker
  fi
  return "${status}"
}

resolve_script() {
  local name="$1"
  local local_path="${SCRIPT_DIR}/${name}"
  local skip_release_checksum=0
  if [[ -n "${EIGHTBALL_REPO_ROOT:-}" ]] || eightball_release_is_development; then
    skip_release_checksum=1
  fi
  if [[ -f "${local_path}" ]]; then
    if [[ "${skip_release_checksum}" -eq 0 ]]; then
      if manifest_path="$(eightball_manifest_path_for_release "${SCRIPT_DIR}" 2>/dev/null || true)"; then
        eightball_verify_download_sha "${local_path}" "${name}" "${manifest_path}" || {
          echo "Local script failed release integrity check: ${name}" >&2
          exit 1
        }
      fi
    fi
    eightball_verify_script_version "${local_path}" "${name}"
    printf '%s' "${local_path}"
    return 0
  fi
  if [[ -z "${RAW_BASE}" ]]; then
    RAW_BASE="$(eightball_release_raw_base "${EIGHTBALL_INSTALL_PROFILE}")"
  fi
  validate_raw_base
  local tmp manifest_path=""
  tmp="$(mktemp)"
  curl -fsSL "${RAW_BASE}/${name}" -o "${tmp}"
  if manifest_path="$(eightball_manifest_path_for_release "${SCRIPT_DIR}" 2>/dev/null || true)"; then
    eightball_verify_download_sha "${tmp}" "${name}" "${manifest_path}" || {
      echo "Download integrity check failed for ${name}." >&2
      rm -f "${tmp}"
      exit 1
    }
  elif ! eightball_release_is_development; then
    echo "Release manifest unavailable; refusing unverified download of ${name}." >&2
    rm -f "${tmp}"
    exit 1
  fi
  bash -n "${tmp}"
  eightball_verify_script_version "${tmp}" "${name}"
  install -m 0755 "${tmp}" "${local_path}"
  rm -f "${tmp}"
  printf '%s' "${local_path}"
}

prepare_release_context() {
  if [[ -n "${EIGHTBALL_REPO_ROOT:-}" && -d "${EIGHTBALL_REPO_ROOT}/profiles" ]]; then
    log "Using explicit development bundle at ${EIGHTBALL_REPO_ROOT}"
    return 0
  fi
  if eightball_local_bundle_ready "${SCRIPT_DIR}"; then
    export EIGHTBALL_REPO_ROOT="$(eightball_locate_repo_root_from "${SCRIPT_DIR}")"
    log "Using local development bundle at ${EIGHTBALL_REPO_ROOT}"
    return 0
  fi
  if eightball_release_is_development; then
    log "Development release override (${EIGHTBALL_RELEASE:-main}); profile data must be supplied locally"
    if repo_root="$(eightball_locate_repo_root_from "${SCRIPT_DIR}" 2>/dev/null || true)"; then
      export EIGHTBALL_REPO_ROOT="${repo_root}"
    fi
    return 0
  fi
  log "Resolving verified release bundle ${EIGHTBALL_RELEASE}"
  eightball_bootstrap_release_runtime "${SCRIPT_DIR}" "${BASH_SOURCE[0]}" || {
    echo "Failed to bootstrap verified release runtime for ${EIGHTBALL_RELEASE}." >&2
    exit 1
  }
  if [[ -z "${MANIFEST}" && -n "${EIGHTBALL_MANIFEST:-}" ]]; then
    MANIFEST="${EIGHTBALL_MANIFEST}"
  fi
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
  trap on_exit EXIT
  eightball_verify_script_version "${BASH_SOURCE[0]}" "trial-install.sh"
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  touch "${LOG_FILE}"
  chmod 0644 "${LOG_FILE}"
  clear_completion_marker

  prepare_release_context

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
  if [[ -n "${MODEL_SLUG}" ]]; then
    export EIGHTBALL_MODEL_SLUG="${MODEL_SLUG}"
    model_args+=(--model-slug "${MODEL_SLUG}")
  fi

  log "[1/4] Loading the public 8-BALL components (profile=${EIGHTBALL_INSTALL_PROFILE}, release=${EIGHTBALL_RELEASE})"
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

  INSTALL_SUCCEEDED=1
  write_completion_marker
  log "Trial install complete. Log: ${LOG_FILE}"
  log "Result: ${PHILOSOPHER_ROOT}/8ball-result.txt"
  log "Marker: ${TRIAL_MARKER}"
}

main "$@"
