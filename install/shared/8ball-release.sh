#!/usr/bin/env bash
# Release download and integrity helpers for trial-install.sh
set -euo pipefail

EIGHTBALL_RELEASE="${EIGHTBALL_RELEASE:-v0.8.0}"
EIGHTBALL_RELEASE_MANIFEST="${EIGHTBALL_RELEASE_MANIFEST:-}"

eightball_release_raw_base() {
  local profile="${1:-ubuntu}"
  if [[ -n "${EIGHTBALL_RAW_BASE:-}" ]]; then
    printf '%s' "${EIGHTBALL_RAW_BASE}"
    return 0
  fi
  if [[ "${EIGHTBALL_RELEASE}" == "main" ]]; then
    printf 'https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/%s' "${profile}"
    return 0
  fi
  printf 'https://raw.githubusercontent.com/terminal-glass/8-ball/%s/install/%s' "${EIGHTBALL_RELEASE}" "${profile}"
}

eightball_manifest_path_for_release() {
  local script_dir="$1"
  if [[ -n "${EIGHTBALL_RELEASE_MANIFEST}" ]]; then
    printf '%s' "${EIGHTBALL_RELEASE_MANIFEST}"
    return 0
  fi
  if [[ "${EIGHTBALL_RELEASE}" == "main" ]]; then
    return 1
  fi
  local candidate="${script_dir}/../releases/${EIGHTBALL_RELEASE}/manifest.json"
  if [[ -f "${candidate}" ]]; then
    printf '%s' "${candidate}"
    return 0
  fi
  return 1
}

eightball_verify_download_sha() {
  local file_path="$1"
  local script_name="$2"
  local manifest_path="$3"
  python3 - "${manifest_path}" "${script_name}" "${file_path}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path, script_name, file_path = sys.argv[1:4]
manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
expected = manifest.get("scripts", {}).get(script_name)
if not expected:
    print(f"[release] No checksum recorded for {script_name}; skipping verification", file=sys.stderr)
    raise SystemExit(0)
digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
if digest != expected:
    print(
        f"[release] SHA-256 mismatch for {script_name}\n"
        f"  expected: {expected}\n"
        f"  actual:   {digest}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
}
