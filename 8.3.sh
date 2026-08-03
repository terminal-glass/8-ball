#!/usr/bin/env bash
# 8-BALL MOTD, remember helper, and local status presentation.
set -euo pipefail

VERSION="8.3 motd 1.0.0"
LOG_FILE="/opt/philosopher/trial-log.txt"
RESULT_FILE="/opt/philosopher/8ball-result.txt"
REMEMBER_HELPER="/usr/local/bin/remember"
MOTD_HELPER="/etc/update-motd.d/98-8ball"

log() {
  local message="$1"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$message" >>"$LOG_FILE"
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "8.3 must run as root"
}

install_remember_helper() {
  cat >"$REMEMBER_HELPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

RESULT_FILE="/opt/philosopher/8ball-result.txt"

cat <<'TEXT'
8-BALL persistent chat upgrade

The public 8-BALL trial installs local AI on your machine.
A future persistent chat upgrade can add a richer always-on experience.

This helper does not activate paid features.
It only explains how to request the upgrade.

Contact:
  8ball@terminal.glass

When you email support, include:
  cat /opt/philosopher/8ball-result.txt

That result file helps us understand your hardware and selected model.
TEXT

if [[ -f "$RESULT_FILE" ]]; then
  echo
  echo "Current result file:"
  cat "$RESULT_FILE"
fi
EOF
  chmod 0755 "$REMEMBER_HELPER"
}

install_motd_helper() {
  install -d -m 0755 /etc/update-motd.d
  cat >"$MOTD_HELPER" <<'EOF'
#!/bin/sh
# 8-BALL public trial MOTD (no network calls, no inference).
RESULT_FILE="/opt/philosopher/8ball-result.txt"

model="none"
profile="none"
tier="none"
model_test="UNKNOWN"
jets_status="UNKNOWN"
ram_mb="?"
cpu_threads="?"
free_disk_mb="?"
gpu="none"
gpu_vram_mb="0"

if [ -f "$RESULT_FILE" ]; then
  model="$(awk -F': ' '/^Model:/ {print $2; exit}' "$RESULT_FILE")"
  profile="$(awk -F': ' '/^Profile:/ {print $2; exit}' "$RESULT_FILE")"
  tier="$(awk -F': ' '/^Tier:/ {print $2; exit}' "$RESULT_FILE")"
  model_test="$(awk -F': ' '/^Model test:/ {print $2; exit}' "$RESULT_FILE")"
  jets_status="$(awk -F': ' '/^Jets status:/ {print $2; exit}' "$RESULT_FILE")"
  ram_mb="$(awk -F': ' '/^RAM MB:/ {print $2; exit}' "$RESULT_FILE")"
  cpu_threads="$(awk -F': ' '/^CPU threads:/ {print $2; exit}' "$RESULT_FILE")"
  free_disk_mb="$(awk -F': ' '/^Free disk MB:/ {print $2; exit}' "$RESULT_FILE")"
  gpu="$(awk -F': ' '/^GPU:/ {print $2; exit}' "$RESULT_FILE")"
  gpu_vram_mb="$(awk -F': ' '/^GPU VRAM MB:/ {print $2; exit}' "$RESULT_FILE")"
fi

ollama_status="STOPPED"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ollama 2>/dev/null; then
  ollama_status="RUNNING"
elif pgrep -x ollama >/dev/null 2>&1; then
  ollama_status="RUNNING"
fi

local_model_status="NOT READY"
if [ "$model_test" = "PASSED" ] && [ -n "$model" ] && [ "$model" != "none" ]; then
  local_model_status="READY"
fi

cat <<BANNER

terminal.glass
😎 Private AI with no more guesswork 😎

SYSTEM STATUS
Ollama ............. ${ollama_status}
Local Model ........ ${local_model_status}
8-BALL JETS ........ ${jets_status}

Local:    ollama run ${model}
Status:   cat /opt/philosopher/8ball-result.txt
Upgrade:  sudo remember
BANNER

if [ "$ollama_status" != "RUNNING" ]; then
  echo "ERROR: Ollama is not responding."
  echo "Run: sudo systemctl restart ollama"
fi

if [ "$free_disk_mb" != "?" ] && [ "$free_disk_mb" -lt 8192 ] 2>/dev/null; then
  echo "NOTICE: Only ${free_disk_mb} MB of disk remains; future models may not fit."
  echo "Review: ollama list | Remove: ollama rm <model>"
fi
EOF
  chmod 0755 "$MOTD_HELPER"
}

main() {
  require_root
  log "Starting ${VERSION}"
  install_remember_helper
  install_motd_helper
  log "Completed ${VERSION}"
  echo "8.3 complete: MOTD and remember helper installed."
  echo "Try: sudo remember"
}

main "$@"
