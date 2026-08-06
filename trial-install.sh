#!/usr/bin/env bash
# Public 8-BALL trial installer — detects platform lane and accepts a base model slug.
# Usage: curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/trial-install.sh | sh -s -- gemma4
set -euo pipefail

MODEL_SLUG="${1:-}"
RAW_BASE="${EIGHTBALL_RAW_BASE:-https://raw.githubusercontent.com/terminal-glass/8-ball/main}"
REPO_HINT="${EIGHTBALL_REPO_ROOT:-}"
PROFILES_BASE="${EIGHTBALL_PROFILES_BASE:-${RAW_BASE}}"

detect_lane() {
  local os arch gpu_vram cuda lane
  os="$(uname -s 2>/dev/null || echo unknown)"
  arch="$(uname -m 2>/dev/null || echo unknown)"

  if [[ -f /sys/hypervisor/uuid ]] && grep -qi ec2 /sys/hypervisor/uuid 2>/dev/null; then
    if curl -fsS --max-time 1 http://169.254.169.254/latest/meta-data/ >/dev/null 2>&1; then
      if command -v nvidia-smi >/dev/null 2>&1; then
        echo "cloud/aws-lightsail/gpu"
        return 0
      fi
      echo "cloud/aws-lightsail/cpu"
      return 0
    fi
  fi

  if [[ -f /etc/digitalocean ]] || grep -qi digitalocean /etc/os-release 2>/dev/null; then
    if command -v nvidia-smi >/dev/null 2>&1; then
      echo "cloud/digitalocean/gpu-droplet"
      return 0
    fi
    echo "cloud/digitalocean/cpu-droplet"
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
      cuda="false"
      if command -v nvidia-smi >/dev/null 2>&1; then
        cuda="true"
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

resolve_installer() {
  local lane="$1"
  local local_path=""
  if [[ -n "${REPO_HINT}" && -f "${REPO_HINT}/install/${lane}/trial-install.sh" ]]; then
    local_path="${REPO_HINT}/install/${lane}/trial-install.sh"
  elif [[ -f "./install/${lane}/trial-install.sh" ]]; then
    local_path="./install/${lane}/trial-install.sh"
  fi
  if [[ -n "${local_path}" ]]; then
    printf '%s' "${local_path}"
    return 0
  fi
  local tmp
  tmp="$(mktemp)"
  curl -fsSL "${RAW_BASE}/install/${lane}/trial-install.sh" -o "${tmp}"
  bash -n "${tmp}"
  install -m 0755 "${tmp}" "${tmp}.run"
  rm -f "${tmp}"
  printf '%s' "${tmp}.run"
}

main() {
  local lane installer
  lane="$(detect_lane)"
  installer="$(resolve_installer "${lane}")"
  export EIGHTBALL_INSTALL_LANE="${lane}"
  export EIGHTBALL_MODEL_SLUG="${MODEL_SLUG}"
  export EIGHTBALL_PROFILES_BASE="${PROFILES_BASE}"
  export EIGHTBALL_RAW_BASE="${RAW_BASE}"
  if [[ -n "${MODEL_SLUG}" ]]; then
    exec "${installer}" --model-slug "${MODEL_SLUG}" "$@"
  fi
  exec "${installer}" "$@"
}

main "$@"
