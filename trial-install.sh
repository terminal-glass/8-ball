#!/usr/bin/env bash
# Public 8-BALL trial installer — stable root bootstrap channel on main.
# Customer URL: https://raw.githubusercontent.com/terminal-glass/8-ball/main/trial-install.sh
set -euo pipefail

EIGHTBALL_RELEASE_REPO="${EIGHTBALL_RELEASE_REPO:-terminal-glass/8-ball}"
EIGHTBALL_APPROVED_RELEASE="${EIGHTBALL_APPROVED_RELEASE:-v0.8.0}"
EIGHTBALL_APPROVED_REF="0370d8fd7f064374f19fcb8f1ca595ba62ba83a1"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-/opt/philosopher}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

eightball_root_raw_base() {
  printf 'https://raw.githubusercontent.com/%s/%s' \
    "${EIGHTBALL_RELEASE_REPO}" "${EIGHTBALL_APPROVED_REF}"
}

eightball_root_verify_artifact() {
  local manifest_path="$1"
  local rel_path="$2"
  local file_path="$3"
  python3 - "${manifest_path}" "${rel_path}" "${file_path}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path, rel_path, file_path = sys.argv[1:4]
manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
expected = manifest.get("artifacts", {}).get(rel_path)
if not expected:
    print(f"[release] No checksum recorded for artifact {rel_path}", file=sys.stderr)
    raise SystemExit(1)
path = Path(file_path)
if not path.is_file() or path.stat().st_size == 0:
    print(f"[release] Missing or empty artifact file: {file_path}", file=sys.stderr)
    raise SystemExit(1)
digest = hashlib.sha256(path.read_bytes()).hexdigest()
if digest != expected:
    print(
        f"[release] SHA-256 mismatch for {rel_path}\n"
        f"  expected: {expected}\n"
        f"  actual:   {digest}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
}

eightball_root_download_verified() {
  local rel_path="$1"
  local dest_path="$2"
  local manifest_path="$3"
  local url="${4:-$(eightball_root_raw_base)/${rel_path}}"
  local tmp parent
  parent="$(dirname "${dest_path}")"
  install -d -m 0755 "${parent}"
  tmp="$(mktemp "${parent}/.artifact.XXXXXX")"
  if ! curl -fsSL "${url}" -o "${tmp}"; then
    rm -f "${tmp}"
    echo "Failed to download release artifact: ${url}" >&2
    return 1
  fi
  if ! eightball_root_verify_artifact "${manifest_path}" "${rel_path}" "${tmp}"; then
    rm -f "${tmp}"
    echo "Refusing to install unverified artifact: ${rel_path}" >&2
    return 1
  fi
  install -m 0644 "${tmp}" "${dest_path}"
  chmod 0755 "${dest_path}" 2>/dev/null || true
  case "${rel_path}" in
    *.sh|*.py) chmod 0755 "${dest_path}" ;;
  esac
  rm -f "${tmp}"
}

eightball_root_fetch_manifest() {
  local dest="$1"
  local url
  url="$(eightball_root_raw_base)/install/releases/${EIGHTBALL_APPROVED_RELEASE}/manifest.json"
  if ! curl -fsSL "${url}" -o "${dest}.partial"; then
    rm -f "${dest}.partial"
    cat >&2 <<EOF
Failed to download release manifest:
  ${url}

The approved immutable release is not available from ${EIGHTBALL_RELEASE_REPO}.
EOF
    return 1
  fi
  if ! python3 -m json.tool "${dest}.partial" >/dev/null 2>&1; then
    rm -f "${dest}.partial"
    echo "Downloaded release manifest is not valid JSON: ${url}" >&2
    return 1
  fi
  mv "${dest}.partial" "${dest}"
}

eightball_root_bootstrap_release() {
  local staging_root="${PHILOSOPHER_ROOT}/.8ball-release/${EIGHTBALL_APPROVED_RELEASE}"
  local manifest_cache="${staging_root}/manifest.json"
  local rel_path dest_path

  install -d -m 0755 "${staging_root}"
  if [[ ! -f "${manifest_cache}" ]]; then
    eightball_root_fetch_manifest "${manifest_cache}" || return 1
  fi

  python3 - "${manifest_cache}" <<'PY' || return 1
import json, sys
json.load(open(sys.argv[1], encoding="utf-8"))
PY

  while IFS= read -r rel_path; do
    [[ -z "${rel_path}" ]] && continue
    dest_path="${staging_root}/${rel_path}"
    if [[ -f "${dest_path}" ]] && eightball_root_verify_artifact "${manifest_cache}" "${rel_path}" "${dest_path}" 2>/dev/null; then
      continue
    fi
    eightball_root_download_verified "${rel_path}" "${dest_path}" "${manifest_cache}" || return 1
  done < <(
    python3 - "${manifest_cache}" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
for rel_path in sorted(manifest.get("artifacts", {})):
    print(rel_path)
PY
  )

  printf '%s' "${staging_root}"
}

detect_lane() {
  local os arch gpu_vram
  os="$(uname -s 2>/dev/null || echo unknown)"
  arch="$(uname -m 2>/dev/null || echo unknown)"

  if [[ -f /sys/hypervisor/uuid ]] && grep -qi ec2 /sys/hypervisor/uuid 2>/dev/null; then
    if curl -fsS --max-time 1 http://169.254.169.254/latest/meta-data/ >/dev/null 2>&1; then
      if command -v nvidia-smi >/dev/null 2>&1; then
        echo "ubuntu/cuda"
        return 0
      fi
      echo "ubuntu/cpu"
      return 0
    fi
  fi

  if [[ -f /etc/digitalocean ]] || grep -qi digitalocean /etc/os-release 2>/dev/null; then
    if command -v nvidia-smi >/dev/null 2>&1; then
      echo "ubuntu/cuda"
      return 0
    fi
    echo "ubuntu/cpu"
    return 0
  fi

  case "${os}" in
    Darwin)
      if [[ "${arch}" == "arm64" ]]; then
        echo "mac/apple-silicon"
      else
        echo "mac/intel"
      fi
      ;;
    MINGW*|MSYS*|CYGWIN*|Windows*)
      if command -v nvidia-smi >/dev/null 2>&1; then
        echo "windows/cuda"
      else
        echo "windows/cpu"
      fi
      ;;
    Linux|GNU/Linux)
      if command -v nvidia-smi >/dev/null 2>&1; then
        gpu_vram="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || echo 0)"
        if [[ "${gpu_vram}" =~ ^[0-9]+$ ]] && [[ "${gpu_vram}" -ge 6000 ]]; then
          echo "ubuntu/cuda"
          return 0
        fi
      fi
      echo "ubuntu/cpu"
      ;;
    *)
      echo "ubuntu/cpu"
      ;;
  esac
}

resolve_local_ubuntu_installer() {
  if [[ -n "${EIGHTBALL_REPO_ROOT:-}" && -f "${EIGHTBALL_REPO_ROOT}/install/ubuntu/trial-install.sh" ]]; then
    printf '%s' "${EIGHTBALL_REPO_ROOT}/install/ubuntu/trial-install.sh"
    return 0
  fi
  if [[ -f "${SCRIPT_DIR}/install/ubuntu/trial-install.sh" ]]; then
    printf '%s' "${SCRIPT_DIR}/install/ubuntu/trial-install.sh"
    return 0
  fi
  return 1
}

run_ubuntu_installer() {
  local lane="$1"
  shift
  local staging installer

  if ! installer="$(resolve_local_ubuntu_installer)"; then
    staging="$(eightball_root_bootstrap_release)" || {
      echo "Failed to bootstrap verified release ${EIGHTBALL_APPROVED_RELEASE}." >&2
      exit 1
    }
    installer="${staging}/install/ubuntu/trial-install.sh"
    export EIGHTBALL_REPO_ROOT="${staging}"
    export EIGHTBALL_MANIFEST="${staging}/install/releases/${EIGHTBALL_APPROVED_RELEASE}/install-manifest.json"
  fi

  export EIGHTBALL_RELEASE="${EIGHTBALL_APPROVED_RELEASE}"
  export EIGHTBALL_RELEASE_REF="${EIGHTBALL_APPROVED_REF}"
  export EIGHTBALL_INSTALL_LANE="${lane}"
  export PHILOSOPHER_ROOT

  if [[ "${EIGHTBALL_BOOTSTRAP_STOP:-0}" == "1" ]]; then
    printf '%s\n' "${installer}"
    exit 0
  fi

  exec "${installer}" "$@"
}

main() {
  local lane
  lane="$(detect_lane)"
  case "${lane}" in
    ubuntu/cpu|ubuntu/cuda)
      run_ubuntu_installer "${lane}" "$@"
      ;;
    *)
      if installer="$(resolve_local_ubuntu_installer)"; then
        export EIGHTBALL_INSTALL_LANE="${lane}"
        exec "${installer}" "$@"
      fi
      cat >&2 <<EOF
This public bootstrap entrypoint currently supports Ubuntu and Debian hosts.

Detected platform lane: ${lane}

Re-run on Ubuntu/Debian, or use a full repository checkout for other platforms.
EOF
      exit 1
      ;;
  esac
}

main "$@"
