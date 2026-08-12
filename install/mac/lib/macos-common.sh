#!/usr/bin/env bash
# Shared macOS installer helpers for 8-BALL public trial lanes (C10.2-1).
set -euo pipefail

MACOS_MIN_MAJOR_VERSION="${MACOS_MIN_MAJOR_VERSION:-14}"
OLLAMA_MACOS_DOCS_URL="${OLLAMA_MACOS_DOCS_URL:-https://docs.ollama.com/macos}"
DEFAULT_OLLAMA_API="${DEFAULT_OLLAMA_API:-http://127.0.0.1:11434}"

mac_log() {
  printf '[%s] %s\n' "${MAC_LOG_PREFIX:-mac}" "$*"
}

mac_refuse_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "8-BALL macOS installers must run as your normal user account, not as root." >&2
    echo "Re-run as your signed-in user: ./trial-install.sh" >&2
    exit 1
  fi
}

mac_require_darwin() {
  if [[ "$(uname -s 2>/dev/null || echo unknown)" != "Darwin" ]]; then
    echo "This installer supports native macOS only. Detected: $(uname -s 2>/dev/null || echo unknown)" >&2
    exit 1
  fi
}

mac_resolve_eightball_root() {
  local default_root="${HOME}/Library/Application Support/8-BALL"
  local root="${EIGHTBALL_ROOT:-${default_root}}"

  if [[ "${root}" != /* ]]; then
    echo "EIGHTBALL_ROOT must be an absolute path." >&2
    exit 1
  fi
  if [[ ! -d "${root}" ]]; then
    mkdir -p "${root}"
  fi
  if [[ ! -w "${root}" ]]; then
    echo "Install state root is not writable by the current user: ${root}" >&2
    exit 1
  fi
  local owner
  owner="$(stat -c '%u' "${root}" 2>/dev/null || stat -f '%u' "${root}" 2>/dev/null || echo "")"
  if [[ -n "${owner}" && "${owner}" != "$(id -u)" ]]; then
    echo "EIGHTBALL_ROOT must be owned by the invoking user: ${root}" >&2
    exit 1
  fi
  EIGHTBALL_ROOT="${root}"
  export EIGHTBALL_ROOT
  LOG_FILE="${EIGHTBALL_ROOT}/8ball-trial.log"
  OBSERVATION_FILE="${EIGHTBALL_ROOT}/runtime-observation.json"
  RESULT_JSON="${EIGHTBALL_ROOT}/8ball-result.json"
  RESULT_FILE="${EIGHTBALL_ROOT}/8ball-result.txt"
  STATUS_BIN="${EIGHTBALL_ROOT}/bin/8ball-status"
}

mac_validate_ollama_api() {
  local api="${OLLAMA_API:-${DEFAULT_OLLAMA_API}}"
  case "${api}" in
    http://127.0.0.1:*|http://localhost:*|http://[::1]:*) ;;
    *)
      echo "OLLAMA_API must use a loopback address (127.0.0.1 or localhost). Refusing: ${api}" >&2
      exit 1
      ;;
  esac
  OLLAMA_API="${api}"
  export OLLAMA_API
}

mac_require_macos_version() {
  local version major
  version="$(sw_vers -productVersion 2>/dev/null || true)"
  major="${version%%.*}"
  if [[ -z "${major}" || "${major}" -lt "${MACOS_MIN_MAJOR_VERSION}" ]]; then
    echo "macOS ${MACOS_MIN_MAJOR_VERSION}+ is required. Detected: ${version:-unknown}" >&2
    exit 1
  fi
}

mac_require_lane_architecture() {
  local expected="${MAC_EXPECTED_ARCH:?MAC_EXPECTED_ARCH is required}"
  local actual
  actual="$(uname -m 2>/dev/null || echo unknown)"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "This lane (${MAC_TARGET_LANE:-unknown}) requires architecture ${expected}. Detected: ${actual}" >&2
    exit 1
  fi
}

mac_validate_model_tag() {
  local tag="$1"
  if [[ ! "${tag}" =~ ^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$ ]]; then
    echo "Invalid Ollama model tag: ${tag}" >&2
    exit 1
  fi
}

mac_find_repo_root() {
  local dir="${1:-$PWD}"
  while [[ "${dir}" != "/" ]]; do
    if [[ -x "${dir}/scripts/macos-observe-host.sh" ]]; then
      printf '%s' "${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  return 1
}

mac_write_observation() {
  local lane_dir="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
  local observe_script=""
  local repo_root=""
  if repo_root="$(mac_find_repo_root "${lane_dir}" 2>/dev/null)"; then
    observe_script="${repo_root}/scripts/macos-observe-host.sh"
  elif [[ -x "${lane_dir}/../../../scripts/macos-observe-host.sh" ]]; then
    observe_script="$(cd "${lane_dir}/../../../scripts" && pwd)/macos-observe-host.sh"
  fi

  mkdir -p "${EIGHTBALL_ROOT}"
  if [[ -n "${observe_script}" && -x "${observe_script}" ]]; then
    "${observe_script}" "${EIGHTBALL_ROOT}" >"${OBSERVATION_FILE}"
  else
    python3 - "${EIGHTBALL_ROOT}" <<'PY' >"${OBSERVATION_FILE}"
import json, os, subprocess, sys
root = sys.argv[1]
arch = subprocess.getoutput("uname -m").strip() or "unknown"
lane = "mac/apple-silicon" if arch == "arm64" else ("mac/intel" if arch == "x86_64" else "unknown")
print(json.dumps({
    "os_family": "macos",
    "architecture": arch,
    "target_lane": lane,
    "provider": "mac",
    "topology": "unknown",
    "os_version": subprocess.getoutput("sw_vers -productVersion").strip() or None,
    "cpu_brand": None,
    "physical_memory_mb": None,
    "free_install_disk_mb": None,
    "cpu_threads": None,
    "gpu_present": "unknown",
    "gpu_name": None,
    "gpu_memory_mb": None,
    "metal_status": "unknown",
    "cuda_status": "not_applicable",
    "install_root": root,
    "observation_status": "observed",
}, indent=2))
PY
  fi
}

mac_find_ollama_app() {
  OLLAMA_APP_PATH=""
  for candidate in "/Applications/Ollama.app" "${HOME}/Applications/Ollama.app"; do
    if [[ -d "${candidate}" ]]; then
      OLLAMA_APP_PATH="${candidate}"
      return 0
    fi
  done
  return 1
}

mac_manual_ollama_install_message() {
  cat >&2 <<EOF
Ollama for macOS is not installed.

Manual steps:
1. Download the official Ollama macOS app from ${OLLAMA_MACOS_DOCS_URL}
2. Open the DMG and drag Ollama into Applications
3. Launch Ollama once from Applications and approve the CLI link prompt if macOS asks
4. Re-run this installer as your signed-in user

The installer does not download Ollama automatically on macOS.
EOF
}

mac_require_ollama_cli() {
  if ! command -v ollama >/dev/null 2>&1; then
    mac_manual_ollama_install_message
    echo "The ollama CLI is not available in PATH. Launch Ollama from Applications and approve the CLI link prompt." >&2
    exit 1
  fi
}

mac_launch_ollama_app() {
  if [[ -z "${OLLAMA_APP_PATH:-}" ]]; then
    mac_find_ollama_app || {
      mac_manual_ollama_install_message
      exit 1
    }
  fi
  if ! curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
    mac_log "Launching Ollama app at ${OLLAMA_APP_PATH}"
    open -a "${OLLAMA_APP_PATH}" >/dev/null 2>&1 || open -a Ollama >/dev/null 2>&1 || true
  fi
}

mac_wait_for_ollama_api() {
  local attempt
  for attempt in $(seq 1 45); do
    if curl -fsS "${OLLAMA_API}/api/tags" >/dev/null 2>&1; then
      mac_log "Ollama API is responding at ${OLLAMA_API}"
      return 0
    fi
    sleep 2
  done
  echo "Ollama API did not become ready at ${OLLAMA_API}" >&2
  echo "Launch Ollama from Applications, approve the CLI link prompt if needed, then re-run." >&2
  exit 1
}

mac_load_observation_json() {
  python3 - "${OBSERVATION_FILE}" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit("missing observation")
print(json.dumps(json.loads(path.read_text(encoding="utf-8"))))
PY
}

mac_ram_gib_from_observation() {
  python3 - "${OBSERVATION_FILE}" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
mb = data.get("physical_memory_mb")
if not isinstance(mb, int) or mb <= 0:
    print("0")
else:
    print(mb // 1024)
PY
}

mac_free_disk_gib_from_observation() {
  python3 - "${OBSERVATION_FILE}" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
mb = data.get("free_install_disk_mb")
if not isinstance(mb, int) or mb <= 0:
    print("0")
else:
    print(mb // 1024)
PY
}

mac_build_candidate_ladder() {
  local ram_gib="$1"
  if [[ "${ram_gib}" -ge 24 ]]; then
    printf '%s\n' "qwen3:14b" "qwen3:8b" "qwen3:4b" "qwen3:1.7b" "qwen3:0.6b"
  elif [[ "${ram_gib}" -ge 12 ]]; then
    printf '%s\n' "qwen3:8b" "qwen3:4b" "qwen3:1.7b" "qwen3:0.6b"
  elif [[ "${ram_gib}" -ge 8 ]]; then
    printf '%s\n' "qwen3:4b" "qwen3:1.7b" "qwen3:0.6b"
  elif [[ "${ram_gib}" -ge 4 ]]; then
    printf '%s\n' "qwen3:1.7b" "qwen3:0.6b"
  else
    printf '%s\n' "qwen3:0.6b"
  fi
}

mac_disk_guard_gib() {
  case "$1" in
    qwen3:14b) echo 14 ;;
    qwen3:8b) echo 9 ;;
    qwen3:4b) echo 6 ;;
    qwen3:1.7b) echo 4 ;;
    qwen3:0.6b) echo 3 ;;
    *) echo 0 ;;
  esac
}

mac_filter_candidates_by_disk() {
  local free_disk="$1"
  local candidate
  while IFS= read -r candidate; do
    [[ -z "${candidate}" ]] && continue
    local need
    need="$(mac_disk_guard_gib "${candidate}")"
    if [[ "${free_disk}" -ge "${need}" ]]; then
      printf '%s\n' "${candidate}"
    fi
  done
}

mac_list_installed_models() {
  ollama list 2>/dev/null | awk 'NR>1 {print $1}' || true
}

mac_model_was_installed_before() {
  local model="$1"
  grep -Fxq "${model}" "${EIGHTBALL_ROOT}/.models-before-trial" 2>/dev/null
}

mac_record_models_before_trial() {
  mac_list_installed_models >"${EIGHTBALL_ROOT}/.models-before-trial"
}

mac_test_model_generate() {
  local model="$1"
  local response
  response="$(
    curl -fsS "${OLLAMA_API}/api/generate" \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"${model}\",\"prompt\":\"Reply with only: 8-BALL READY\",\"stream\":false}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("response",""))'
  )" || return 1
  grep -qi "8-BALL READY" <<<"${response}"
}

mac_remove_model_if_new() {
  local model="$1"
  if mac_model_was_installed_before "${model}"; then
    mac_log "Keeping pre-existing model ${model}"
    return 0
  fi
  mac_log "Removing newly pulled model that failed verification: ${model}"
  ollama rm "${model}" >/dev/null 2>&1 || true
}

mac_write_result_record() {
  local model="$1" status="$2" acceleration="$3"
  python3 - "${RESULT_JSON}" "${RESULT_FILE}" "${model}" "${status}" "${acceleration}" "${MAC_TARGET_LANE}" "${OLLAMA_API}" "${OBSERVATION_FILE}" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

result_json, result_txt, model, status, acceleration, lane, api, obs_path = sys.argv[1:9]
obs = json.loads(Path(obs_path).read_text(encoding="utf-8")) if Path(obs_path).is_file() else {}
payload = {
    "selected_model": model,
    "test_status": status,
    "acceleration": acceleration,
    "lane": lane,
    "ollama_api": api,
    "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "observation": {
        "architecture": obs.get("architecture"),
        "physical_memory_mb": obs.get("physical_memory_mb"),
        "free_install_disk_mb": obs.get("free_install_disk_mb"),
        "cpu_threads": obs.get("cpu_threads"),
        "metal_status": obs.get("metal_status"),
        "gpu_memory_mb": obs.get("gpu_memory_mb"),
        "target_lane": obs.get("target_lane"),
    },
}
Path(result_json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
lines = [
    f"Model: {model}",
    f"Install lane: {lane}",
    f"Acceleration: {acceleration}",
    f"Model test: {status}",
    f"Ollama API: {api}",
    f"Architecture: {obs.get('architecture', 'unknown')}",
    f"RAM MB: {obs.get('physical_memory_mb', 'unknown')}",
    f"Free disk MB: {obs.get('free_install_disk_mb', 'unknown')}",
    f"CPU threads: {obs.get('cpu_threads', 'unknown')}",
    f"Metal status: {obs.get('metal_status', 'unknown')}",
    "Jets status: OPTIONAL_AFTER_SIGNIN",
]
Path(result_txt).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

mac_write_status_helper() {
  mkdir -p "${EIGHTBALL_ROOT}/bin"
  cat >"${STATUS_BIN}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="${EIGHTBALL_ROOT}"
RESULT="\${ROOT}/8ball-result.txt"
API="${OLLAMA_API}"
echo "8-BALL status"
echo "State root: \${ROOT}"
echo "Result file: \${RESULT}"
if [[ -f "\${RESULT}" ]]; then
  cat "\${RESULT}"
else
  echo "No result file yet. Run trial-install.sh first."
fi
echo "Local endpoint: \${API}"
echo "Jets: optional; run 'ollama signin' separately if you want cloud models."
echo "Status helper: \${ROOT}/bin/8ball-status"
EOF
  chmod +x "${STATUS_BIN}"
}
