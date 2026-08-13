#!/usr/bin/env bash
# 8-BALL suite version contract — source from trial-install and 8.x scripts.
set -euo pipefail

EIGHTBALL_SUITE_VERSION="${EIGHTBALL_SUITE_VERSION:-0.8.0}"
EIGHTBALL_SCRIPT_FAMILY="${EIGHTBALL_SCRIPT_FAMILY:-8-BALL}"

eightball_read_script_version() {
  local script_path="$1"
  if [[ ! -f "${script_path}" ]]; then
    return 1
  fi
  awk -F'"' '/^EIGHTBALL_SCRIPT_VERSION=/ {print $2; exit}' "${script_path}"
}

eightball_verify_script_version() {
  local script_path="$1"
  local label="${2:-$(basename "${script_path}")}"
  local found=""
  found="$(eightball_read_script_version "${script_path}" || true)"
  if [[ -z "${found}" ]]; then
    echo "[version] ${label}: missing EIGHTBALL_SCRIPT_VERSION" >&2
    return 1
  fi
  if [[ "${found}" != "${EIGHTBALL_SUITE_VERSION}" ]]; then
    cat >&2 <<EOF
[version] Incompatible 8-BALL script versions detected.
  Expected suite version: ${EIGHTBALL_SUITE_VERSION} (${EIGHTBALL_SCRIPT_FAMILY})
  ${label}: ${found}
  Refuse to run a mismatched installer bundle.
  Set EIGHTBALL_RELEASE to a single tagged release or use a consistent local checkout.
EOF
    return 1
  fi
  return 0
}

eightball_verify_bundle() {
  local base_dir="$1"
  shift
  local script rel
  for script in "$@"; do
    rel="${script#${base_dir}/}"
    rel="${rel#/}"
    if ! eightball_verify_script_version "${base_dir}/${script}" "${rel}"; then
      return 1
    fi
  done
  return 0
}
