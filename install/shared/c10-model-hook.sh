#!/usr/bin/env bash
# C10 model selection helpers for 8.2.sh
set -euo pipefail

c10_resolve_repo_root() {
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
  c10_resolve_repo_root || return 1
  local selector="${REPO_ROOT}/install/shared/c10-select-model.py"
  if [[ ! -f "${selector}" ]]; then
    return 1
  fi
  python3 "${selector}" "${slug}" "${lane}" "${REPO_ROOT}/${assumption}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["selected_ollama_ref"])'
}

c10_fallback_pull() {
  local slug="$1"
  local lane="${EIGHTBALL_INSTALL_LANE:-${EIGHTBALL_INSTALL_PROFILE:-ubuntu/cpu}}"
  c10_resolve_repo_root || return 1
  local page="${REPO_ROOT}/profiles/${slug}.json"
  [[ -f "${page}" ]] || return 1
  python3 - "${page}" <<'PY'
import json, sys
from pathlib import Path
sizes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("sizes", [])
for size in reversed(sizes):
    print(size["ollama_ref"])
PY
}
