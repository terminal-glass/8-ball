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
RESULT_JSON="${PHILOSOPHER_ROOT}/8ball-result.json"
MANIFEST="${EIGHTBALL_MANIFEST:-}"
REQUESTED_MODEL=""
MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-}"
OLLAMA_API="${OLLAMA_API:-http://127.0.0.1:11434}"
SELECTION_PLAN=""
ATTEMPT_LOG="[]"

# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-version.sh"
# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-model-test.sh"

usage() {
  cat <<'EOF'
Usage: 8.2.sh [--manifest PATH] [--model OLLAMA_TAG] [--model-slug SLUG]

Resolves hardware -> profile lane -> approved candidates from profiles/<slug>/<lane>/
using runtime profile fit evaluation, then proves the selection with a real inference test.
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
  [[ -n "${MANIFEST}" ]] && args+=(--manifest "${MANIFEST}")
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
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("minimum_disk_mib", {}).get(sys.argv[1], ""))' "${model}" <<<"${SELECTION_PLAN}"
}

record_attempt() {
  local candidate="$1" gate_status="$2" pull_status="$3" inference_status="$4" note="$5"
  ATTEMPT_LOG="$(
    python3 - "${candidate}" "${gate_status}" "${pull_status}" "${inference_status}" "${note}" "${ATTEMPT_LOG}" <<'PY'
import json, sys
candidate, gate_status, pull_status, inference_status, note, current = sys.argv[1:7]
attempts = json.loads(current) if current else []
attempts.append({
    "candidate": candidate,
    "resource_gate": gate_status,
    "pull": pull_status,
    "inference": inference_status,
    "note": note,
})
print(json.dumps(attempts))
PY
  )"
}

write_result() {
  local model="$1" test_status="$2" selection_source="$3"
  local lane tier os_name distro ram cpu disk gpu_name gpu_vram profile_id slug
  lane="$(plan_field lane_path)"
  tier="$(plan_field tier)"
  profile_id="$(plan_field profile_id)"
  slug="$(plan_field model_slug)"
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
Profile: ${profile_id}
Install profile: ${EIGHTBALL_INSTALL_PROFILE}
Install lane: ${EIGHTBALL_INSTALL_LANE:-${lane}}
Detected OS: ${os_name}/${distro}
Detected platform/profile: ${lane}
Model slug: ${slug}
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

  python3 - "${RESULT_JSON}" "${model}" "${test_status}" "${selection_source}" "${profile_id}" "${slug}" "${lane}" "${tier}" "${ATTEMPT_LOG}" "${SELECTION_PLAN}" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

result_json, model, test_status, selection_source, profile_id, slug, lane, tier, attempts_json, plan_json = sys.argv[1:11]
plan = json.loads(plan_json)
payload = {
    "selected_model": model,
    "test_status": test_status,
    "selection_source": selection_source,
    "profile_id": profile_id,
    "model_slug": slug,
    "lane": lane,
    "tier": tier,
    "inference_succeeded": test_status == "PASSED",
    "manual_selection_status": plan.get("manual_selection_status"),
    "manual_rejection_reason": plan.get("manual_rejection_reason"),
    "fallback_chain": plan.get("fallback_chain", []),
    "attempts": json.loads(attempts_json) if attempts_json else [],
    "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
Path(result_json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  chmod 0644 "${RESULT_JSON}"
}

install_8balljets_helper() {
  local target="${EIGHTBALL_BIN_DIR:-/usr/local/bin}/8balljets"
  install -d -m 0755 "$(dirname "${target}")"
  cat >"${target}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "8-BALL JETS cloud options are available after sign-in."
echo "This public trial installer does not activate paid features."
echo "Support: 8ball@terminal.glass"
EOF
  chmod 0755 "${target}"
}

candidate_passes_disk_gate() {
  local model="$1"
  local free_disk min_disk
  free_disk="$(hardware_field free_disk_mb)"
  min_disk="$(minimum_disk_for_model "${model}")"
  if [[ -z "${min_disk}" ]]; then
    return 0
  fi
  if [[ "${free_disk}" =~ ^[0-9]+$ ]] && [[ "${free_disk}" -lt "${min_disk}" ]]; then
    return 1
  fi
  return 0
}

run_manual_override() {
  local model="$1"
  local manual_status
  manual_status="$(plan_field manual_selection_status)"
  if [[ "${manual_status}" == "rejected-by-gates" ]]; then
    echo "Requested model ${model} does not fit measured hardware: $(plan_field manual_rejection_reason)" >&2
    write_result "${model}" "FAILED" "manual-override-rejected-by-gates"
    exit 1
  fi
  if [[ "${manual_status}" == "unknown-metadata" ]]; then
    log "Requested model ${model} lacks approved profile metadata; proceeding without resource gates"
  fi
  local before_file
  before_file="$(mktemp)"
  eightball_models_before_pull >"${before_file}"
  if ! candidate_passes_disk_gate "${model}"; then
    local free_disk min_disk
    free_disk="$(hardware_field free_disk_mb)"
    min_disk="$(minimum_disk_for_model "${model}")"
    record_attempt "${model}" "FAILED" "skipped" "skipped" "insufficient disk (${free_disk} < ${min_disk} MiB)"
    echo "Insufficient free disk (${free_disk} MB) for ${model} (need ~${min_disk} MB)." >&2
    write_result "${model}" "FAILED" "manual-override"
    rm -f "${before_file}"
    exit 1
  fi
  record_attempt "${model}" "PASSED" "pending" "pending" "manual override"
  if eightball_pull_and_test "${model}" "${before_file}"; then
    record_attempt "${model}" "PASSED" "PASSED" "PASSED" "manual override succeeded"
    write_result "${model}" "PASSED" "manual-override"
    install_8balljets_helper
    rm -f "${before_file}"
    return 0
  fi
  record_attempt "${model}" "PASSED" "FAILED" "FAILED" "manual override failed pull or inference"
  write_result "${model}" "FAILED" "manual-override"
  rm -f "${before_file}"
  echo "Manual model override failed for ${model}." >&2
  exit 1
}

run_candidate_chain() {
  local candidate before_file tested_model="" first_candidate
  first_candidate="$(candidate_list | head -n1)"
  before_file="$(mktemp)"
  eightball_models_before_pull >"${before_file}"
  while IFS= read -r candidate; do
    [[ -z "${candidate}" ]] && continue
    log "Trying candidate ${candidate}"
    if ! candidate_passes_disk_gate "${candidate}"; then
      local free_disk min_disk
      free_disk="$(hardware_field free_disk_mb)"
      min_disk="$(minimum_disk_for_model "${candidate}")"
      log "Candidate ${candidate} rejected by disk gate (${free_disk} MB free, need ~${min_disk} MB)"
      record_attempt "${candidate}" "FAILED" "skipped" "skipped" "insufficient disk"
      continue
    fi
    record_attempt "${candidate}" "PASSED" "pending" "pending" "automatic candidate"
    if eightball_pull_and_test "${candidate}" "${before_file}"; then
      record_attempt "${candidate}" "PASSED" "PASSED" "PASSED" "candidate succeeded"
      tested_model="${candidate}"
      break
    fi
    record_attempt "${candidate}" "PASSED" "FAILED" "FAILED" "pull or inference failed"
    log "Candidate ${candidate} failed pull or inference test"
  done < <(candidate_list)
  rm -f "${before_file}"
  if [[ -n "${tested_model}" ]]; then
    write_result "${tested_model}" "PASSED" "$(plan_field selection_source)"
    install_8balljets_helper
    log "Model test passed; result written to ${RESULT_FILE}"
    return 0
  fi
  write_result "${first_candidate:-unknown}" "FAILED" "$(plan_field selection_source)"
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

  load_selection_plan
  log "Resolved profile $(plan_field profile_id) via $(plan_field resolution_source)"
  log "Selection source: $(plan_field selection_source)"

  if [[ -n "${REQUESTED_MODEL}" ]]; then
    run_manual_override "${REQUESTED_MODEL}"
    exit 0
  fi

  run_candidate_chain
}

main "$@"
