#!/usr/bin/env bash
# 8-BALL model selection, pull/test/fallback, result file, and 8balljets helper.
set -euo pipefail

VERSION="8.2 model selection 1.0.0"
LOG_FILE="/opt/philosopher/trial-log.txt"
RESULT_FILE="/opt/philosopher/8ball-result.txt"
PHILOSOPHER_ROOT="/opt/philosopher"
JETS_HELPER="/usr/local/bin/8balljets"

REQUESTED_MODEL=""
SELECTED_MODEL=""
SELECTED_PROFILE=""
SELECTED_TIER=""
MODEL_TEST_STATUS="FAILED"
JETS_STATUS="READY_AFTER_SIGNIN"

EXISTING_MODELS_FILE=""

RAM_MB=0
CPU_THREADS=0
FREE_DISK_MB=0
GPU_NAME="none"
GPU_VRAM_MB=0

log() {
  local message="$1"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message" >>"$LOG_FILE"
}

die() {
  echo "ERROR: $*" >&2
  write_result_file
  exit 1
}

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "8.2 must run as root"
}

require_ollama() {
  command -v ollama >/dev/null 2>&1 || die "Ollama is not installed. Run 8.1 first."
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null || die "Ollama API is not responding locally."
}

read_hardware() {
  RAM_MB="$(awk '/MemTotal:/ {print int($2/1024)}' /proc/meminfo)"
  CPU_THREADS="$(nproc)"
  FREE_DISK_MB="$(df -Pm "$PHILOSOPHER_ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [[ -z "$FREE_DISK_MB" ]]; then
    FREE_DISK_MB="$(df -Pm / | awk 'NR==2 {print $4}')"
  fi

  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 | xargs || true)"
    GPU_VRAM_MB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 | awk '{print int($1)}' || true)"
  fi
  [[ -n "$GPU_NAME" ]] || GPU_NAME="none"
  [[ -n "$GPU_VRAM_MB" ]] || GPU_VRAM_MB=0
}

profile_for_model() {
  local model="$1"
  echo "${model//:/-}"
}

tier_for_model() {
  local model="$1"
  case "$model" in
    *:0.6b|*:1b|tinyllama*|phi3:mini*) echo "LOCAL LITE" ;;
    *:1.7b|*:2b|*:3b) echo "LOCAL STANDARD" ;;
    *) echo "LOCAL PLUS" ;;
  esac
}

build_candidate_list() {
  local -a candidates=()
  if [[ "$RAM_MB" -ge 32000 ]]; then
    candidates+=(qwen3:8b qwen3:4b qwen3:1.7b qwen3:0.6b tinyllama)
  elif [[ "$RAM_MB" -ge 16000 ]]; then
    candidates+=(qwen3:4b qwen3:1.7b qwen3:0.6b tinyllama)
  elif [[ "$RAM_MB" -ge 8000 ]]; then
    candidates+=(qwen3:1.7b qwen3:0.6b tinyllama)
  elif [[ "$RAM_MB" -ge 4000 ]]; then
    candidates+=(qwen3:0.6b tinyllama)
  else
    candidates+=(tinyllama)
  fi
  printf '%s\n' "${candidates[@]}"
}

snapshot_existing_models() {
  EXISTING_MODELS_FILE="$(mktemp /tmp/8ball-existing-models.XXXXXX)"
  ollama list 2>/dev/null | awk 'NR>1 {print $1}' | sort -u >"$EXISTING_MODELS_FILE"
}

model_was_preexisting() {
  local model="$1"
  grep -Fxq "$model" "$EXISTING_MODELS_FILE"
}

pull_model() {
  local model="$1"
  log "Pulling model ${model}"
  ollama pull "$model"
}

remove_newly_pulled_model() {
  local model="$1"
  if model_was_preexisting "$model"; then
    log "Leaving pre-existing model installed: ${model}"
    return 0
  fi
  log "Removing newly pulled model after failure: ${model}"
  ollama rm "$model" >/dev/null 2>&1 || true
}

test_model() {
  local model="$1"
  local response
  if ! response="$(
    curl -fsS http://127.0.0.1:11434/api/generate \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"${model}\",\"prompt\":\"Reply with exactly OK.\",\"stream\":false,\"options\":{\"num_predict\":16}}" \
      --max-time 180
  )"; then
    return 1
  fi
  echo "$response" | jq -er '.response | length > 0' >/dev/null 2>&1
}

try_model() {
  local model="$1"
  pull_model "$model"
  if test_model "$model"; then
    SELECTED_MODEL="$model"
    SELECTED_PROFILE="$(profile_for_model "$model")"
    SELECTED_TIER="$(tier_for_model "$model")"
    MODEL_TEST_STATUS="PASSED"
    return 0
  fi
  remove_newly_pulled_model "$model"
  return 1
}

write_result_file() {
  install -d -m 0755 "$PHILOSOPHER_ROOT"
  cat >"$RESULT_FILE" <<EOF
Model: ${SELECTED_MODEL:-none}
Profile: ${SELECTED_PROFILE:-none}
Tier: ${SELECTED_TIER:-none}
Model test: ${MODEL_TEST_STATUS}
Jets status: ${JETS_STATUS}
RAM MB: ${RAM_MB}
CPU threads: ${CPU_THREADS}
Free disk MB: ${FREE_DISK_MB}
GPU: ${GPU_NAME}
GPU VRAM MB: ${GPU_VRAM_MB}
EOF
  chmod 0644 "$RESULT_FILE"
}

install_8balljets_helper() {
  cat >"$JETS_HELPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

RESULT_FILE="/opt/philosopher/8ball-result.txt"

echo "8-BALL JETS"
echo "==========="
echo
echo "8-BALL JETS are cloud-capable models you can use after sign-in."
echo "This public trial installer keeps local AI working on your machine."
echo
if [[ -f "$RESULT_FILE" ]]; then
  echo "Current local result:"
  sed -n '1,12p' "$RESULT_FILE"
  echo
fi
echo "Local model command:"
if [[ -f "$RESULT_FILE" ]]; then
  model="$(awk -F': ' '/^Model:/ {print $2}' "$RESULT_FILE" | head -n1)"
  if [[ -n "$model" && "$model" != "none" ]]; then
    echo "  ollama run ${model}"
  else
    echo "  ollama list"
  fi
else
  echo "  cat ${RESULT_FILE}"
fi
echo
echo "Jets status: READY AFTER SIGN-IN"
echo "This helper does not activate paid features."
EOF
  chmod 0755 "$JETS_HELPER"
}

select_model() {
  if [[ -n "$REQUESTED_MODEL" ]]; then
    log "Requested model: ${REQUESTED_MODEL}"
    if try_model "$REQUESTED_MODEL"; then
      return 0
    fi
    die "Requested model failed pull or inference test: ${REQUESTED_MODEL}"
  fi

  local candidate
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    log "Trying candidate model: ${candidate}"
    if try_model "$candidate"; then
      return 0
    fi
  done < <(build_candidate_list)

  die "No candidate model passed pull and inference testing"
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model)
        [[ $# -ge 2 ]] || die "--model requires a value"
        REQUESTED_MODEL="$2"
        shift 2
        ;;
      -h|--help)
        echo "Usage: sudo ./8.2.sh [--model <tag>]"
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done

  require_root
  require_ollama
  log "Starting ${VERSION}"
  snapshot_existing_models
  trap 'rm -f "$EXISTING_MODELS_FILE"' EXIT
  read_hardware
  select_model
  write_result_file
  install_8balljets_helper
  log "Completed ${VERSION}; selected model ${SELECTED_MODEL}"
  echo "8.2 complete: model ${SELECTED_MODEL} tested successfully."
  echo "Result written to ${RESULT_FILE}"
}

main "$@"
