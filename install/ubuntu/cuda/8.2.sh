#!/usr/bin/env bash
# 8.2 — public 8-BALL model selection using committed profile lane data.
# Install lane: ubuntu/cuda
set -euo pipefail

EIGHTBALL_INSTALL_LANE="ubuntu/cuda"
EIGHTBALL_INSTALL_PROFILE="ubuntu/cuda"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/ubuntu-cuda.json"
UBUNTU_LOG_PREFIX="8.2"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/ubuntu-common.sh
source "${SCRIPT_DIR}/../lib/ubuntu-common.sh"

INSTALLER_SMOKE_SCRIPT_NAME="8.2.sh"
INSTALLER_SMOKE_PLATFORM="linux"
INSTALLER_SMOKE_CHECKS="- Verify profile lane data availability
- Would select and verify a local model from committed profiles during a real install (requires root)"
# shellcheck source=../../shared/installer-smoke-contract.sh
source "${SCRIPT_DIR}/../../shared/installer-smoke-contract.sh"

REQUESTED_MODEL=""
MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-}"

usage() {
  cat <<'EOF'
Usage: 8.2.sh [--model OLLAMA_TAG] [--model-slug SLUG]

Selects a model using profiles/<slug>/ubuntu/cuda/lane.json and measured hardware.
Public installs require --model-slug unless --model is supplied with a matching slug.

Developer-only legacy manifest guessing requires:
  EIGHTBALL_LEGACY_MANIFEST_SELECTION=1
EOF
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
      --manifest)
        echo "8.2 no longer accepts --manifest on the public path. Use profile lane data." >&2
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

require_model_slug() {
  if [[ -z "${MODEL_SLUG}" ]]; then
    cat >&2 <<'EOF'
Missing model slug for profile-driven selection.

Provide one of:
  --model-slug <slug>     (recommended public path)
  --model <tag>           (requires the same slug via EIGHTBALL_MODEL_SLUG)

The public installer does not guess models from install-manifest.json.
EOF
    exit 1
  fi
}

select_model() {
  local selection_json selected reason
  ubuntu_write_hardware_env

  if [[ -n "${REQUESTED_MODEL}" ]]; then
    require_model_slug
    if ! selection_json="$(ubuntu_profile_runtime validate --model-slug "${MODEL_SLUG}" --lane "${EIGHTBALL_INSTALL_LANE}" --model "${REQUESTED_MODEL}")"; then
      echo "${selection_json}" >&2
      exit 1
    fi
    reason="manual_model_validated"
  else
    require_model_slug
    if ! selection_json="$(ubuntu_profile_runtime select --model-slug "${MODEL_SLUG}" --lane "${EIGHTBALL_INSTALL_LANE}")"; then
      echo "${selection_json}" >&2
      exit 1
    fi
    reason="profile_lane_selected"
  fi

  selected="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("selected_ollama_ref") or "")' <<<"${selection_json}")"
  if [[ -z "${selected}" ]]; then
    echo "${selection_json}" >&2
    exit 1
  fi
  ubuntu_write_recommendation_env "${selected}" "${MODEL_SLUG}" "${reason}"
  printf '%s' "${selected}"
}

legacy_manifest_selection() {
  cat >&2 <<'EOF'
EIGHTBALL_LEGACY_MANIFEST_SELECTION is enabled (developer only).
The public installer path must use profile lane artifacts instead.
EOF
  exit 1
}

test_model_with_fallback() {
  local primary="$1"
  if ubuntu_test_model_generate "${primary}"; then
    printf '%s' "${primary}"
    return 0
  fi
  ubuntu_remove_failed_model "${primary}"

  local lane_json repo_root candidate
  repo_root="$(ubuntu_find_repo_root)" || return 1
  lane_json="${repo_root}/profiles/${MODEL_SLUG}/${EIGHTBALL_INSTALL_LANE}/lane.json"
  [[ -f "${lane_json}" ]] || return 1
  while IFS= read -r candidate; do
    [[ -z "${candidate}" || "${candidate}" == "${primary}" ]] && continue
    ubuntu_log "Primary pull failed; trying fallback ${candidate}"
    if ubuntu_test_model_generate "${candidate}"; then
      printf '%s' "${candidate}"
      return 0
    fi
    ubuntu_remove_failed_model "${candidate}"
  done < <(python3 - "${lane_json}" <<'PY'
import json, sys
from pathlib import Path
lane = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for row in reversed(lane.get("size_fit", [])):
    if row.get("fit_status") == "fit" and row.get("fits"):
        print(row["ollama_ref"])
PY
)
  return 1
}

main() {
  installer_smoke_prologue "$@"
  parse_args "$@"
  if [[ "${EIGHTBALL_LEGACY_MANIFEST_SELECTION:-0}" == "1" ]]; then
    legacy_manifest_selection
  fi

  ubuntu_validate_ollama_api
  ubuntu_ensure_state_root
  ubuntu_resolve_profile_dir

  if ! curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    echo "Ollama is not responding. Run 8.1.sh first." >&2
    exit 1
  fi

  selected_model="$(select_model)"
  ubuntu_log "Selected model ${selected_model}"

  local tested_model tier="LOCAL LITE" test_status="FAILED"
  if tested_model="$(test_model_with_fallback "${selected_model}")"; then
    test_status="PASSED"
    ubuntu_write_result_env "${tested_model}" "${MODEL_SLUG}" "${test_status}" "${tier}"
    ubuntu_install_8balljets_helper
    ubuntu_log "Model test passed; result written to ${RESULT_FILE}"
  else
    ubuntu_write_result_env "${selected_model}" "${MODEL_SLUG}" "${test_status}" "${tier}"
    echo "Model test failed for ${selected_model} (no smaller fallback succeeded)" >&2
    exit 1
  fi
}

main "$@"
