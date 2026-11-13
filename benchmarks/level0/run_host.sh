#!/usr/bin/env bash
# Level-0 benchmark on a real (or emulated) machine. Runs ON the target.
# Uses the machine as-is (no cgroup caps): Ollama as installed by its official
# installer (systemd service on 127.0.0.1:11434). Installs Ollama only if it
# is missing (INSTALL_OLLAMA=1, the default).
#
#   LABEL=vm-x86-2c-2g ./run_host.sh            # bench + 10-minute cron tests
#   LABEL=... CRON_MINUTES=0 ./run_host.sh      # bench only
#
# Writes results/<LABEL>/bench.jsonl and results/<LABEL>/cron-<model>.json.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
LABEL=${LABEL:?set LABEL, e.g. vm-arm64-2g} MODELS=${MODELS:-tinyllama:1.1b llama3.2:1b}
RUNS=${RUNS:-3} NUM_CTX=${NUM_CTX:-4096} NUM_THREAD=${NUM_THREAD:-$(nproc)}
CRON_MINUTES=${CRON_MINUTES:-10} CRON_MODELS=${CRON_MODELS:-$MODELS}
HOST=${OLLAMA_HOST:-127.0.0.1:11434}
OUT=$here/results/$LABEL; mkdir -p "$OUT"
if ! command -v ollama >/dev/null && [ "${INSTALL_OLLAMA:-1}" = 1 ]; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
for i in $(seq 60); do curl -fs "http://$HOST/api/version" >/dev/null && break; sleep 1; done
for m in $MODELS; do ollama list | awk '{print $1}' | grep -qx "$m" || ollama pull "$m"; done
CG=$(sed -n 's/^0:://p' /proc/$(pgrep -xo ollama)/cgroup 2>/dev/null); CG=/sys/fs/cgroup$CG
{ echo "# label=$LABEL $(nproc) CPU, $(free -m | awk '/Mem:/{print $2}') MiB RAM, swap $(free -m | awk '/Swap:/{print $2}') MiB, arch $(uname -m), no extra caps, num_ctx=$NUM_CTX num_thread=$NUM_THREAD"
  echo "# cpu_model=$(lscpu | sed -n 's/^Model name: *//p' | head -1) ollama=$(ollama --version 2>/dev/null | awk '{print $NF}' | tail -1) os=$( . /etc/os-release; echo "$PRETTY_NAME") date=$(date -Is)"
} > "$OUT/bench.jsonl"
args=(); for m in $MODELS; do args+=(--model "$m"); done
python3 "$here/l0_bench.py" --host "$HOST" --runs "$RUNS" --num-ctx "$NUM_CTX" \
  --num-thread "$NUM_THREAD" --cgroup "$CG" --profile "$LABEL" "${args[@]}" >> "$OUT/bench.jsonl"
if [ "$CRON_MINUTES" -gt 0 ]; then
  command -v crontab >/dev/null || { echo "no cron installed" > "$OUT/cron-missing.txt"; exit 0; }
  for m in $CRON_MODELS; do
    OLLAMA_HOST=$HOST MODEL=$m MINUTES=$CRON_MINUTES NUM_THREAD=$NUM_THREAD \
      OUT=$OUT LABEL=$(echo "$m" | tr ':/' '__') "$here/cron_test.sh"
  done
fi
echo "done: $OUT"
