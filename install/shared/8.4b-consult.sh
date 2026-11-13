#!/usr/bin/env bash
# 8.4b-consult.sh — experimental consultation.
# Letter suffix "b": this script is not a new install stage.
# trial-install.sh, 8.1.sh, 8.2.sh, and 8.3.sh keep their numbers.
# Catalog values are forwarded as arguments and are never expanded by the shell.
# A Meta API key is read by Python getpass on a terminal. The shell never
# sees that key, and the key is not accepted in "$@".
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ "${HOME:-}" == "/root" ]]; then
  printf '%s\n' "8.4b refuses HOME=/root. Use the installing user's home." >&2
  exit 2
fi

exec python3 -m eight_ball.manager consult "$@"
