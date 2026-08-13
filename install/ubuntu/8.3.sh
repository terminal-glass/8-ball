#!/usr/bin/env bash
# 8.3 — public 8-BALL login MOTD and remember helper (no network calls on login).
# Install profile: ubuntu
set -euo pipefail

EIGHTBALL_SCRIPT_VERSION="0.8.0"
EIGHTBALL_INSTALL_PROFILE="ubuntu"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_DIR="${SCRIPT_DIR}/../shared"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
PHILOSOPHER_BIN="${PHILOSOPHER_ROOT}/bin"
MOTD_TEMPLATE="${SCRIPT_DIR}/assets/first-MOTD.txt"
MOTD_TARGET="${EIGHTBALL_MOTD_TARGET:-/etc/update-motd.d/99-8ball-trial}"
ALERT_META="${PHILOSOPHER_ROOT}/8ball-temp-alert.meta"
ALERT_TEXT="${PHILOSOPHER_ROOT}/8ball-temp-alert.txt"
ALERT_HISTORY="${PHILOSOPHER_ROOT}/8ball-alert-history"
BULLETIN_FILE="${PHILOSOPHER_ROOT}/8ball-bulletin.txt"
TRIAL_MARKER="${PHILOSOPHER_ROOT}/trial-installed"
RESULT_FILE="${PHILOSOPHER_ROOT}/8ball-result.txt"
RESULT_JSON="${PHILOSOPHER_ROOT}/8ball-result.json"
LOG_FILE="${PHILOSOPHER_ROOT}/8ball-trial.log"
STATUS_SCRIPT="${SHARED_DIR}/8ball-client-status.py"
BULLETIN_REFRESH="${SHARED_DIR}/8ball-bulletin-refresh.sh"
SYSTEMD_DIR="/etc/systemd/system"

# shellcheck source=/dev/null
source "${SHARED_DIR}/8ball-version.sh"

log() {
  printf '[8.3] %s\n' "$*"
}

require_root() {
  if [[ "${EIGHTBALL_TEST_SKIP_ROOT:-0}" == "1" ]]; then
    return 0
  fi
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "8.3 requires root. Re-run with sudo." >&2
    exit 1
  fi
}

ensure_state_permissions() {
  install -d -m 0755 "${PHILOSOPHER_ROOT}" "${PHILOSOPHER_BIN}"
  touch "${LOG_FILE}"
  chmod 0644 "${LOG_FILE}"
  if [[ -f "${RESULT_FILE}" ]]; then
    chmod 0644 "${RESULT_FILE}"
  fi
  if [[ -f "${RESULT_JSON}" ]]; then
    chmod 0644 "${RESULT_JSON}"
  fi
  if [[ ! -f "${ALERT_HISTORY}" ]]; then
    : >"${ALERT_HISTORY}"
  fi
  chmod 0640 "${ALERT_HISTORY}"
  chown root:adm "${ALERT_HISTORY}" 2>/dev/null || true
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
  local target="${EIGHTBALL_BIN_DIR:-/usr/local/bin}/remember"
  install -d -m 0755 "$(dirname "${target}")"
  cat >"${target}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cat <<EOM
8-BALL persistent chat upgrades are handled outside this public catalog repository.

Email: 8ball@terminal.glass
Include: cat ${RESULT_FILE}

This helper does not activate paid features, Passport, or commercial bundles.
EOM
EOF
  chmod 0755 "${target}"
}

install_status_helpers() {
  install -m 0755 "${STATUS_SCRIPT}" "${PHILOSOPHER_BIN}/8ball-client-status.py"
  install -m 0755 "${BULLETIN_REFRESH}" "${PHILOSOPHER_BIN}/8ball-bulletin-refresh.sh"
}

seed_offline_bulletin() {
  if [[ ! -f "${BULLETIN_FILE}" ]]; then
    cat >"${BULLETIN_FILE}" <<'EOF'
8-BALL trial bulletin unavailable offline.
Check https://terminal.glass for updates.
EOF
    chmod 0644 "${BULLETIN_FILE}"
  fi
}

install_bulletin_timer() {
  if [[ "${EIGHTBALL_TEST_SKIP_ROOT:-0}" == "1" ]]; then
    return 0
  fi
  if [[ ! -d "${SYSTEMD_DIR}" ]]; then
    log "systemd not present; skipping bulletin timer installation"
    return 0
  fi
  install -m 0644 "${SHARED_DIR}/systemd/8ball-bulletin-refresh.service" \
    "${SYSTEMD_DIR}/8ball-bulletin-refresh.service"
  install -m 0644 "${SHARED_DIR}/systemd/8ball-bulletin-refresh.timer" \
    "${SYSTEMD_DIR}/8ball-bulletin-refresh.timer"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    systemctl enable --now 8ball-bulletin-refresh.timer >/dev/null 2>&1 || true
  fi
}

seed_temp_alert() {
  if [[ -f "${ALERT_META}" && -f "${ALERT_TEXT}" ]]; then
    return 0
  fi
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
  install -d -m 0755 "$(dirname "${MOTD_TARGET}")"
  cat >"${MOTD_TARGET}" <<MOTDEOF
#!/usr/bin/env bash
# 8-BALL login MOTD — lightweight local status only (no pulls, no inference).
set -euo pipefail
export PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT}"
export OLLAMA_API="\${OLLAMA_API:-http://127.0.0.1:11434}"
STATUS_SCRIPT="${PHILOSOPHER_BIN}/8ball-client-status.py"
TEMPLATE_FILE="${MOTD_TEMPLATE}"
BULLETIN_FILE="${BULLETIN_FILE}"

if [[ ! -x "\${STATUS_SCRIPT}" ]]; then
  echo "8-BALL status helper missing: \${STATUS_SCRIPT}"
  exit 0
fi

python3 "\${STATUS_SCRIPT}" render-motd "\${TEMPLATE_FILE}"

if [[ -f "\${BULLETIN_FILE}" ]]; then
  echo
  cat "\${BULLETIN_FILE}"
fi
MOTDEOF
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
  install_status_helpers
  install_remember_helper
  seed_offline_bulletin
  install_bulletin_timer
  seed_temp_alert
  write_trial_marker
  if [[ "${skip_motd}" -eq 0 ]]; then
    install_motd
    log "Installed MOTD at ${MOTD_TARGET}"
  fi
  log "Installed remember helper at ${EIGHTBALL_BIN_DIR:-/usr/local/bin}/remember"
  log "Login MOTD performs no network calls"
}

main "$@"
