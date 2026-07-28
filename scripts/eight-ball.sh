#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -e ".[dev]" -q
eight-ball "$@"
