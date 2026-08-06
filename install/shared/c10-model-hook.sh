#!/usr/bin/env bash
# C10 model selection helpers for 8.2.sh
set -euo pipefail

c10_resolve_repo_root() {
  if [[ -n "${EIGHTBALL_REPO_ROOT:-}" && -d "${EIGHTBALL_REPO_ROOT}/profiles" ]]; then
    REPO_ROOT="${EIGHTBALL_REPO_ROOT}"
    return 0
  fi
  local dir="${SCRIPT_DIR}"
  while [[ "${dir}" != "/" ]]; do
    if [[ -d "${dir}/profiles" && -d "${dir}/install" ]]; then
      REPO_ROOT="${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  return 1
}

c10_select_model_slug() {
  local slug="$1"
  local lane="${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE:-ubuntu/cpu}}"
  local assumption="${EIGHTBALL_PROVIDER_ASSUMPTION:-profiles/provider-assumptions/ubuntu-cpu.json}"
  local selector=""
  local result=""
  local selected=""
  local status=""

  if [[ -n "${EIGHTBALL_PROFILES_BASE:-}" ]]; then
    selector="${EIGHTBALL_PROFILES_BASE%/}/install/shared/c10-select-model.py"
    if [[ "${selector}" == http* ]]; then
      local tmp
      tmp="$(mktemp)"
      curl -fsSL "${selector}" -o "${tmp}"
      selector="${tmp}"
    fi
  else
    c10_resolve_repo_root || return 1
    selector="${REPO_ROOT}/install/shared/c10-select-model.py"
  fi
  [[ -f "${selector}" ]] || return 1

  if ! result="$(python3 "${selector}" "${slug}" "${lane}" "${assumption}")"; then
  echo "${result}" >&2
  return 1
  fi
  selected="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("selected_ollama_ref") or "")' <<<"${result}")"
  status="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("selection_status",""))' <<<"${result}")"
  if [[ -z "${selected}" || "${status}" != "selected" ]]; then
    echo "${result}" >&2
    return 1
  fi
  printf '%s' "${selected}"
}

c10_fallback_pull() {
  local slug="$1"
  local lane="${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE:-ubuntu/cpu}}"
  local lane_json=""
  if [[ -n "${EIGHTBALL_PROFILES_BASE:-}" && "${EIGHTBALL_PROFILES_BASE}" == http* ]]; then
    lane_json="$(curl -fsSL "${EIGHTBALL_PROFILES_BASE%/}/profiles/${slug}/${lane}/lane.json")"
    python3 - "${lane_json}" <<'PY'
import json, sys
lane = json.loads(sys.argv[1])
for row in reversed(lane.get("size_fit", [])):
    if row.get("fit_status") == "fit" and row.get("fits"):
        print(row["ollama_ref"])
PY
    return 0
  fi
  c10_resolve_repo_root || return 1
  lane_json="${REPO_ROOT}/profiles/${slug}/${lane}/lane.json"
  [[ -f "${lane_json}" ]] || return 1
  python3 - "${lane_json}" <<'PY'
import json, sys
from pathlib import Path
lane = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for row in reversed(lane.get("size_fit", [])):
    if row.get("fit_status") == "fit" and row.get("fits"):
        print(row["ollama_ref"])
PY
}
