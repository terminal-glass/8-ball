#!/usr/bin/env bash
# 8.3 — public 8-BALL login MOTD and remember helper (no network calls on login).
# Install profile: digitalocean-droplet
set -euo pipefail

EIGHTBALL_INSTALL_LANE="cloud/digitalocean/cpu-droplet"
EIGHTBALL_PROVIDER_ASSUMPTION="profiles/provider-assumptions/cloud-digitalocean-cpu-droplet.json"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
MOTD_TEMPLATE="${SCRIPT_DIR}/assets/first-MOTD.txt"
MOTD_TARGET="/etc/update-motd.d/99-8ball-trial"

log() {
  printf '[8.3] %s\n' "$*"
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "8.3 requires root. Re-run with sudo." >&2
    exit 1
  fi
}

install_remember_helper() {
  cat >/usr/local/bin/remember <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cat <<EOM
8-BALL persistent chat upgrades are handled outside this public catalog repository.

Email: 8ball@terminal.glass
Include: cat /opt/philosopher/8ball-result.txt

This helper does not activate paid features, Passport, or commercial bundles.
EOM
EOF
  chmod 0755 /usr/local/bin/remember
}

install_motd() {
  if [[ ! -f "${MOTD_TEMPLATE}" ]]; then
    echo "Missing MOTD template: ${MOTD_TEMPLATE}" >&2
    exit 1
  fi
  install -d -m 0755 /etc/update-motd.d
  cat >"${MOTD_TARGET}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
RESULT_FILE="/opt/philosopher/8ball-result.txt"
TEMPLATE_FILE="__TEMPLATE_FILE__"
ollama_status="STOPPED"
model_status="UNKNOWN"
selected_model="unknown"
if systemctl is-active --quiet ollama 2>/dev/null || curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  ollama_status="RUNNING"
fi
if [[ -f "${RESULT_FILE}" ]]; then
  selected_model="$(awk -F': ' '$1 == "Model" {print $2}' "${RESULT_FILE}")"
  if awk -F': ' '$1 == "Model test" && $2 == "PASSED"' "${RESULT_FILE}" >/dev/null; then
    model_status="READY"
  fi
fi
sed \
  -e "s/__OLLAMA_STATUS__/${ollama_status}/g" \
  -e "s/__MODEL_STATUS__/${model_status}/g" \
  -e "s/__SELECTED_MODEL__/${selected_model}/g" \
  "${TEMPLATE_FILE}"
EOF
  sed -i "s|__TEMPLATE_FILE__|${MOTD_TEMPLATE}|g" "${MOTD_TARGET}"
  chmod 0755 "${MOTD_TARGET}"
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<'EOF'
Usage: 8.3.sh [options]

Lane: cloud/digitalocean/cpu-droplet

Options:
  -h, --help    Show this help without mutating the host
EOF
    exit 0
  fi
  require_root
  install_remember_helper
  install_motd
  log "Installed MOTD at ${MOTD_TARGET}"
  log "Installed remember helper at /usr/local/bin/remember"
  log "Login MOTD performs no network calls"
}

main "$@"
