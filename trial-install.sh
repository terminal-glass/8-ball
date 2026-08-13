#!/usr/bin/env bash
# Public 8-BALL trial installer — detects platform lane and accepts a base model slug.
# Usage: ./trial-install.sh --model-slug gemma
set -euo pipefail

EIGHTBALL_RELEASE_REPO="${EIGHTBALL_RELEASE_REPO:-funtech64/8-ball}"
EIGHTBALL_RELEASE_REF="${EIGHTBALL_RELEASE_REF:-7800b2c478b6f8e59a56e45dbc2c5de64106e032}"
REPO_HINT="${EIGHTBALL_REPO_ROOT:-}"
PHILO_ROOT="${PHILO_ROOT:-/opt/philosopher}"
TRIAL_LOG="${PHILO_ROOT}/trial-log.txt"

detect_lane() {
  local os arch gpu_vram
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

resolve_installer() {
  local lane="$1"
  if [[ -n "${REPO_HINT}" && -f "${REPO_HINT}/install/${lane}/trial-install.sh" ]]; then
    printf '%s' "${REPO_HINT}/install/${lane}/trial-install.sh"
    return 0
  fi
  if [[ -f "./install/${lane}/trial-install.sh" ]]; then
    printf '%s' "./install/${lane}/trial-install.sh"
    return 0
  fi
  cat >&2 <<EOF
Could not find install/${lane}/trial-install.sh in a local checkout.

Clone https://github.com/${EIGHTBALL_RELEASE_REPO} at ref ${EIGHTBALL_RELEASE_REF}
and run:
  cd install/${lane}
  sudo ./trial-install.sh --model-slug <slug> --yes
EOF
  exit 1
}

main() {
  local lane installer
  lane="$(detect_lane)"
  installer="$(resolve_installer "${lane}")"
  export EIGHTBALL_INSTALL_LANE="${lane}"
  export EIGHTBALL_RELEASE_REPO EIGHTBALL_RELEASE_REF PHILO_ROOT TRIAL_LOG
  exec "${installer}" "$@"
}

main "$@"
