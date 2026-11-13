#!/usr/bin/env bash
# Cron reliability under model load.
# Installs a temporary every-minute crontab entry for the current user that
# appends a timestamp, keeps the local model generating non-stop for
# MINUTES minutes, then removes the entry and reports missed/late runs.
#
#   OLLAMA_HOST=127.0.0.1:11434 MODEL=llama3.2:1b MINUTES=10 NUM_THREAD=2 ./cron_test.sh
#   MODEL=none skips the model load (e.g. to test cron next to OpenClaw only).
set -euo pipefail
HOST=${OLLAMA_HOST:-127.0.0.1:11434} MODEL=${MODEL:-llama3.2:1b} MINUTES=${MINUTES:-10}
NUM_THREAD=${NUM_THREAD:-$(nproc)} LATE_S=${LATE_S:-5} OUT=${OUT:-results} LABEL=${LABEL:-cron}
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
PROBE=$OUT/.cron-probe-$LABEL.log; : > "$PROBE"
TAG="# l0-cron-probe"
pgrep -x cron >/dev/null || pgrep -x crond >/dev/null || { echo "cron daemon not running" >&2; exit 2; }
old=$(crontab -l 2>/dev/null | grep -v "$TAG" || true)
restore() { printf '%s\n' "$old" | grep -v '^$' | crontab - 2>/dev/null || crontab -r 2>/dev/null || true; }
trap 'restore; kill ${LOADPID:-0} 2>/dev/null || true' EXIT
{ printf '%s\n' "$old" | grep -v '^$' || true
  echo "* * * * * date +\%s.\%N >> $PROBE $TAG"; } | crontab -
# start on a minute boundary so every expected minute is counted
sleep $(( 61 - $(date +%-S) ))
start=$(date +%s)
if [ "$MODEL" = none ]; then : > "$OUT/.cron-load-$LABEL.log"; sleep 1 & else
( while :; do
    curl -s "http://$HOST/api/generate" -d "{\"model\":\"$MODEL\",\"prompt\":\"Write a long, detailed installation guide for a home AI server.\",\"stream\":false,\"keep_alive\":\"10m\",\"options\":{\"num_predict\":512,\"num_thread\":$NUM_THREAD,\"num_ctx\":4096}}" \
      | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin); print("gen", d.get("eval_count"), round(d["eval_count"]/(d["eval_duration"]/1e9),2), flush=True)
except Exception as e: print("generr", e, flush=True)'
  done ) > "$OUT/.cron-load-$LABEL.log" 2>&1 &
fi
LOADPID=$!
sleep $(( MINUTES * 60 + 20 ))
kill $LOADPID 2>/dev/null || true; pkill -P $LOADPID 2>/dev/null || true
end=$(date +%s); restore
python3 - "$PROBE" "$start" "$MINUTES" "$LATE_S" "$OUT/.cron-load-$LABEL.log" "$LABEL" "$MODEL" <<'PY' | tee "$OUT/cron-$LABEL.json"
import json, sys, statistics
probe, start, minutes, late_s, loadlog, label, model = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), sys.argv[5], sys.argv[6], sys.argv[7]
ts = [float(l) for l in open(probe) if l.strip()]
first = start - start % 60
expected = [first + 60 * i for i in range(minutes)]
lat, missed = [], 0
for m in expected:
    hits = [t - m for t in ts if m <= t < m + 60]
    if hits: lat.append(min(hits))
    else: missed += 1
gens = [l.split() for l in open(loadlog) if l.startswith("gen ")]
rates = [float(g[2]) for g in gens if len(g) == 3]
print(json.dumps({"label": label, "load_model": model, "minutes": minutes, "expected_runs": len(expected),
  "fired": len(lat), "missed": missed, "late_over_s": late_s, "late": sum(1 for x in lat if x > late_s),
  "lateness_s_min": round(min(lat), 3) if lat else None, "lateness_s_median": round(statistics.median(lat), 3) if lat else None,
  "lateness_s_max": round(max(lat), 3) if lat else None, "load_generations": len(gens),
  "load_eval_tok_s_median": round(statistics.median(rates), 2) if rates else None}))
PY
rm -f "$PROBE"
