#!/usr/bin/env bash
# 8.2 — macOS Happy Nerds model trial ladder with local inference verification.
set -euo pipefail

EIGHTBALL_INSTALL_LANE="mac/apple-silicon"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/mac-apple-silicon.json"
MAC_EXPECTED_ARCH="arm64"
MAC_TARGET_LANE="mac/apple-silicon"
MAC_ACCELERATION="metal"
MAC_LOG_PREFIX="8.2"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/macos-common.sh
source "${SCRIPT_DIR}/../lib/macos-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="8.2.sh"
INSTALLER_SMOKE_PLATFORM="mac"
INSTALLER_SMOKE_CHECKS="- Verify catalog or profile availability for model selection
- Would run the trial model ladder with local inference checks during a real install"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

REQUESTED_MODEL=""

usage() {
  cat <<'EOF'
Usage: 8.2.sh [--model OLLAMA_TAG]

Runs the Happy Nerds trial ladder on macOS using observed RAM and install-disk facts.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model)
        REQUESTED_MODEL="$2"
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

mac_resolve_acceleration() {
  local metal_status arch
  metal_status="$(python3 -c "import json;print(json.load(open('${OBSERVATION_FILE}')).get('metal_status','unknown'))")"
  arch="$(python3 -c "import json;print(json.load(open('${OBSERVATION_FILE}')).get('architecture','unknown'))")"
  if [[ "${arch}" == "arm64" && "${metal_status}" == "supported" ]]; then
    MAC_ACCELERATION="metal"
  else
    MAC_ACCELERATION="cpu"
  fi
}

main() {
  installer_smoke_prologue "$@"
  parse_args "$@"
  mac_refuse_root
  mac_require_darwin
  mac_resolve_eightball_root
  mac_validate_ollama_api
  mac_require_lane_architecture

  if [[ ! -f "${OBSERVATION_FILE}" ]]; then
    echo "Missing runtime observation. Run 8.1.sh first." >&2
    exit 1
  fi
  if ! curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    echo "Ollama is not responding. Run 8.1.sh first." >&2
    exit 1
  fi

  mac_record_models_before_trial
  mac_resolve_acceleration

  local ram_gib free_disk
  local candidates=()
  local line
  ram_gib="$(mac_ram_gib_from_observation)"
  free_disk="$(mac_free_disk_gib_from_observation)"

  if [[ -n "${REQUESTED_MODEL}" ]]; then
    mac_validate_model_tag "${REQUESTED_MODEL}"
    candidates=("${REQUESTED_MODEL}")
  else
    while IFS= read -r line; do
      [[ -z "${line}" ]] && continue
      candidates+=("${line}")
    done < <(mac_build_candidate_ladder "${ram_gib}" | mac_filter_candidates_by_disk "${free_disk}")
  fi

  if [[ "${#candidates[@]}" -eq 0 ]]; then
    echo "No trial candidates remain after disk guards." >&2
    exit 1
  fi

  local model selected="" status="FAILED"
  for model in "${candidates[@]}"; do
    mac_log "Trying candidate ${model}"
    if ! ollama pull "${model}"; then
      mac_remove_model_if_new "${model}"
      continue
    fi
    if mac_test_model_generate "${model}"; then
      selected="${model}"
      status="PASSED"
      break
    fi
    mac_remove_model_if_new "${model}"
  done

  if [[ -z "${selected}" ]]; then
    mac_write_result_record "none" "${status}" "${MAC_ACCELERATION}"
    echo "No candidate passed the local inference test." >&2
    exit 1
  fi

  mac_write_result_record "${selected}" "${status}" "${MAC_ACCELERATION}"
  mac_log "Selected model ${selected}; result written to ${RESULT_FILE}"
}

main "$@"
