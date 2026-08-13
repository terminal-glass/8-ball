#!/usr/bin/env bash
# Shared no-mutation help/preflight contract for public installer entrypoints (C10.2-5).
# Source from lane scripts after EIGHTBALL_INSTALL_LANE is set.
set -euo pipefail

: "${EIGHTBALL_INSTALL_LANE:?EIGHTBALL_INSTALL_LANE is required}"
: "${INSTALLER_SMOKE_SCRIPT_NAME:?INSTALLER_SMOKE_SCRIPT_NAME is required}"
: "${INSTALLER_SMOKE_PLATFORM:?INSTALLER_SMOKE_PLATFORM is required (mac|linux)}"
: "${INSTALLER_SMOKE_CHECKS:?INSTALLER_SMOKE_CHECKS is required}"

installer_smoke_usage() {
  cat <<EOF
Usage: ${INSTALLER_SMOKE_SCRIPT_NAME} [options]

Lane: ${EIGHTBALL_INSTALL_LANE}

${INSTALLER_SMOKE_CHECKS}

Options:
  -h, --help       Show this help without mutating the host
  --preflight      Report lane identity and planned checks without installing software
EOF
}

installer_smoke_preflight_mac() {
  if [[ "$(uname -s 2>/dev/null || echo unknown)" != "Darwin" ]]; then
    echo "unsupported: lane ${EIGHTBALL_INSTALL_LANE} requires native macOS" >&2
    return 2
  fi
  if [[ -n "${MAC_EXPECTED_ARCH:-}" ]]; then
    local actual
    actual="$(uname -m 2>/dev/null || echo unknown)"
    if [[ "${actual}" != "${MAC_EXPECTED_ARCH}" ]]; then
      echo "unsupported: lane ${EIGHTBALL_INSTALL_LANE} requires architecture ${MAC_EXPECTED_ARCH}; detected ${actual}" >&2
      return 2
    fi
  fi
  return 0
}

installer_smoke_preflight_linux() {
  if [[ ! -f /etc/os-release ]]; then
    echo "unsupported: lane ${EIGHTBALL_INSTALL_LANE} requires a Debian-family host with /etc/os-release" >&2
    return 2
  fi
  # shellcheck source=/dev/null
  source /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ;;
    *)
      echo "unsupported: lane ${EIGHTBALL_INSTALL_LANE} requires Ubuntu or Debian; detected ID=${ID:-unknown}" >&2
      return 2
      ;;
  esac
  return 0
}

installer_smoke_run_preflight() {
  printf 'lane: %s\n' "${EIGHTBALL_INSTALL_LANE}"
  printf 'mode: preflight (no installation performed)\n'
  printf 'planned_checks:\n%s\n' "${INSTALLER_SMOKE_CHECKS}"
  case "${INSTALLER_SMOKE_PLATFORM}" in
    mac) installer_smoke_preflight_mac ;;
    linux) installer_smoke_preflight_linux ;;
    *)
      echo "unsupported: unknown smoke platform ${INSTALLER_SMOKE_PLATFORM}" >&2
      return 2
      ;;
  esac
}

installer_smoke_prologue() {
  for arg in "$@"; do
    case "${arg}" in
      -h|--help)
        installer_smoke_usage
        exit 0
        ;;
      --preflight)
        installer_smoke_run_preflight
        exit $?
        ;;
    esac
  done
}
