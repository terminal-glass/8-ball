#!/usr/bin/env bash
# 8.3 — public 8-BALL login MOTD and remember helper (no network calls on login).
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_SCRIPT_VERSION="0.8.0"
EIGHTBALL_INSTALL_PROFILE="ubuntu"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_DIR="${SCRIPT_DIR}/../shared"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
MOTD_TEMPLATE="${SCRIPT_DIR}/assets/first-MOTD.txt"
MOTD_TARGET="/etc/update-motd.d/99-8ball-trial"
ALERT_META="${PHILOSOPHER_ROOT}/8ball-temp-alert.meta"
ALERT_TEXT="${PHILOSOPHER_ROOT}/8ball-temp-alert.txt"
ALERT_HISTORY="${PHILOSOPHER_ROOT}/8ball-alert-history"
BULLETIN_FILE="${PHILOSOPHER_ROOT}/8ball-bulletin.txt"
TRIAL_MARKER="${PHILOSOPHER_ROOT}/trial-installed"
RESULT_FILE="${PHILOSOPHER_ROOT}/8ball-result.txt"
LOG_FILE="${PHILOSOPHER_ROOT}/8ball-trial.log"

# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-version.sh"
# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-model-test.sh"

log() {
  printf '[8.3] %s\n' "$*"
}

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "8.3 requires root. Re-run with sudo." >&2
    exit 1
  fi
}

ensure_state_permissions() {
  install -d -m 0755 "${PHILOSOPHER_ROOT}"
  touch "${LOG_FILE}" "${RESULT_FILE}"
  chmod 0644 "${LOG_FILE}" "${RESULT_FILE}"
  : >"${ALERT_HISTORY}"
  chmod 0640 "${ALERT_HISTORY}"
  chown root:adm "${ALERT_HISTORY}" 2>/dev/null || chmod 0640 "${ALERT_HISTORY}"
  if [[ -f "${ALERT_META}" ]]; then
    chmod 0640 "${ALERT_META}"
    chown root:adm "${ALERT_META}" 2>/dev/null || true
  fi
  if [[ -f "${ALERT_TEXT}" ]]; then
    chmod 0644 "${ALERT_TEXT}"
  fi
  if [[ -f "${BULLETIN_FILE}" ]]; then
    chmod 0644 "${BULLETIN_FILE}"
  fi
  if [[ -f "${TRIAL_MARKER}" ]]; then
    chmod 0644 "${TRIAL_MARKER}"
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

refresh_bulletin_if_available() {
  local bulletin_url="${EIGHTBALL_BULLETIN_URL:-}"
  if [[ -z "${bulletin_url}" ]]; then
    if [[ ! -f "${BULLETIN_FILE}" ]]; then
      cat >"${BULLETIN_FILE}" <<'EOF'
8-BALL trial bulletin unavailable offline.
Check https://terminal.glass for updates.
EOF
      chmod 0644 "${BULLETIN_FILE}"
    fi
    return 0
  fi
  if curl -fsS --max-time 5 "${bulletin_url}" -o "${BULLETIN_FILE}.tmp" 2>/dev/null; then
    mv "${BULLETIN_FILE}.tmp" "${BULLETIN_FILE}"
    chmod 0644 "${BULLETIN_FILE}"
    log "Bulletin refreshed during install"
  else
    rm -f "${BULLETIN_FILE}.tmp"
    log "Bulletin refresh skipped (network unavailable)"
  fi
}

seed_temp_alert() {
  local message="${EIGHTBALL_TEMP_ALERT:-Welcome to the 8-BALL trial. Run: ollama run <model>}"
  local logins="${EIGHTBALL_TEMP_ALERT_LOGINS:-3}"
  cat >"${ALERT_TEXT}" <<EOF
${message}
EOF
  chmod 0644 "${ALERT_TEXT}"
  printf '%s\n' "${logins}" >"${ALERT_META}"
  chmod 0640 "${ALERT_META}"
  chown root:adm "${ALERT_META}" 2>/dev/null || true
}

write_trial_marker() {
  cat >"${TRIAL_MARKER}" <<EOF
suite_version=${EIGHTBALL_SUITE_VERSION}
script_family=${EIGHTBALL_SCRIPT_FAMILY}
installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
install_profile=${EIGHTBALL_INSTALL_PROFILE}
install_lane=${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE}}
EOF
  chmod 0644 "${TRIAL_MARKER}"
}

install_motd() {
  if [[ ! -f "${MOTD_TEMPLATE}" ]]; then
    echo "Missing MOTD template: ${MOTD_TEMPLATE}" >&2
    exit 1
  fi
  install -d -m 0755 /etc/update-motd.d
  cat >"${MOTD_TARGET}" <<'MOTDEOF'
#!/usr/bin/env bash
set -euo pipefail
RESULT_FILE="/opt/philosopher/8ball-result.txt"
TEMPLATE_FILE="__TEMPLATE_FILE__"
ALERT_META="/opt/philosopher/8ball-temp-alert.meta"
ALERT_TEXT="/opt/philosopher/8ball-temp-alert.txt"
ALERT_HISTORY="/opt/philosopher/8ball-alert-history"
ollama_status="STOPPED"
model_status="UNKNOWN"
selected_model="unknown"

motd_model_installed() {
  local model="$1"
  local listed base tag
  [[ -n "${model}" && "${model}" != "unknown" ]] || return 1
  while IFS= read -r listed; do
    [[ -z "${listed}" ]] && continue
    if [[ "${listed}" == "${model}" || "${listed}" == "${model}"* ]]; then
      return 0
    fi
    base="${model%%:*}"
    tag="${model#*:}"
    if [[ "${tag}" != "${model}" && "${listed}" == "${base}" ]]; then
      return 0
    fi
    if [[ "${listed}" == "${base}:${tag}"* ]]; then
      return 0
    fi
  done < <(ollama list 2>/dev/null | awk 'NR>1 {print $1}')
  return 1
}

if systemctl is-active --quiet ollama 2>/dev/null || curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  ollama_status="RUNNING"
fi
if [[ -f "${RESULT_FILE}" ]]; then
  selected_model="$(awk -F': ' '$1 == "Model" {print $2; exit}' "${RESULT_FILE}")"
fi
if [[ "${ollama_status}" == "RUNNING" && -n "${selected_model}" && "${selected_model}" != "unknown" ]]; then
  if motd_model_installed "${selected_model}"; then
    model_status="READY"
  else
    model_status="MISSING"
  fi
fi

if [[ -f "${ALERT_META}" && -f "${ALERT_TEXT}" ]]; then
  remaining="$(tr -d '[:space:]' < "${ALERT_META}" 2>/dev/null || echo 0)"
  if [[ "${remaining}" =~ ^[0-9]+$ ]] && [[ "${remaining}" -gt 0 ]]; then
    cat "${ALERT_TEXT}"
    remaining=$((remaining - 1))
    if [[ -w "${ALERT_META}" ]]; then
      printf '%s\n' "${remaining}" >"${ALERT_META}"
    elif command -v runuser >/dev/null 2>&1; then
      runuser -u root -- sh -c "printf '%s\n' '${remaining}' > '${ALERT_META}'" 2>/dev/null || true
    fi
    if [[ "${remaining}" -le 0 ]]; then
      date -u +%Y-%m-%dT%H:%M:%SZ >>"${ALERT_HISTORY}" 2>/dev/null || true
    fi
    echo
  fi
fi

sed \
  -e "s/__OLLAMA_STATUS__/${ollama_status}/g" \
  -e "s/__MODEL_STATUS__/${model_status}/g" \
  -e "s/__SELECTED_MODEL__/${selected_model}/g" \
  "${TEMPLATE_FILE}"
MOTDEOF
  sed -i "s|__TEMPLATE_FILE__|${MOTD_TEMPLATE}|g" "${MOTD_TARGET}"
  chmod 0755 "${MOTD_TARGET}"
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<EOF
Usage: 8.3.sh [options]

Suite: ${EIGHTBALL_SCRIPT_FAMILY} ${EIGHTBALL_SUITE_VERSION}
Lane: ${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE}}

Options:
  --no-motd     Install helpers and state only
  -h, --help    Show this help without mutating the host
EOF
    exit 0
  fi
  local skip_motd=0
  if [[ "${1:-}" == "--no-motd" ]]; then
    skip_motd=1
  fi
  require_root
  eightball_verify_script_version "${BASH_SOURCE[0]}" "8.3.sh"
  ensure_state_permissions
  install_remember_helper
  refresh_bulletin_if_available
  seed_temp_alert
  write_trial_marker
  if [[ "${skip_motd}" -eq 0 ]]; then
    install_motd
    log "Installed MOTD at ${MOTD_TARGET}"
  fi
  log "Installed remember helper at /usr/local/bin/remember"
  log "Login MOTD performs no network calls"
}

main "$@"
