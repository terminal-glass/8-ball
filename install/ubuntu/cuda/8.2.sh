#!/usr/bin/env bash
# 8.2 — public 8-BALL model selection using install-manifest.json.
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_INSTALL_PROFILE="ubuntu/cuda"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=""
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
RESULT_FILE="${PHILOSOPHER_ROOT}/8ball-result.txt"
MANIFEST="${EIGHTBALL_MANIFEST:-}"
REQUESTED_MODEL=""
MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-}"
OLLAMA_API="${OLLAMA_API:-http://127.0.0.1:11434}"

# Locate shared C10 helpers from lane or profile install directories.
_C10_HOOK=""
for _candidate in \
  "${SCRIPT_DIR}/../shared/c10-model-hook.sh" \
  "${SCRIPT_DIR}/../../shared/c10-model-hook.sh" \
  "${SCRIPT_DIR}/../../../shared/c10-model-hook.sh"; do
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

Reads profiles/<model-slug>.json when --model-slug is provided, otherwise uses
data/generated/pages/install-manifest.json for conservative trial selection.
EOF
}

log() {
  printf '[8.2] %s\n' "$*"
}

resolve_repo_root() {
  local dir="${SCRIPT_DIR}"
  while [[ "${dir}" != "/" ]]; do
    if [[ -f "${dir}/data/generated/pages/install-manifest.json" ]]; then
      REPO_ROOT="${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  cat >&2 <<EOF
Could not locate 8-ball repository root from ${SCRIPT_DIR}.
Clone the full repository or set EIGHTBALL_MANIFEST to install-manifest.json.
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

require_manifest() {
  if [[ -z "${MANIFEST}" ]]; then
    resolve_repo_root
    MANIFEST="${REPO_ROOT}/data/generated/pages/install-manifest.json"
  fi
  if [[ ! -f "${MANIFEST}" ]]; then
    cat >&2 <<EOF
Missing catalog manifest: ${MANIFEST}

Clone the full 8-ball repository or set EIGHTBALL_MANIFEST to a generated
data/generated/pages/install-manifest.json file. This script does not guess models
from Markdown or private installer assets.
EOF
    exit 1
  fi
}

detect_hardware() {
  RAM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
  CPU_THREADS="$(nproc 2>/dev/null || echo 1)"
  FREE_DISK_MB="$(df -Pm / | awk 'NR==2 {print $4}')"
  GPU_NAME="none"
  GPU_VRAM_MB="0"
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 || echo none)"
    GPU_VRAM_MB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || echo 0)"
  fi
}

deployment_type_for_hardware() {
  if [[ "${GPU_VRAM_MB}" =~ ^[0-9]+$ ]] && [[ "${GPU_VRAM_MB}" -ge 12000 ]]; then
    echo 7
  elif [[ "${GPU_VRAM_MB}" =~ ^[0-9]+$ ]] && [[ "${GPU_VRAM_MB}" -ge 6000 ]]; then
    echo 6
  elif [[ "${RAM_MB}" -ge 16000 ]]; then
    echo 5
  elif [[ "${RAM_MB}" -ge 8000 ]]; then
    echo 4
  else
    echo 3
  fi
}

select_model_from_manifest() {
  local deployment_type="$1"
  python3 - "${MANIFEST}" "${deployment_type}" "${REQUESTED_MODEL}" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
deployment_type = sys.argv[2]
requested = sys.argv[3]
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
models = manifest.get("models", {})

def deployment_entry(model_entry):
    deployments = model_entry.get("deployments", {})
    return deployments.get(deployment_type)

preferred_order = [
    "qwen3:0.6b",
    "tinyllama:latest",
    "llama3.2:1b",
    "phi3:mini",
]

if requested:
    for model_id, entry in models.items():
        deployment = deployment_entry(entry)
        if not deployment:
            continue
        ollama_id = deployment.get("ollama_identifier") or ""
        if ollama_id == requested or ollama_id.endswith(f":{requested}"):
            print(ollama_id)
            raise SystemExit(0)
    print(requested)
    raise SystemExit(0)

for candidate in preferred_order:
    for model_id, entry in models.items():
        deployment = deployment_entry(entry)
        if not deployment:
            continue
        ollama_id = deployment.get("ollama_identifier") or ""
        if ollama_id == candidate:
            print(ollama_id)
            raise SystemExit(0)

for model_id, entry in sorted(models.items()):
    deployment = deployment_entry(entry)
    if deployment and deployment.get("ollama_identifier"):
        print(deployment["ollama_identifier"])
        raise SystemExit(0)

raise SystemExit("No deployable model found in manifest")
PY
}

test_model() {
  local model="$1"
  if ! ollama pull "${model}"; then
    return 1
  fi
  local response
  response="$(
    curl -fsS "${OLLAMA_API}/api/generate" \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"${model}\",\"prompt\":\"Reply with only: 8-BALL READY\",\"stream\":false}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("response",""))'
  )"
  if grep -qi "8-BALL READY" <<<"${response}"; then
    return 0
  fi
  log "Model response did not contain expected token: ${response}"
  return 1
}

test_model_with_fallback() {
  local primary="$1"
  if test_model "${primary}"; then
    printf '%s' "${primary}"
    return 0
  fi
  if [[ -n "${MODEL_SLUG}" ]] && declare -F c10_fallback_pull >/dev/null 2>&1; then
    local candidate
    while IFS= read -r candidate; do
      [[ -z "${candidate}" || "${candidate}" == "${primary}" ]] && continue
      log "Pull failed for ${primary}; trying fallback ${candidate}"
      if test_model "${candidate}"; then
        printf '%s' "${candidate}"
        return 0
      fi
    done < <(c10_fallback_pull "${MODEL_SLUG}")
  fi
  return 1
}

write_result() {
  local model="$1" tier="$2" test_status="$3"
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  cat >"${RESULT_FILE}" <<EOF
Model: ${model}
Profile: ${model//[:\/]/-}
Install profile: ${EIGHTBALL_INSTALL_PROFILE}
Install lane: ${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE}}
Model slug: ${MODEL_SLUG:-n/a}
Tier: ${tier}
Model test: ${test_status}
Jets status: READY_AFTER_SIGNIN
RAM MB: ${RAM_MB}
CPU threads: ${CPU_THREADS}
Free disk MB: ${FREE_DISK_MB}
GPU: ${GPU_NAME}
GPU VRAM MB: ${GPU_VRAM_MB}
Manifest: ${MANIFEST}
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

main() {
  parse_args "$@"
  if ! curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    echo "Ollama is not responding. Run 8.1.sh first." >&2
    exit 1
  fi
  detect_hardware
  selected_model=""
  if [[ -n "${MODEL_SLUG}" ]] && declare -F c10_select_model_slug >/dev/null 2>&1; then
    if selected_model="$(c10_select_model_slug "${MODEL_SLUG}")"; then
      log "C10 selected ${selected_model} for model slug ${MODEL_SLUG}"
    fi
  fi
  if [[ -z "${selected_model}" ]]; then
    require_manifest
    deployment_type="$(deployment_type_for_hardware)"
    log "Using deployment type ${deployment_type} from manifest ${MANIFEST}"
    selected_model="$(select_model_from_manifest "${deployment_type}")"
  fi
  log "Selected model ${selected_model}"
  tier="LOCAL LITE"
  if tested_model="$(test_model_with_fallback "${selected_model}")"; then
    write_result "${tested_model}" "${tier}" "PASSED"
    install_8balljets_helper
    log "Model test passed; result written to ${RESULT_FILE}"
  else
    write_result "${selected_model}" "${tier}" "FAILED"
    echo "Model test failed for ${selected_model} (no smaller fallback succeeded)" >&2
    exit 1
  fi
}

main "$@"
