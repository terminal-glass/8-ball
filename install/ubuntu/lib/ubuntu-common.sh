#!/usr/bin/env bash
# Shared Ubuntu/Debian installer helpers for public 8-BALL trial lanes.
set -euo pipefail

SUITE_VERSION="8BALL-0.8.0"
PHILO_ROOT="${PHILO_ROOT:-/opt/philosopher}"
PHILOSOPHER_ROOT="${PHILOSOPHER_ROOT:-${PHILO_ROOT}}"
TRIAL_LOG="${PHILO_ROOT}/trial-log.txt"
LOG_FILE="${TRIAL_LOG}"
RESULT_FILE="${PHILOSOPHER_ROOT}/8ball-result.txt"
RESULT_ENV="${PHILOSOPHER_ROOT}/profiles/90-result.env"
RECOMMENDATION_ENV="${PHILOSOPHER_ROOT}/profiles/50-recommendation.env"
HARDWARE_ENV="${PHILOSOPHER_ROOT}/profiles/20-hardware.env"
OLLAMA_API="${OLLAMA_API:-http://127.0.0.1:11434}"
OLLAMA_PULL_TIMEOUT_SECONDS="${OLLAMA_PULL_TIMEOUT_SECONDS:-1800}"

RAM_MB="0"
CPU_THREADS="0"
FREE_DISK_MB="0"
FREE_DISK_GB="0"
SYSTEM_RAM_GB="0"
USABLE_MODEL_RAM_GB="0"
GPU_NAME="none"
GPU_VRAM_MB="0"
GPU_VRAM_GB="0"
CUDA_AVAILABLE="false"

# Release pin for remote bootstrap (maintainer: bump on each public installer release).
EIGHTBALL_RELEASE_REPO="${EIGHTBALL_RELEASE_REPO:-terminal-glass/8-ball}"
EIGHTBALL_RELEASE_REF="${EIGHTBALL_RELEASE_REF:-1f3655acdcf469108d33fb886116847753959384}"

UBUNTU_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

declare -A EIGHTBALL_RELEASE_SHA256=()

ubuntu_release_hash_key() {
  printf '%s/%s' "${EIGHTBALL_INSTALL_LANE}" "$1"
}

ubuntu_set_release_hashes_for_lane() {
  local lane="${1:?lane required}"
  local canonical_trial
  canonical_trial="$(ubuntu_sha256_file "${UBUNTU_LIB_DIR}/../trial-install.sh")"
  case "${lane}" in
    ubuntu/cpu)
      EIGHTBALL_RELEASE_SHA256["ubuntu/cpu/trial-install.sh"]="${canonical_trial}"
      EIGHTBALL_RELEASE_SHA256["ubuntu/cpu/8.1.sh"]="2e69bc2d23af825edd9d19d7140f07ff0d936efed553245c4c37794eaccf68be"
      EIGHTBALL_RELEASE_SHA256["ubuntu/cpu/8.2.sh"]="77334d876d5134e381a5fb30db84badd3e2b99c906ce5ed8beec3519c7ba73da"
      EIGHTBALL_RELEASE_SHA256["ubuntu/cpu/8.3.sh"]="33edfbc5922cc54aa64647d249623cc7542ba32683e1e408b0a74242ff99549b"
      ;;
    ubuntu/cuda)
      EIGHTBALL_RELEASE_SHA256["ubuntu/cuda/trial-install.sh"]="${canonical_trial}"
      EIGHTBALL_RELEASE_SHA256["ubuntu/cuda/8.1.sh"]="94ad8c9bdcc8724e83e6bc9257ed8c104ac7d4c2274e6d6d3d282158fca447f6"
      EIGHTBALL_RELEASE_SHA256["ubuntu/cuda/8.2.sh"]="1a9641c9b71e93cb4f60b2823665cab9cf7a70309527f32aa51a441c3d0fe00d"
      EIGHTBALL_RELEASE_SHA256["ubuntu/cuda/8.3.sh"]="6ff7df449a72e577330bc0d9cee35249faa0c588c33fca87f3cef842ffd7108d"
      ;;
    *)
      echo "No release hashes configured for lane ${lane}" >&2
      exit 1
      ;;
  esac
}

ubuntu_log() {
  local prefix="${UBUNTU_LOG_PREFIX:-ubuntu}"
  printf '[%s] %s\n' "${prefix}" "$*"
  printf '[%s] %s\n' "${prefix}" "$*" >>"${TRIAL_LOG}" 2>/dev/null || true
}

ubuntu_require_root() {
  if [[ "${EIGHTBALL_TEST_SKIP_ROOT:-0}" == "1" ]]; then
    return 0
  fi
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "This installer requires root. Re-run with sudo." >&2
    exit 1
  fi
}

ubuntu_validate_ollama_api() {
  case "${OLLAMA_API}" in
    http://127.0.0.1:*|http://localhost:*|http://[::1]:*) ;;
    *)
      echo "OLLAMA_API must use a loopback address. Refusing: ${OLLAMA_API}" >&2
      exit 1
      ;;
  esac
}

ubuntu_require_debian_family() {
  if [[ ! -f /etc/os-release ]]; then
    echo "Ubuntu/Debian hosts with /etc/os-release are required." >&2
    exit 1
  fi
  # shellcheck source=/dev/null
  source /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ;;
    *)
      echo "Ubuntu/Debian required. Detected ID=${ID:-unknown}." >&2
      exit 1
      ;;
  esac
}

ubuntu_ensure_state_root() {
  install -d -m 0755 "${PHILO_ROOT}" "${PHILOSOPHER_ROOT}/profiles"
  touch "${TRIAL_LOG}"
  chmod 0644 "${TRIAL_LOG}"
}

ubuntu_resolve_profile_dir() {
  local profile_dir=""
  if [[ -n "${EIGHTBALL_PROFILE_DIR:-}" ]]; then
    profile_dir="${EIGHTBALL_PROFILE_DIR}"
  elif [[ -n "${NCGPT_PROFILE_DIR:-}" ]]; then
    profile_dir="${NCGPT_PROFILE_DIR}"
  elif [[ -f /opt/philosopher/instance.env ]]; then
    # shellcheck source=/dev/null
    source /opt/philosopher/instance.env
    profile_dir="${PROFILE_DIR:-${EIGHTBALL_PROFILE_DIR:-}}"
  fi
  if [[ -z "${profile_dir}" ]]; then
    profile_dir="${PHILOSOPHER_ROOT}/profiles"
  fi
  EIGHTBALL_PROFILE_DIR="${profile_dir}"
  export EIGHTBALL_PROFILE_DIR
  install -d -m 0755 "${EIGHTBALL_PROFILE_DIR}"
}

ubuntu_find_repo_root() {
  local dir="${1:-${SCRIPT_DIR:-$PWD}}"
  if [[ -n "${EIGHTBALL_REPO_ROOT:-}" && -f "${EIGHTBALL_REPO_ROOT}/profiles/manifest.json" ]]; then
    printf '%s' "${EIGHTBALL_REPO_ROOT}"
    return 0
  fi
  while [[ "${dir}" != "/" ]]; do
    if [[ -f "${dir}/profiles/manifest.json" ]]; then
      printf '%s' "${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  return 1
}

ubuntu_release_raw_url() {
  local lane="${EIGHTBALL_INSTALL_LANE:?EIGHTBALL_INSTALL_LANE is required}"
  local name="$1"
  if [[ "${name}" == "trial-install.sh" ]]; then
    printf 'https://raw.githubusercontent.com/%s/%s/install/ubuntu/trial-install.sh' \
      "${EIGHTBALL_RELEASE_REPO}" "${EIGHTBALL_RELEASE_REF}"
    return 0
  fi
  printf 'https://raw.githubusercontent.com/%s/%s/install/%s/%s' \
    "${EIGHTBALL_RELEASE_REPO}" "${EIGHTBALL_RELEASE_REF}" "${lane}" "${name}"
}

ubuntu_sha256_file() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${path}" | awk '{print $1}'
  else
    python3 - "${path}" <<'PY'
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
PY
  fi
}

ubuntu_verify_and_stage_remote_script() {
  local name="$1"
  ubuntu_set_release_hashes_for_lane "${EIGHTBALL_INSTALL_LANE}"
  local key expected actual allow_dev url tmp
  key="$(ubuntu_release_hash_key "${name}")"
  expected="${EIGHTBALL_RELEASE_SHA256[${key}]:-}"

  if [[ -z "${expected}" || "${expected}" == *_HASH ]]; then
    echo "Release pin missing trusted SHA-256 for ${key}. Maintainer must update install/ubuntu/lib/ubuntu-common.sh." >&2
    exit 1
  fi

  url="$(ubuntu_release_raw_url "${name}")"
  tmp="$(mktemp)"
  if ! curl -fsSL "${url}" -o "${tmp}"; then
    rm -f "${tmp}"
    echo "Failed to download release-pinned payload: ${url}" >&2
    exit 1
  fi

  actual="$(ubuntu_sha256_file "${tmp}")"
  if [[ "${actual}" != "${expected}" ]]; then
    rm -f "${tmp}"
    echo "Checksum mismatch for ${name}." >&2
    echo "Expected: ${expected}" >&2
    echo "Actual:   ${actual}" >&2
    echo "Refusing to install or execute an unverified remote script." >&2
    exit 1
  fi

  if ! bash -n "${tmp}"; then
    rm -f "${tmp}"
    echo "Syntax check failed for downloaded ${name}." >&2
    exit 1
  fi

  if [[ "${EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS:-0}" == "1" ]]; then
    ubuntu_log "DEVELOPMENT ONLY: staging verified ${name} from ${url}"
  else
    ubuntu_log "Verified release-pinned ${name} from ${url}"
  fi
  printf '%s' "${tmp}"
}

ubuntu_resolve_lane_script() {
  local name="$1"
  local local_path="${SCRIPT_DIR}/${name}"
  if [[ -f "${local_path}" ]]; then
    printf '%s' "${local_path}"
    return 0
  fi

  if [[ "${EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS:-0}" == "1" && -n "${EIGHTBALL_DEV_RAW_BASE:-}" ]]; then
    local tmp dev_url="${EIGHTBALL_DEV_RAW_BASE%/}/${name}"
    tmp="$(mktemp)"
    ubuntu_log "DEVELOPMENT ONLY: downloading ${name} from ${dev_url} (integrity override)"
    curl -fsSL "${dev_url}" -o "${tmp}"
    bash -n "${tmp}"
    printf '%s' "${tmp}"
    return 0
  fi

  ubuntu_verify_and_stage_remote_script "${name}"
}

ubuntu_show_planned_changes() {
  cat <<EOF
Planned 8-BALL system changes:
  - Install packages: ca-certificates, curl, python3, zstd (via apt-get)
  - Create state directories under ${PHILO_ROOT}
  - Install Ollama only when missing and only with explicit --accept-ollama-install-risk
  - Configure Ollama for localhost API at ${OLLAMA_API}
  - Write profile runtime artifacts under ${PHILOSOPHER_ROOT}/profiles
  - Install MOTD and helper scripts when 8.3 runs

This public installer does NOT create swap, modify /etc/fstab, or write global APT policy files.
EOF
}

ubuntu_require_noninteractive_confirm() {
  if [[ "${EIGHTBALL_NONINTERACTIVE_CONFIRM:-0}" == "1" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    cat >&2 <<EOF
Refusing unattended execution without explicit confirmation.

Re-run with:
  --yes   (or export EIGHTBALL_NONINTERACTIVE_CONFIRM=1)

$(ubuntu_show_planned_changes)
EOF
    exit 1
  fi
}

ubuntu_detect_hardware() {
  RAM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
  CPU_THREADS="$(nproc 2>/dev/null || echo 1)"
  FREE_DISK_MB="$(df -Pm / | awk 'NR==2 {print $4}')"
  FREE_DISK_GB="$(python3 - <<PY
print(round(${FREE_DISK_MB} / 1024.0, 2))
PY
)"
  SYSTEM_RAM_GB="$(python3 - <<PY
print(round(${RAM_MB} / 1024.0, 2))
PY
)"
  USABLE_MODEL_RAM_GB="$(python3 - <<PY
print(round((${RAM_MB} / 1024.0) * 0.6, 2))
PY
)"
  GPU_NAME="none"
  GPU_VRAM_MB="0"
  GPU_VRAM_GB="0"
  CUDA_AVAILABLE="false"
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 || echo none)"
    GPU_VRAM_MB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || echo 0)"
    if [[ "${GPU_VRAM_MB}" =~ ^[0-9]+$ ]]; then
      GPU_VRAM_GB="$(python3 - <<PY
print(round(${GPU_VRAM_MB} / 1024.0, 2))
PY
)"
      CUDA_AVAILABLE="true"
    fi
  fi

  export EIGHTBALL_SYSTEM_RAM_GB="${SYSTEM_RAM_GB}"
  export EIGHTBALL_USABLE_MODEL_RAM_GB="${USABLE_MODEL_RAM_GB}"
  export EIGHTBALL_FREE_DISK_GB="${FREE_DISK_GB}"
  export EIGHTBALL_CPU_THREADS="${CPU_THREADS}"
  export EIGHTBALL_GPU_VRAM_GB="${GPU_VRAM_GB}"
  export EIGHTBALL_CUDA_AVAILABLE="${CUDA_AVAILABLE}"
}

ubuntu_write_hardware_env() {
  if [[ "${EIGHTBALL_USE_MEASURED_HARDWARE_ENV:-0}" == "1" ]]; then
    RAM_MB="$(python3 - <<PY
import os
print(int(float(os.environ.get("EIGHTBALL_SYSTEM_RAM_GB", "0") or 0) * 1024))
PY
)"
    CPU_THREADS="${EIGHTBALL_CPU_THREADS:-1}"
    FREE_DISK_MB="$(python3 - <<PY
import os
print(int(float(os.environ.get("EIGHTBALL_FREE_DISK_GB", "0") or 0) * 1024))
PY
)"
    SYSTEM_RAM_GB="${EIGHTBALL_SYSTEM_RAM_GB:-0}"
    USABLE_MODEL_RAM_GB="${EIGHTBALL_USABLE_MODEL_RAM_GB:-0}"
    FREE_DISK_GB="${EIGHTBALL_FREE_DISK_GB:-0}"
    GPU_NAME="${EIGHTBALL_GPU_NAME:-none}"
    GPU_VRAM_MB="$(python3 - <<PY
import os
print(int(float(os.environ.get("EIGHTBALL_GPU_VRAM_GB", "0") or 0) * 1024))
PY
)"
    GPU_VRAM_GB="${EIGHTBALL_GPU_VRAM_GB:-0}"
    CUDA_AVAILABLE="${EIGHTBALL_CUDA_AVAILABLE:-false}"
  else
    ubuntu_detect_hardware
  fi
  install -d -m 0755 "${EIGHTBALL_PROFILE_DIR}"
  cat >"${HARDWARE_ENV}" <<EOF
# Written by 8.2 (${SUITE_VERSION})
EIGHTBALL_SYSTEM_RAM_GB=${SYSTEM_RAM_GB}
EIGHTBALL_USABLE_MODEL_RAM_GB=${USABLE_MODEL_RAM_GB}
EIGHTBALL_FREE_DISK_GB=${FREE_DISK_GB}
EIGHTBALL_CPU_THREADS=${CPU_THREADS}
EIGHTBALL_GPU_NAME=${GPU_NAME}
EIGHTBALL_GPU_VRAM_GB=${GPU_VRAM_GB}
EIGHTBALL_CUDA_AVAILABLE=${CUDA_AVAILABLE}
EOF
  chmod 0644 "${HARDWARE_ENV}"
}

ubuntu_write_recommendation_env() {
  local model="$1" slug="$2" reason="$3"
  cat >"${RECOMMENDATION_ENV}" <<EOF
# Written by 8.2 (${SUITE_VERSION})
EIGHTBALL_MODEL_SLUG=${slug}
EIGHTBALL_SELECTED_OLLAMA_REF=${model}
EIGHTBALL_SELECTION_REASON=${reason}
EIGHTBALL_INSTALL_LANE=${EIGHTBALL_INSTALL_LANE}
EOF
  chmod 0644 "${RECOMMENDATION_ENV}"
}

ubuntu_write_result_env() {
  local model="$1" slug="$2" test_status="$3" tier="$4"
  cat >"${RESULT_ENV}" <<EOF
# Written by 8.2 (${SUITE_VERSION})
MODEL=${model}
MODEL_SLUG=${slug}
MODEL_TEST=${test_status}
TIER=${tier}
INSTALL_LANE=${EIGHTBALL_INSTALL_LANE}
JETS_STATUS=READY_AFTER_SIGNIN
MANIFEST_SOURCE=profiles
EOF
  chmod 0644 "${RESULT_ENV}"

  cat >"${RESULT_FILE}" <<EOF
Model: ${model}
Profile: ${model//[:\/]/-}
Install profile: ${EIGHTBALL_INSTALL_LANE}
Install lane: ${EIGHTBALL_INSTALL_LANE}
Model slug: ${slug}
Tier: ${tier}
Model test: ${test_status}
Jets status: READY_AFTER_SIGNIN
RAM MB: ${RAM_MB}
CPU threads: ${CPU_THREADS}
Free disk MB: ${FREE_DISK_MB}
GPU: ${GPU_NAME}
GPU VRAM MB: ${GPU_VRAM_MB}
Manifest: profiles/${slug}.json
EOF
  chmod 0644 "${RESULT_FILE}"
}

ubuntu_install_packages() {
  ubuntu_log "Installing minimal prerequisites"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y --no-install-recommends ca-certificates curl python3 zstd
}

ubuntu_install_ollama_if_missing() {
  if command -v ollama >/dev/null 2>&1; then
    ubuntu_log "Ollama already installed; reusing existing binary"
    return 0
  fi

  if [[ "${EIGHTBALL_ACCEPT_OLLAMA_INSTALL_RISK:-0}" != "1" ]]; then
    cat >&2 <<'EOF'
Ollama is not installed and the official Linux installer cannot be integrity-verified.

The public 8-BALL installer does not execute mutable https://ollama.com/install.sh
without an explicit development opt-in because Ollama does not publish a pinned
release artifact with a documented SHA-256 for that script.

Install Ollama manually from https://ollama.com/download, then re-run this installer,
or re-run 8.1 with:
  --accept-ollama-install-risk
EOF
    exit 1
  fi

  ubuntu_log "DEVELOPMENT ONLY: downloading ollama.com/install.sh (syntax check only; no checksum available)"
  local tmp
  tmp="$(mktemp)"
  if ! curl -fsSL https://ollama.com/install.sh -o "${tmp}"; then
    rm -f "${tmp}"
    echo "Ollama install script download failed." >&2
    exit 1
  fi
  if ! bash -n "${tmp}"; then
    rm -f "${tmp}"
    echo "Ollama install script failed bash -n syntax check." >&2
    exit 1
  fi
  if ! bash "${tmp}"; then
    rm -f "${tmp}"
    echo "Ollama installation failed." >&2
    exit 1
  fi
  rm -f "${tmp}"
  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama install finished but ollama was not found in PATH." >&2
    exit 1
  fi
}

ubuntu_start_ollama() {
  if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    ubuntu_log "Ollama API already responding on ${OLLAMA_API}"
    return 0
  fi

  if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
    systemctl enable ollama >/dev/null 2>&1 || true
    if systemctl restart ollama; then
      return 0
    fi
    ubuntu_log "systemctl restart ollama failed; trying ollama serve"
  else
    ubuntu_log "systemd unavailable; starting ollama serve in background"
  fi

  if pgrep -x ollama >/dev/null 2>&1; then
    return 0
  fi

  nohup ollama serve >>"${TRIAL_LOG}" 2>&1 &
  sleep 2
}

ubuntu_wait_for_ollama() {
  for _ in $(seq 1 30); do
    if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
      ubuntu_log "Ollama API is responding on ${OLLAMA_API}"
      return 0
    fi
    sleep 2
  done
  echo "Ollama did not become ready at ${OLLAMA_API}" >&2
  exit 1
}

ubuntu_validate_model_tag() {
  local tag="$1"
  if [[ ! "${tag}" =~ ^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$ ]]; then
    echo "Invalid Ollama model tag: ${tag}" >&2
    exit 1
  fi
}

ubuntu_ollama_pull_with_timeout() {
  local model="$1"
  local log_file
  log_file="$(mktemp)"
  if command -v timeout >/dev/null 2>&1; then
    if timeout "${OLLAMA_PULL_TIMEOUT_SECONDS}" ollama pull "${model}" >"${log_file}" 2>&1; then
      cat "${log_file}" >>"${TRIAL_LOG}" || true
      rm -f "${log_file}"
      return 0
    fi
  else
    if ollama pull "${model}" >"${log_file}" 2>&1; then
      cat "${log_file}" >>"${TRIAL_LOG}" || true
      rm -f "${log_file}"
      return 0
    fi
  fi
  ubuntu_log "Model pull failed or timed out for ${model}"
  tail -n 20 "${log_file}" >>"${TRIAL_LOG}" 2>/dev/null || true
  rm -f "${log_file}"
  return 1
}

ubuntu_test_model_generate() {
  local model="$1"
  if ! ubuntu_ollama_pull_with_timeout "${model}"; then
    return 1
  fi
  local response
  if ! response="$(
    curl -fsS --max-time 120 "${OLLAMA_API}/api/generate" \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"${model}\",\"prompt\":\"Reply with only: 8-BALL READY\",\"stream\":false}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("response",""))'
  )"; then
    return 1
  fi
  if grep -qi "8-BALL READY" <<<"${response}"; then
    return 0
  fi
  ubuntu_log "Model response did not contain expected token: ${response}"
  return 1
}

ubuntu_remove_failed_model() {
  local model="$1"
  ollama rm "${model}" >/dev/null 2>&1 || true
}

ubuntu_profile_runtime() {
  local repo_root
  repo_root="$(ubuntu_find_repo_root)" || {
    echo "Could not locate profiles/manifest.json for profile-driven selection." >&2
    exit 1
  }
  python3 "${UBUNTU_LIB_DIR}/ubuntu-profile-runtime.py" "$@"
}

ubuntu_install_8balljets_helper() {
  local target="${EIGHTBALL_BIN_DIR:-/usr/local/bin}/8balljets"
  install -d -m 0755 "$(dirname "${target}")"
  cat >"${target}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "8-BALL JETS cloud options are available after sign-in."
echo "This public trial installer does not activate paid features."
echo "Support: 8ball@terminal.glass"
EOF
  chmod 0755 "${target}"
}

ubuntu_install_remember_helper() {
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

ubuntu_install_motd() {
  local template="$1"
  local target="${EIGHTBALL_MOTD_TARGET:-/etc/update-motd.d/99-8ball-trial}"
  if [[ ! -f "${template}" ]]; then
    echo "Missing MOTD template: ${template}" >&2
    exit 1
  fi
  install -d -m 0755 "$(dirname "${target}")"
  cat >"${target}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
RESULT_ENV="${RESULT_ENV}"
RESULT_FILE="${RESULT_FILE}"
TEMPLATE_FILE="${template}"
ollama_status="STOPPED"
model_status="UNKNOWN"
selected_model="unknown"
if systemctl is-active --quiet ollama 2>/dev/null || curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  ollama_status="RUNNING"
fi
if [[ -f "\${RESULT_ENV}" ]]; then
  # shellcheck source=/dev/null
  source "\${RESULT_ENV}"
  selected_model="\${MODEL:-unknown}"
  if [[ "\${MODEL_TEST:-}" == "PASSED" ]]; then
    model_status="READY"
  fi
elif [[ -f "\${RESULT_FILE}" ]]; then
  selected_model="\$(awk -F': ' '\$1 == "Model" {print \$2}' "\${RESULT_FILE}")"
  if awk -F': ' '\$1 == "Model test" && \$2 == "PASSED"' "\${RESULT_FILE}" >/dev/null; then
    model_status="READY"
  fi
fi
sed \
  -e "s/__OLLAMA_STATUS__/\${ollama_status}/g" \
  -e "s/__MODEL_STATUS__/\${model_status}/g" \
  -e "s/__SELECTED_MODEL__/\${selected_model}/g" \
  "\${TEMPLATE_FILE}"
EOF
  chmod 0755 "${target}"
}
