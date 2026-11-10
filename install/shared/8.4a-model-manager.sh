#!/usr/bin/env bash
# 8.4a-model-manager.sh — experimental free model manager.
# Letter suffix "a": this script is not part of
# trial-install.sh -> 8.1.sh -> 8.2.sh -> 8.3.sh.
# Catalog values are data. They are forwarded as arguments and are never
# expanded into a shell command.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ "${HOME:-}" == "/root" ]]; then
  printf '%s\n' "8.4a refuses HOME=/root. Use the installing user's home." >&2
  exit 2
fi

exec python3 -m eight_ball.manager "$@"
