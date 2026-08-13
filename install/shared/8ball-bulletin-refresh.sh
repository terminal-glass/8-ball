#!/usr/bin/env bash
# Refresh cached 8-BALL bulletin text (async; not used at login).
set -euo pipefail

PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
BULLETIN_FILE="${PHILOSOPHER_ROOT}/8ball-bulletin.txt"
BULLETIN_URL="${EIGHTBALL_BULLETIN_URL:-}"

install -d -m 0755 "${PHILOSOPHER_ROOT}"

if [[ -z "${BULLETIN_URL}" ]]; then
  if [[ ! -f "${BULLETIN_FILE}" ]]; then
    cat >"${BULLETIN_FILE}" <<'EOF'
8-BALL trial bulletin unavailable offline.
Check https://terminal.glass for updates.
EOF
    chmod 0644 "${BULLETIN_FILE}"
  fi
  exit 0
fi

tmp="$(mktemp)"
if curl -fsS --max-time 15 "${BULLETIN_URL}" -o "${tmp}"; then
  if [[ -s "${tmp}" ]]; then
    install -m 0644 "${tmp}" "${BULLETIN_FILE}"
    rm -f "${tmp}"
    exit 0
  fi
fi
rm -f "${tmp}"
exit 0
