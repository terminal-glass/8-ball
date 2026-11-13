#!/usr/bin/env bash
# One command per target host. Copies the scripts over ssh, runs run_host.sh
# there, and copies the results back to results/<LABEL>/ here.
#
#   SSH="ssh -o ... user@target" LABEL=vm-arm64-2g ./run_remote.sh
#
# SSH is the full ssh command for the target (jump hosts, keys, etc. are the
# caller's business and are never written into results). Extra env vars
# (MODELS, RUNS, CRON_MINUTES, NUM_THREAD) are passed through.
set -euo pipefail
: "${SSH:?set SSH to the ssh command for the target}" "${LABEL:?}"
here=$(cd "$(dirname "$0")" && pwd)
pass=""; for v in LABEL MODELS RUNS NUM_CTX NUM_THREAD CRON_MINUTES CRON_MODELS INSTALL_OLLAMA; do
  [ -n "${!v:-}" ] && pass+="$v='${!v}' "; done
tar -C "$here" -cf - l0_bench.py cron_test.sh run_host.sh | $SSH 'mkdir -p ~/l0bench && tar -xf - -C ~/l0bench'
$SSH "cd ~/l0bench && $pass bash run_host.sh"
mkdir -p "$here/results/$LABEL"
$SSH "tar -C ~/l0bench/results/$LABEL -cf - --exclude='./.*' ." | tar -xf - -C "$here/results/$LABEL"
echo "results in results/$LABEL"
