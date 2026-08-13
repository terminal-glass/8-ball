#!/usr/bin/env bash
# 8.2 — public 8-BALL model selection via profile mapping + runtime proof.
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_SCRIPT_VERSION="0.8.0"
EIGHTBALL_INSTALL_PROFILE="ubuntu"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_DIR="${SCRIPT_DIR}/../shared"
REPO_ROOT=""
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
RESULT_FILE="${PHILOSOPHER_ROOT}/8ball-result.txt"
MANIFEST="${EIGHTBALL_MANIFEST:-}"
REQUESTED_MODEL=""
MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-qwen3}"
OLLAMA_API="${OLLAMA_API:-http://127.0.0.1:11434}"
SELECTION_PLAN=""

# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-version.sh"
# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-model-test.sh"

_C10_HOOK=""
for _candidate in \
  "${SHARED_DIR}/c10-model-hook.sh" \
  "${SCRIPT_DIR}/../shared/c10-model-hook.sh"; do
  if [[ -f "${_candidate}" ]]; then
    _C10_HOOK="${_candidate}"
    break
  fi
done
if [[ -n "${_C10_HOOK}" ]]; then
  # shellcheck source=/dev/null
  source "${_C10_HOOK}"
fi

usage() {
  cat <<'EOF'
Usage: 8.2.sh [--manifest PATH] [--model OLLAMA_TAG] [--model-slug SLUG]

Resolves hardware -> profile lane -> candidate models from profiles/<slug>/<lane>/lane.json
with pilot-menu fallback, then proves the selection with a real inference test.
EOF
}

log() {
  printf '[8.2] %s\n' "$*"
}

resolve_repo_root() {
  local dir="${SCRIPT_DIR}"
  while [[ "${dir}" != "/" ]]; do
    if [[ -d "${dir}/profiles" && -d "${dir}/install" ]]; then
      REPO_ROOT="${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  cat >&2 <<EOF
Could not locate 8-ball repository root from ${SCRIPT_DIR}.
Clone the full repository or set EIGHTBALL_REPO_ROOT.
EOF
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --manifest)
        MANIFEST="$2"
        shift 2
        ;;
      --model)
        REQUESTED_MODEL="$2"
        shift 2
        ;;
      --model-slug)
        MODEL_SLUG="$2"
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

load_selection_plan() {
  resolve_repo_root
  export EIGHTBALL_REPO_ROOT="${REPO_ROOT}"
  local -a args=(plan)
  [[ -n "${REQUESTED_MODEL}" ]] && args+=(--model "${REQUESTED_MODEL}")
  [[ -n "${MODEL_SLUG}" ]] && args+=(--slug "${MODEL_SLUG}")
  if [[ -n "${EIGHTBALL_INSTALL_LANE:-}" ]]; then
    args+=(--lane "${EIGHTBALL_INSTALL_LANE}")
  fi
  SELECTION_PLAN="$(
    python3 "${SHARED_DIR}/c10-hardware-resolve.py" "${args[@]}"
  )"
}

plan_field() {
  local field="$1"
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get(sys.argv[1], ""))' "${field}" <<<"${SELECTION_PLAN}"
}

hardware_field() {
  local field="$1"
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("hardware", {}).get(sys.argv[1], ""))' "${field}" <<<"${SELECTION_PLAN}"
}

gpu_field() {
  local field="$1"
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("hardware", {}).get("gpu", {}).get(sys.argv[1], ""))' "${field}" <<<"${SELECTION_PLAN}"
}

candidate_list() {
  python3 -c 'import json,sys; print("\n".join(json.load(sys.stdin).get("candidates", [])))' <<<"${SELECTION_PLAN}"
}

minimum_disk_for_model() {
  local model="$1"
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("minimum_disk_mib", {}).get(sys.argv[1], 3072))' "${model}" <<<"${SELECTION_PLAN}"
}

write_result() {
  local model="$1" test_status="$2" selection_source="$3"
  local lane tier os_name distro ram cpu disk gpu_name gpu_vram
  lane="$(plan_field lane_path)"
  tier="$(plan_field tier)"
  selection_source="$(plan_field selection_source)"
  os_name="$(hardware_field os)"
  distro="$(hardware_field distro)"
  ram="$(hardware_field ram_mb)"
  cpu="$(hardware_field cpu_threads)"
  disk="$(hardware_field free_disk_mb)"
  gpu_name="$(gpu_field name)"
  gpu_vram="$(gpu_field vram_mb)"
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  cat >"${RESULT_FILE}" <<EOF
Model: ${model}
Profile: ${model//[:\/]/-}
Install profile: ${EIGHTBALL_INSTALL_PROFILE}
Install lane: ${EIGHTBALL_INSTALL_LANE:-${lane}}
Detected OS: ${os_name}/${distro}
Detected platform/profile: ${lane}
Model slug: ${MODEL_SLUG}
Tier: ${tier}
Selection source: ${selection_source}
Model test: ${test_status}
Jets status: READY_AFTER_SIGNIN
RAM MB: ${ram}
CPU threads: ${cpu}
Free disk MB: ${disk}
GPU: ${gpu_name}
GPU VRAM MB: ${gpu_vram}
Provider assumption: $(plan_field provider_assumption)
Resolution source: $(plan_field resolution_source)
Manifest: ${MANIFEST:-n/a}
EOF
  chmod 0644 "${RESULT_FILE}"
}

install_8balljets_helper() {
  cat >/usr/local/bin/8balljets <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "8-BALL JETS cloud options are available after sign-in."
echo "This public trial installer does not activate paid features."
echo "Support: 8ball@terminal.glass"
EOF
  chmod 0755 /usr/local/bin/8balljets
}

run_manual_override() {
  local model="$1"
  local before_file free_disk min_disk
  before_file="$(mktemp)"
  eightball_models_before_pull >"${before_file}"
  free_disk="$(hardware_field free_disk_mb)"
  min_disk="$(minimum_disk_for_model "${model}")"
  if [[ "${free_disk}" =~ ^[0-9]+$ ]] && [[ "${free_disk}" -lt "${min_disk}" ]]; then
    echo "Insufficient free disk (${free_disk} MB) for ${model} (need ~${min_disk} MB)." >&2
    rm -f "${before_file}"
    exit 1
  fi
  if eightball_pull_and_test "${model}" "${before_file}"; then
    write_result "${model}" "PASSED" "manual-override"
    install_8balljets_helper
    rm -f "${before_file}"
    return 0
  fi
  write_result "${model}" "FAILED" "manual-override"
  rm -f "${before_file}"
  echo "Manual model override failed for ${model}." >&2
  exit 1
}

run_candidate_chain() {
  local candidate before_file tested_model=""
  before_file="$(mktemp)"
  eightball_models_before_pull >"${before_file}"
  while IFS= read -r candidate; do
    [[ -z "${candidate}" ]] && continue
    log "Trying candidate ${candidate}"
    if eightball_pull_and_test "${candidate}" "${before_file}"; then
      tested_model="${candidate}"
      break
    fi
    log "Candidate ${candidate} failed pull or inference test"
  done < <(candidate_list)
  rm -f "${before_file}"
  if [[ -n "${tested_model}" ]]; then
    write_result "${tested_model}" "PASSED" "$(plan_field selection_source)"
    install_8balljets_helper
    log "Model test passed; result written to ${RESULT_FILE}"
    return 0
  fi
  write_result "$(candidate_list | head -n1)" "FAILED" "$(plan_field selection_source)"
  echo "Model test failed for all candidates." >&2
  exit 1
}

main() {
  parse_args "$@"
  eightball_verify_script_version "${BASH_SOURCE[0]}" "8.2.sh"
  if ! curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    echo "Ollama is not responding. Run 8.1.sh first." >&2
    exit 1
  fi

  if [[ -n "${MODEL_SLUG}" && -z "${REQUESTED_MODEL}" ]] && declare -F c10_select_model_slug >/dev/null 2>&1; then
    local c10_model=""
    if c10_model="$(c10_select_model_slug "${MODEL_SLUG}")"; then
      log "C10 selected ${c10_model} for model slug ${MODEL_SLUG}"
      REQUESTED_MODEL="${c10_model}"
    fi
  fi

  load_selection_plan
  log "Resolved lane $(plan_field lane_path) via $(plan_field resolution_source)"
  log "Selection source: $(plan_field selection_source)"

  if [[ -n "${REQUESTED_MODEL}" ]]; then
    run_manual_override "${REQUESTED_MODEL}"
    exit 0
  fi

  run_candidate_chain
}

main "$@"
