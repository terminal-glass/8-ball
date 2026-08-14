#!/usr/bin/env bash
# Release download and integrity helpers for trial-install.sh
set -euo pipefail

EIGHTBALL_RELEASE="${EIGHTBALL_RELEASE:-v0.8.0}"
EIGHTBALL_RELEASE_MANIFEST="${EIGHTBALL_RELEASE_MANIFEST:-}"
EIGHTBALL_RELEASE_REPO="${EIGHTBALL_RELEASE_REPO:-terminal-glass/8-ball}"

eightball_release_is_development() {
  if [[ "${EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS:-0}" == "1" ]]; then
    return 0
  fi
  if [[ -n "${EIGHTBALL_RAW_BASE:-}" ]]; then
    return 0
  fi
  if [[ "${EIGHTBALL_RELEASE}" == "main" ]]; then
    return 0
  fi
  return 1
}

eightball_release_raw_base() {
  local profile="${1:-ubuntu}"
  if [[ -n "${EIGHTBALL_RAW_BASE:-}" ]]; then
    printf '%s' "${EIGHTBALL_RAW_BASE}"
    return 0
  fi
  if [[ "${EIGHTBALL_RELEASE}" == "main" ]]; then
    printf 'https://raw.githubusercontent.com/%s/main/install/%s' \
      "${EIGHTBALL_RELEASE_REPO}" "${profile}"
    return 0
  fi
  if [[ -n "${EIGHTBALL_RELEASE_REF:-}" ]]; then
    printf 'https://raw.githubusercontent.com/%s/%s/install/%s' \
      "${EIGHTBALL_RELEASE_REPO}" "${EIGHTBALL_RELEASE_REF}" "${profile}"
    return 0
  fi
  echo "EIGHTBALL_RELEASE_REF is required for verified release bootstrap." >&2
  return 1
}

eightball_release_raw_repo_base() {
  if [[ -n "${EIGHTBALL_RAW_BASE:-}" ]]; then
    local trimmed="${EIGHTBALL_RAW_BASE%/}"
    trimmed="${trimmed%/install/ubuntu}"
    trimmed="${trimmed%/install}"
    printf '%s' "${trimmed}"
    return 0
  fi
  if [[ "${EIGHTBALL_RELEASE}" == "main" ]]; then
    printf 'https://raw.githubusercontent.com/%s/main' "${EIGHTBALL_RELEASE_REPO}"
    return 0
  fi
  if [[ -n "${EIGHTBALL_RELEASE_REF:-}" ]]; then
    printf 'https://raw.githubusercontent.com/%s/%s' \
      "${EIGHTBALL_RELEASE_REPO}" "${EIGHTBALL_RELEASE_REF}"
    return 0
  fi
  echo "EIGHTBALL_RELEASE_REF is required for verified release bootstrap (logical ${EIGHTBALL_RELEASE} is not a Git ref)." >&2
  return 1
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

eightball_fetch_release_manifest() {
  local dest="$1"
  local manifest_url
  if manifest_path="$(eightball_manifest_path_for_release "${2:-.}" 2>/dev/null)"; then
    install -D -m 0644 "${manifest_path}" "${dest}"
    printf '%s' "${dest}"
    return 0
  fi
  manifest_url="$(eightball_release_raw_repo_base)/install/releases/${EIGHTBALL_RELEASE}/manifest.json"
  if ! curl -fsSL "${manifest_url}" -o "${dest}.partial"; then
    rm -f "${dest}.partial"
    echo "Failed to download release manifest: ${manifest_url}" >&2
    return 1
  fi
  if ! python3 -m json.tool "${dest}.partial" >/dev/null 2>&1; then
    rm -f "${dest}.partial"
    echo "Downloaded release manifest is not valid JSON: ${manifest_url}" >&2
    return 1
  fi
  mv "${dest}.partial" "${dest}"
  printf '%s' "${dest}"
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
artifacts = manifest.get("artifacts", {})
expected = None
for rel_path, digest in artifacts.items():
    if rel_path.endswith(f"/{script_name}") or rel_path == script_name:
        expected = digest
        break
if expected is None:
    expected = manifest.get("scripts", {}).get(script_name)
if not expected:
    print(f"[release] No checksum recorded for {script_name}; refusing verification", file=sys.stderr)
    raise SystemExit(1)
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

eightball_verify_artifact_sha() {
  local rel_path="$1"
  local file_path="$2"
  local manifest_path="$3"
  python3 - "${manifest_path}" "${rel_path}" "${file_path}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path, rel_path, file_path = sys.argv[1:4]
manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
artifacts = manifest.get("artifacts", {})
expected = artifacts.get(rel_path)
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

eightball_download_verified_artifact() {
  local rel_path="$1"
  local dest_path="$2"
  local manifest_path="$3"
  local url="${4:-$(eightball_release_raw_repo_base)/${rel_path}}"
  local tmp parent
  parent="$(dirname "${dest_path}")"
  install -d -m 0755 "${parent}"
  tmp="$(mktemp "${parent}/.artifact.XXXXXX")"
  if ! curl -fsSL "${url}" -o "${tmp}"; then
    rm -f "${tmp}"
    echo "Failed to download release artifact: ${url}" >&2
    return 1
  fi
  if ! eightball_verify_artifact_sha "${rel_path}" "${tmp}" "${manifest_path}"; then
    rm -f "${tmp}"
    echo "Refusing to install unverified artifact: ${rel_path}" >&2
    return 1
  fi
  mv "${tmp}" "${dest_path}"
}

eightball_locate_repo_root_from() {
  local start_dir="$1"
  local dir="${start_dir}"
  while [[ "${dir}" != "/" ]]; do
    if [[ -d "${dir}/profiles" && -d "${dir}/install" && -f "${dir}/scripts/c10_common.py" ]]; then
      printf '%s' "${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  return 1
}

eightball_local_bundle_ready() {
  local script_dir="$1"
  local script
  for script in 8.1.sh 8.2.sh 8.3.sh; do
    if [[ ! -f "${script_dir}/${script}" ]]; then
      return 1
    fi
    if ! eightball_verify_script_version "${script_dir}/${script}" "${script}"; then
      return 1
    fi
  done
  if ! eightball_locate_repo_root_from "${script_dir}" >/dev/null; then
    return 1
  fi
  return 0
}

eightball_bootstrap_release_runtime() {
  local script_dir="$1"
  local staging_root="${EIGHTBALL_RELEASE_STAGING:-${PHILOSOPHER_ROOT:-/opt/philosopher}/.8ball-release/${EIGHTBALL_RELEASE}}"
  local manifest_cache="${staging_root}/manifest.json"
  local rel_path dest_path script_name local_script
  local -a ubuntu_runtime_scripts=(
    install/ubuntu/8.1.sh
    install/ubuntu/8.2.sh
    install/ubuntu/8.3.sh
  )

  if eightball_release_is_development; then
    echo "[release] DEVELOPMENT override active; skipping verified release bootstrap." >&2
    if repo_root="$(eightball_locate_repo_root_from "${script_dir}" 2>/dev/null || true)"; then
      export EIGHTBALL_REPO_ROOT="${repo_root}"
    fi
    return 0
  fi

  install -d -m 0755 "${staging_root}"
  if [[ ! -f "${manifest_cache}" ]]; then
    eightball_fetch_release_manifest "${manifest_cache}" "${script_dir}" || return 1
  fi

  python3 - "${manifest_cache}" <<'PY' || return 1
import json, sys
json.load(open(sys.argv[1], encoding="utf-8"))
PY

  while IFS= read -r rel_path; do
    [[ -z "${rel_path}" ]] && continue
    case "${rel_path}" in
      install/ubuntu/trial-install.sh) continue ;;
    esac
    dest_path="${staging_root}/${rel_path}"
    if [[ -f "${dest_path}" ]] && eightball_verify_artifact_sha "${rel_path}" "${dest_path}" "${manifest_cache}" 2>/dev/null; then
      continue
    fi
    eightball_download_verified_artifact "${rel_path}" "${dest_path}" "${manifest_cache}" || return 1
  done < <(
    python3 - "${manifest_cache}" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
for rel_path in sorted(manifest.get("artifacts", {})):
    print(rel_path)
PY
  )

  export EIGHTBALL_REPO_ROOT="${staging_root}"
  export EIGHTBALL_RELEASE_STAGING="${staging_root}"
  if [[ -z "${EIGHTBALL_MANIFEST:-}" && -f "${staging_root}/install/releases/${EIGHTBALL_RELEASE}/install-manifest.json" ]]; then
    export EIGHTBALL_MANIFEST="${staging_root}/install/releases/${EIGHTBALL_RELEASE}/install-manifest.json"
  elif [[ -z "${EIGHTBALL_MANIFEST:-}" && -f "${staging_root}/data/generated/pages/install-manifest.json" ]]; then
    export EIGHTBALL_MANIFEST="${staging_root}/data/generated/pages/install-manifest.json"
  fi

  for rel_path in "${ubuntu_runtime_scripts[@]}"; do
    script_name="${rel_path##*/}"
    local_script="${script_dir}/${script_name}"
    dest_path="${staging_root}/${rel_path}"
    if [[ ! -f "${local_script}" ]] || ! eightball_verify_artifact_sha "${rel_path}" "${local_script}" "${manifest_cache}" 2>/dev/null; then
      install -m 0755 "${dest_path}" "${local_script}"
    fi
  done

  if [[ -d "${staging_root}/install/shared" ]]; then
    install -d -m 0755 "${script_dir}/../shared"
    for shared_file in "${staging_root}"/install/shared/*; do
      [[ -f "${shared_file}" ]] || continue
      install -m 0755 "${shared_file}" "${script_dir}/../shared/$(basename "${shared_file}")"
    done
    if [[ -d "${staging_root}/install/shared/systemd" ]]; then
      install -d -m 0755 "${script_dir}/../shared/systemd"
      install -m 0644 "${staging_root}"/install/shared/systemd/* "${script_dir}/../shared/systemd/" 2>/dev/null || true
    fi
  fi
  if [[ -d "${staging_root}/install/ubuntu/assets" ]]; then
    install -d -m 0755 "${script_dir}/assets"
    install -m 0644 "${staging_root}"/install/ubuntu/assets/* "${script_dir}/assets/" 2>/dev/null || true
  fi

  printf '%s' "${staging_root}"
}
