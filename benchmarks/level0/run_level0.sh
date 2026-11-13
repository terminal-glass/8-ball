#!/usr/bin/env bash
# Emulate a level-0 (Raspberry Pi class) machine with a cgroup v2 slice and
# run the canary benchmark inside it. Needs root (sudo) for the cgroup only;
# Ollama itself runs as the invoking user.
#
#   OLLAMA_BIN=/path/to/ollama OLLAMA_MODELS=/path/to/models \
#   PROFILE=l0-4c-2g CPUS=0-3 NUM_THREAD=4 CPU_MAX="max 100000" MEM_MAX=2G \
#   ./run_level0.sh tinyllama:1.1b llama3.2:1b
#
# Add CRON_MINUTES=10 (and RUNS=0 to skip the benchmark) for the cron test.
#
# CPU_MAX is cgroup cpu.max ("max 100000" = 4 full cores when CPUS=0-3,
# "200000 100000" = 2 cores' worth spread over the 4 pinned cores).
set -euo pipefail
: "${OLLAMA_BIN:?}" "${OLLAMA_MODELS:?}"
PROFILE=${PROFILE:-l0-4c-2g} CPUS=${CPUS:-0-3} CPU_MAX=${CPU_MAX:-max 100000}
NUM_THREAD=${NUM_THREAD:-4} MEM_MAX=${MEM_MAX:-2G} RUNS=${RUNS:-3} NUM_CTX=${NUM_CTX:-4096} PORT=${PORT:-11555}
OUT=${OUT:-$(dirname "$0")/results/box-emulated-$PROFILE}; mkdir -p "$OUT"
here=$(cd "$(dirname "$0")" && pwd)
CG=/sys/fs/cgroup/l0emu-$PROFILE
cleanup() { [ -n "${CRONPID:-}" ] && sudo kill "$CRONPID" 2>/dev/null; [ -n "${SPID:-}" ] && kill "$SPID" 2>/dev/null; sleep 2
  pkill -f "ollama runner" 2>/dev/null || true; sudo rmdir "$CG" 2>/dev/null || true; }
trap cleanup EXIT
sudo mkdir -p "$CG"
echo "$CPUS" | sudo tee "$CG/cpuset.cpus" >/dev/null
echo 0       | sudo tee "$CG/cpuset.mems" >/dev/null
echo "$CPU_MAX" | sudo tee "$CG/cpu.max" >/dev/null
echo "$MEM_MAX" | sudo tee "$CG/memory.max" >/dev/null
echo 0 | sudo tee "$CG/memory.swap.max" >/dev/null 2>&1 || true
# start ollama inside the cgroup: move this subshell in, then drop to our user
( me=$BASHPID; echo "$me" | sudo tee "$CG/cgroup.procs" >/dev/null
  exec env OLLAMA_HOST=127.0.0.1:$PORT OLLAMA_MODELS="$OLLAMA_MODELS" \
    OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=10m \
    "$OLLAMA_BIN" serve ) > "$OUT/.serve.log" 2>&1 &
SPID=$!
for i in $(seq 60); do curl -fs "http://127.0.0.1:$PORT/api/version" >/dev/null && break; sleep 1; done
curl -fs "http://127.0.0.1:$PORT/api/version" >/dev/null || { echo "ollama did not start"; cat "$OUT/.serve.log"; exit 1; }
[ "$RUNS" -gt 0 ] && {
  echo "# profile=$PROFILE cpus=$CPUS cpu.max='$CPU_MAX' memory.max=$MEM_MAX swap=0 num_ctx=$NUM_CTX num_thread=$NUM_THREAD"
  echo "# cpu_model=$(lscpu | sed -n 's/^Model name: *//p') ollama=$("$OLLAMA_BIN" --version 2>/dev/null | tail -1 | awk '{print $NF}') date=$(date -Is)"
} > "$OUT/bench.jsonl"
args=(); for m in "$@"; do args+=(--model "$m"); done
[ "$RUNS" -gt 0 ] && python3 "$here/l0_bench.py" --host 127.0.0.1:$PORT --runs "$RUNS" --num-ctx "$NUM_CTX" --num-thread "$NUM_THREAD" \
  --cgroup "$CG" --profile "$PROFILE" "${args[@]}" | tee -a "$OUT/bench.jsonl"

# Optional: cron reliability under load, with the cron daemon inside the same
# CPU/RAM slice (a real Pi shares its 4 cores between cron and the model).
if [ -n "${CRON_MINUTES:-}" ]; then
  if ! pgrep -x cron >/dev/null; then
    ( me=$BASHPID; echo "$me" | sudo tee "$CG/cgroup.procs" >/dev/null; exec sudo cron -f ) &
    sleep 2; CRONPID=$(pgrep -x -n cron)
  fi
  OLLAMA_HOST=127.0.0.1:$PORT MODEL=${CRON_MODEL:-llama3.2:1b} MINUTES=$CRON_MINUTES \
    NUM_THREAD=$NUM_THREAD OUT=$OUT LABEL=$(echo "${CRON_MODEL:-llama3.2:1b}" | tr ':/' '__') "$here/cron_test.sh"
fi
