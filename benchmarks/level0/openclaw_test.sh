#!/usr/bin/env bash
# OpenClaw on a level-0 machine, cloud model only, no Ollama running.
# Runs ON the target. Installs Node 24 and OpenClaw if missing (needs sudo),
# configures a loopback gateway whose only model is the hosted Meta provider,
# measures gateway RAM, tries one consultation turn, and runs the cron probe
# next to the gateway. No API key is used or needed to run this test; with no
# key the consultation turn is expected to fail with a missing-credential error.
#
#   LABEL=vm-x86-2c-2g STOP_OLLAMA=1 CRON_MINUTES=5 ./openclaw_test.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
LABEL=${LABEL:?} OC_VERSION=${OC_VERSION:-2026.11.3} NODE_MAJOR=${NODE_MAJOR:-24}
CRON_MINUTES=${CRON_MINUTES:-5} SAMPLE_S=${SAMPLE_S:-180} PORT=${PORT:-18789}
OUT=$here/results/$LABEL; mkdir -p "$OUT"; R=$OUT/openclaw.json
# Stop Ollama first (frees any loaded model before the npm install, which needs
# several hundred MB on a 2 GB machine).
ollama_was=$(systemctl is-active ollama 2>/dev/null || echo absent)
[ "${STOP_OLLAMA:-1}" = 1 ] && [ "$ollama_was" = active ] && sudo systemctl stop ollama
arch=$(uname -m); case $arch in x86_64) na=x64;; aarch64|arm64) na=arm64;; *) na=$arch;; esac
if ! node -v 2>/dev/null | grep -q "^v$NODE_MAJOR\."; then
  ver=$(curl -fsSL https://nodejs.org/dist/latest-v$NODE_MAJOR.x/SHASUMS256.txt | grep -o "node-v[0-9.]*-linux-$na.tar.xz" | head -1)
  curl -fsSLO "https://nodejs.org/dist/latest-v$NODE_MAJOR.x/$ver"
  curl -fsSL "https://nodejs.org/dist/latest-v$NODE_MAJOR.x/SHASUMS256.txt" | grep " $ver\$" | sha256sum -c -
  sudo tar -xJf "$ver" -C /usr/local --strip-components=1 && rm -f "$ver"
fi
command -v openclaw >/dev/null || sudo npm install -g --no-fund --no-audit "openclaw@$OC_VERSION" >/dev/null 2>&1
openclaw plugins list 2>/dev/null | grep -q meta || openclaw plugins install @openclaw/meta-provider >/dev/null 2>&1
mkdir -p ~/.openclaw && chmod 700 ~/.openclaw
python3 - "$PORT" <<'PY'
import json, os, secrets, sys
p = os.path.expanduser("~/.openclaw/openclaw.json")
c = json.load(open(p)) if os.path.exists(p) else {}
c.setdefault("gateway", {}).update({"mode": "local", "bind": "loopback", "port": int(sys.argv[1])})
c["gateway"].setdefault("auth", {"mode": "token", "token": secrets.token_hex(24)})
c["tools"] = {"profile": "minimal", "exec": {"mode": "allowlist"}, "deny": ["*"]}
c["skills"] = {"limits": {"maxSkillsInPrompt": 0}}
c.setdefault("agents", {}).setdefault("defaults", {}).update({
    "workspace": os.path.expanduser("~/.openclaw/workspace"), "model": {"primary": "meta/muse-spark-1.3"},
    "skipBootstrap": True, "timeoutSeconds": 300})
c.setdefault("models", {})["mode"] = "merge"; c["models"].pop("providers", None)
c["memory"] = {"search": {"enabled": False}}
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f: json.dump(c, f, indent=2)
PY
openclaw config validate >/dev/null 2>&1 && cfg_ok=true || cfg_ok=false
avail_before=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
t0=$(date +%s.%N)
nohup env -u MODEL_API_KEY openclaw gateway --port "$PORT" > "$OUT/.gateway.log" 2>&1 &
GPID=$!
ready=null
for i in $(seq 600); do
  if grep -q '\[gateway\] ready' "$OUT/.gateway.log" 2>/dev/null; then ready=$(python3 -c "import time;print(round(time.time()-$t0,1))"); break; fi; sleep 1; done
peak=0; samples=()
end=$(( $(date +%s) + SAMPLE_S ))
while [ "$(date +%s)" -lt "$end" ]; do
  kb=0; for p in $(pgrep -f "openclaw"); do [ "$(cat /proc/$p/comm 2>/dev/null)" = bash ] && continue; v=$(awk '/VmRSS/{print $2}' /proc/$p/status 2>/dev/null); kb=$((kb + ${v:-0})); done
  [ "$kb" -gt "$peak" ] && peak=$kb; samples+=("$kb"); sleep 5; done
idle_kb=${samples[-1]:-0}
avail_gw=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
c0=$(date +%s.%N)
env -u MODEL_API_KEY timeout 300 openclaw agent --agent main --timeout 120 \
  -m "Installer consultation: this machine has $(nproc) CPU cores and $(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024 )) MiB RAM. What should run locally?" \
  > "$OUT/.consult.log" 2>&1; consult_rc=$?
consult_s=$(python3 -c "import time;print(round(time.time()-$c0,1))")
consult_err=$(grep -v -i deprecat "$OUT/.consult.log" | grep -oE 'No API key found for provider "[a-z]+"|ProviderAuthError|[A-Za-z]+Error' | head -1)
cron_json=null
if [ "$CRON_MINUTES" -gt 0 ] && command -v crontab >/dev/null; then
  MODEL=none MINUTES=$CRON_MINUTES OUT=$OUT LABEL=openclaw-gateway-only "$here/cron_test.sh" > /dev/null
  cron_json=$(cat "$OUT/cron-openclaw-gateway-only.json")
fi
kb=0; for p in $(pgrep -f "openclaw"); do [ "$(cat /proc/$p/comm 2>/dev/null)" = bash ] && continue; v=$(awk '/VmRSS/{print $2}' /proc/$p/status 2>/dev/null); kb=$((kb + ${v:-0})); done
[ "$kb" -gt "$peak" ] && peak=$kb
kill "$GPID" 2>/dev/null; sleep 3; pkill -f "openclaw gateway" 2>/dev/null
[ "$ollama_was" = active ] && sudo systemctl start ollama
export R_LABEL=$LABEL R_OC="$(openclaw --version 2>/dev/null | head -1)" R_NODE="$(node -v)" R_ARCH=$arch \
  R_CFG=$cfg_ok R_STOP=${STOP_OLLAMA:-1} R_OLL=$ollama_was R_AB=$avail_before R_AG=$avail_gw R_READY=$ready \
  R_IDLE=$idle_kb R_PEAK=$peak R_CRC=$consult_rc R_CS=$consult_s R_CERR="$consult_err" R_CRON="$cron_json"
python3 - <<'PY' > "$R"
import json, os
e = os.environ
print(json.dumps({"label": e["R_LABEL"], "openclaw": e["R_OC"], "node": e["R_NODE"], "arch": e["R_ARCH"],
  "config_valid": e["R_CFG"] == "true", "model": "meta/muse-spark-1.3 (hosted, no key)",
  "ollama_running_during_test": not (e["R_STOP"] == "1") and e["R_OLL"] == "active",
  "mem_available_mb_before": int(e["R_AB"]), "mem_available_mb_with_gateway": int(e["R_AG"]),
  "gateway_ready_s": None if e["R_READY"] == "null" else float(e["R_READY"]),
  "gateway_rss_mb_idle": round(int(e["R_IDLE"]) / 1024, 1), "gateway_rss_mb_peak": round(int(e["R_PEAK"]) / 1024, 1),
  "consult_exit": int(e["R_CRC"]), "consult_s": float(e["R_CS"]), "consult_error": e["R_CERR"],
  "cron": None if e["R_CRON"] == "null" else json.loads(e["R_CRON"])}, indent=1))
PY
cat "$R"

# Phase 2 (optional): OpenClaw consultation on the local canary through Ollama.
# LOCAL_MODEL=tinyllama:1.1b  (no API key needed; Ollama must be installed)
if [ -n "${LOCAL_MODEL:-}" ] && command -v ollama >/dev/null; then
  sudo systemctl start ollama; for i in $(seq 60); do curl -fs http://127.0.0.1:11434/api/version >/dev/null && break; sleep 1; done
  cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.cloud-only
  python3 - "$LOCAL_MODEL" <<'PY'
import json, os, sys
m = sys.argv[1]; p = os.path.expanduser("~/.openclaw/openclaw.json"); c = json.load(open(p))
c["agents"]["defaults"]["model"] = {"primary": f"ollama/{m}"}
c["models"]["providers"] = {"ollama": {"baseUrl": "http://127.0.0.1:11434", "api": "ollama", "apiKey": "ollama-local",
  "timeoutSeconds": 900, "models": [{"id": m, "name": m, "contextWindow": 2048, "contextTokens": 2048,
  "compat": {"supportsTools": False}, "params": {"num_ctx": 2048}}]}}
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f: json.dump(c, f, indent=2)
PY
  oom0=$(sudo dmesg | grep -c "Out of memory")
  nohup openclaw gateway --port "$PORT" > "$OUT/.gateway-local.log" 2>&1 & GPID=$!
  for i in $(seq 600); do grep -q '\[gateway\] ready' "$OUT/.gateway-local.log" 2>/dev/null && break; sleep 1; done
  ( peak=0; while kill -0 $GPID 2>/dev/null; do t=$(free -k | awk '/Mem:/{print $3}'); [ "$t" -gt "$peak" ] && echo "$t" > "$OUT/.used-peak"; [ "$t" -gt "$peak" ] && peak=$t; sleep 1; done ) &
  c0=$(date +%s.%N)
  timeout 900 openclaw agent --agent main --timeout 840 \
    -m "Installer consultation: this machine has $(nproc) CPU cores and $(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024 )) MiB RAM. In three short bullets, what should run locally?" \
    > "$OUT/.consult-local.log" 2>&1; lrc=$?
  ls=$(python3 -c "import time;print(round(time.time()-$c0,1))")
  oom1=$(sudo dmesg | grep -c "Out of memory")
  kill $GPID 2>/dev/null; sleep 3; pkill -f "openclaw gateway" 2>/dev/null
  cp ~/.openclaw/openclaw.json.cloud-only ~/.openclaw/openclaw.json
  export L_OUT=$OUT L_MODEL=$LOCAL_MODEL L_RC=$lrc L_S=$ls L_OOM=$((oom1 - oom0))
  python3 - "$R" <<'PY'
import json, os, sys
e = os.environ
r = json.load(open(sys.argv[1]))
txt = [l for l in open(e["L_OUT"] + "/.consult-local.log") if "eprecat" not in l and l.strip()]
r["local_consult"] = {"model": "ollama/" + e["L_MODEL"], "num_ctx": 2048, "exit": int(e["L_RC"]), "wall_s": float(e["L_S"]),
  "system_used_mb_peak": round(int(open(e["L_OUT"] + "/.used-peak").read()) / 1024), "new_oom_kills": int(e["L_OOM"]),
  "reply_head": "".join(txt)[-400:].replace(__import__("os").path.expanduser("~"), "~")}
json.dump(r, open(sys.argv[1], "w"), indent=1); print(json.dumps(r["local_consult"], indent=1))
PY
fi
