#!/usr/bin/env bash
# trial-install.sh — public 8-BALL free/trial installer entrypoint.
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_SCRIPT_VERSION="0.8.0"
EIGHTBALL_INSTALL_PROFILE="ubuntu"
EIGHTBALL_RELEASE="${EIGHTBALL_RELEASE:-v0.8.0}"
EIGHTBALL_RELEASE_REF="${EIGHTBALL_RELEASE_REF:-ff9197ad0c3417b74b4ab580a099dfa49bf311ab}"
export EIGHTBALL_RELEASE_REF
EIGHTBALL_RELEASE_REPO="${EIGHTBALL_RELEASE_REPO:-terminal-glass/8-ball}"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
EIGHTBALL_BOOTSTRAP_ROOT="${EIGHTBALL_BOOTSTRAP_ROOT:-${PHILOSOPHER_ROOT}/.8ball-bootstrap/ubuntu}"
LOG_FILE="${PHILOSOPHER_ROOT}/8ball-trial.log"
TRIAL_MARKER="${PHILOSOPHER_ROOT}/trial-installed"
RAW_BASE="${EIGHTBALL_RAW_BASE:-}"
REQUESTED_MODEL=""
MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-}"
SKIP_MOTD=0
MANIFEST="${EIGHTBALL_MANIFEST:-}"
INSTALL_SUCCEEDED=0
ENTRY_SCRIPT=""
EIGHTBALL_STREAMED_INSTALL=0

eightball_resolve_entry_context() {
  local source_path="${BASH_SOURCE[0]:-}"
  if [[ -n "${source_path}" && "${source_path}" != bash && -f "${source_path}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${source_path}")" && pwd)"
    ENTRY_SCRIPT="${source_path}"
    SHARED_DIR="${SCRIPT_DIR}/../shared"
    EIGHTBALL_STREAMED_INSTALL=0
    return 0
  fi
  EIGHTBALL_STREAMED_INSTALL=1
  SCRIPT_DIR="${EIGHTBALL_BOOTSTRAP_ROOT}/install/ubuntu"
  SHARED_DIR="${EIGHTBALL_BOOTSTRAP_ROOT}/install/shared"
  ENTRY_SCRIPT="${SCRIPT_DIR}/trial-install.sh"
  install -d -m 0755 "${SCRIPT_DIR}" "${SHARED_DIR}"
}

eightball_resolve_entry_context

detect_ubuntu_install_lane() {
  if [[ -n "${EIGHTBALL_INSTALL_LANE:-}" ]]; then
    printf '%s' "${EIGHTBALL_INSTALL_LANE}"
    return 0
  fi
  local gpu_vram
  if command -v nvidia-smi >/dev/null 2>&1; then
    gpu_vram="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || echo 0)"
    if [[ "${gpu_vram}" =~ ^[0-9]+$ ]] && [[ "${gpu_vram}" -ge 6000 ]]; then
      printf '%s' "ubuntu/cuda"
      return 0
    fi
  fi
  printf '%s' "ubuntu/cpu"
}

export EIGHTBALL_INSTALL_LANE="${EIGHTBALL_INSTALL_LANE:-$(detect_ubuntu_install_lane)}"

eightball_entrypoint_release_repo_base() {
  if [[ -n "${EIGHTBALL_RAW_BASE:-}" ]]; then
    local trimmed="${EIGHTBALL_RAW_BASE%/}"
    trimmed="${trimmed%/install/ubuntu}"
    trimmed="${trimmed%/install}"
    printf '%s' "${trimmed}"
    return 0
  fi
  if [[ -n "${EIGHTBALL_RELEASE_REF:-}" ]]; then
    printf 'https://raw.githubusercontent.com/%s/%s' \
      "${EIGHTBALL_RELEASE_REPO}" "${EIGHTBALL_RELEASE_REF}"
    return 0
  fi
  if [[ "${EIGHTBALL_RELEASE}" == "main" ]]; then
    printf 'https://raw.githubusercontent.com/%s/main' "${EIGHTBALL_RELEASE_REPO}"
    return 0
  fi
  echo "EIGHTBALL_RELEASE_REF is required for verified release bootstrap (logical ${EIGHTBALL_RELEASE} is not a Git ref)." >&2
  return 1
}

eightball_entrypoint_verify_artifact() {
  local manifest_path="$1"
  local rel_path="$2"
  local file_path="$3"
  python3 - "${manifest_path}" "${rel_path}" "${file_path}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path, rel_path, file_path = sys.argv[1:4]
manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
expected = manifest.get("artifacts", {}).get(rel_path)
if not expected:
    print(f"[release] No checksum recorded for artifact {rel_path}", file=sys.stderr)
    raise SystemExit(1)
path = Path(file_path)
if not path.is_file() or path.stat().st_size == 0:
    print(f"[release] Missing or empty artifact file: {file_path}", file=sys.stderr)
    raise SystemExit(1)
digest = hashlib.sha256(path.read_bytes()).hexdigest()
if digest != expected:
    print(
        f"[release] SHA-256 mismatch for {rel_path}\n"
        f"  expected: {expected}\n"
        f"  actual:   {digest}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
}

eightball_entrypoint_download_verified() {
  local rel_path="$1"
  local dest_path="$2"
  local manifest_path="$3"
  local url="${4:-$(eightball_entrypoint_release_repo_base)/${rel_path}}"
  local tmp parent
  parent="$(dirname "${dest_path}")"
  install -d -m 0755 "${parent}"
  tmp="$(mktemp "${parent}/.artifact.XXXXXX")"
  if ! curl -fsSL "${url}" -o "${tmp}"; then
    rm -f "${tmp}"
    echo "Failed to download release artifact: ${url}" >&2
    return 1
  fi
  if ! eightball_entrypoint_verify_artifact "${manifest_path}" "${rel_path}" "${tmp}"; then
    rm -f "${tmp}"
    echo "Refusing to install unverified artifact: ${rel_path}" >&2
    return 1
  fi
  install -m 0755 "${tmp}" "${dest_path}"
  rm -f "${tmp}"
}

eightball_entrypoint_fetch_dev_shared() {
  local base url tmp
  if [[ -n "${EIGHTBALL_RAW_BASE:-}" ]]; then
    base="${EIGHTBALL_RAW_BASE%/}"
  elif [[ "${EIGHTBALL_RELEASE}" == "main" ]]; then
    base="https://raw.githubusercontent.com/${EIGHTBALL_RELEASE_REPO}/main/install/shared"
  else
    echo "Development shared-helper fetch requires EIGHTBALL_RELEASE=main or EIGHTBALL_RAW_BASE." >&2
    return 1
  fi
  install -d -m 0755 "${SHARED_DIR}"
  for name in 8ball-version.sh 8ball-release.sh; do
    url="${base}/${name}"
    tmp="$(mktemp)"
    if ! curl -fsSL "${url}" -o "${tmp}"; then
      rm -f "${tmp}"
      echo "Failed to download development helper: ${url}" >&2
      return 1
    fi
    install -m 0755 "${tmp}" "${SHARED_DIR}/${name}"
    rm -f "${tmp}"
  done
}

eightball_entrypoint_fetch_verified_shared() {
  local manifest_cache rel_path dest_path url
  manifest_cache="$(mktemp)"
  url="$(eightball_entrypoint_release_repo_base)/install/releases/${EIGHTBALL_RELEASE}/manifest.json"
  if ! curl -fsSL "${url}" -o "${manifest_cache}"; then
    rm -f "${manifest_cache}"
    cat >&2 <<EOF
Failed to download release manifest:
  ${url}

Published immutable release source is not available from ${EIGHTBALL_RELEASE_REPO}.
Set EIGHTBALL_RELEASE_REF to the approved commit SHA for logical release ${EIGHTBALL_RELEASE}.
EOF
    return 1
  fi
  if ! python3 -m json.tool "${manifest_cache}" >/dev/null 2>&1; then
    rm -f "${manifest_cache}"
    echo "Downloaded release manifest is not valid JSON: ${url}" >&2
    return 1
  fi
  install -d -m 0755 "${SHARED_DIR}"
  for rel_path in install/shared/8ball-version.sh install/shared/8ball-release.sh; do
    dest_path="${SHARED_DIR}/$(basename "${rel_path}")"
    if ! eightball_entrypoint_download_verified "${rel_path}" "${dest_path}" "${manifest_cache}"; then
      rm -f "${manifest_cache}"
      return 1
    fi
  done
  rm -f "${manifest_cache}"
}

bootstrap_entrypoint_helpers() {
  local version_sh="${SHARED_DIR}/8ball-version.sh"
  local release_sh="${SHARED_DIR}/8ball-release.sh"
  if [[ -f "${version_sh}" && -f "${release_sh}" ]]; then
    return 0
  fi
  if [[ "${EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS:-0}" == "1" || "${EIGHTBALL_RELEASE}" == "main" || -n "${EIGHTBALL_RAW_BASE:-}" ]]; then
    eightball_entrypoint_fetch_dev_shared
    return $?
  fi
  eightball_entrypoint_fetch_verified_shared
}

eightball_entrypoint_ensure_smoke_contract() {
  local dest="${SHARED_DIR}/installer-smoke-contract.sh"
  local base url
  if [[ -f "${dest}" ]]; then
    return 0
  fi
  if ! base="$(eightball_entrypoint_release_repo_base)"; then
    return 1
  fi
  url="${base}/install/shared/installer-smoke-contract.sh"
  install -d -m 0755 "${SHARED_DIR}"
  if ! curl -fsSL "${url}" -o "${dest}"; then
    echo "Failed to download installer smoke contract: ${url}" >&2
    return 1
  fi
  chmod 0755 "${dest}"
}

bootstrap_entrypoint_helpers

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
  EIGHTBALL_RELEASE       Logical product version (default: v0.8.0)
  EIGHTBALL_RELEASE_REF   Approved immutable git ref for verified bootstrap
  EIGHTBALL_RAW_BASE      Explicit raw script base URL override
  EIGHTBALL_REPO_ROOT     Full checkout override for local development bundles
EOF
}

INSTALLER_SMOKE_SCRIPT_NAME="trial-install.sh"
INSTALLER_SMOKE_PLATFORM="linux"
INSTALLER_SMOKE_CHECKS="- Detect Ubuntu CPU or CUDA lane from host hardware
- Would orchestrate foundation (8.1), model ladder (8.2), and MOTD (8.3) during a real install (requires root)"
eightball_entrypoint_ensure_smoke_contract
# shellcheck source=/dev/null
source "${SHARED_DIR}/installer-smoke-contract.sh"

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
  eightball_bootstrap_release_runtime "${SCRIPT_DIR}" || {
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
  installer_smoke_prologue "$@"
  parse_args "$@"
  require_root
  trap on_exit EXIT
  if [[ -f "${ENTRY_SCRIPT}" ]]; then
    eightball_verify_script_version "${ENTRY_SCRIPT}" "trial-install.sh"
  fi
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  touch "${LOG_FILE}"
  chmod 0644 "${LOG_FILE}"
  clear_completion_marker

  prepare_release_context

  if [[ "${EIGHTBALL_BOOTSTRAP_STOP:-0}" == "1" ]]; then
    log "Bootstrap stop requested; release context prepared."
    INSTALL_SUCCEEDED=1
    exit 0
  fi

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
