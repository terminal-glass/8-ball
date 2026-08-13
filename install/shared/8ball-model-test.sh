#!/usr/bin/env bash
# Shared model pull, inference test, and fallback helpers for 8.2.sh
set -euo pipefail

eightball_list_installed_models() {
  ollama list 2>/dev/null | awk 'NR>1 {print $1}'
}

eightball_model_is_installed() {
  local model="$1"
  local listed candidate base tag
  [[ -n "${model}" ]] || return 1
  while IFS= read -r listed; do
    [[ -z "${listed}" ]] && continue
    if [[ "${listed}" == "${model}" ]]; then
      return 0
    fi
    if [[ "${listed}" == "${model}"* ]]; then
      return 0
    fi
    base="${model%%:*}"
    tag="${model#*:}"
    if [[ "${tag}" != "${model}" && "${listed}" == "${base}" ]]; then
      return 0
    fi
    if [[ "${listed}" == "${base}:${tag}"* ]]; then
      return 0
    fi
  done < <(eightball_list_installed_models)
  return 1
}

eightball_models_before_pull() {
  eightball_list_installed_models | sort -u
}

eightball_remove_if_newly_pulled() {
  local model="$1"
  local before_file="$2"
  if grep -Fxq "${model}" "${before_file}" 2>/dev/null; then
    return 0
  fi
  ollama rm "${model}" >/dev/null 2>&1 || true
}

eightball_validate_model_name() {
  local model="$1"
  if [[ ! "${model}" =~ ^[A-Za-z0-9._:@/+-]+$ ]]; then
    echo "Invalid model name: ${model}" >&2
    return 1
  fi
  return 0
}

eightball_test_model_inference() {
  local model="$1"
  local response=""
  response="$(
    curl -fsS "${OLLAMA_API}/api/generate" \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"${model}\",\"prompt\":\"Reply with only: 8-BALL READY\",\"stream\":false}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("response",""))'
  )" || return 1
  if grep -qi "8-BALL READY" <<<"${response}"; then
    return 0
  fi
  printf '[8.2] Model response did not contain expected token: %s\n' "${response}" >&2
  return 1
}

eightball_pull_and_test() {
  local model="$1"
  local before_file="$2"
  if ! eightball_validate_model_name "${model}"; then
    return 1
  fi
  if ! ollama pull "${model}"; then
    return 1
  fi
  if eightball_test_model_inference "${model}"; then
    return 0
  fi
  eightball_remove_if_newly_pulled "${model}" "${before_file}"
  return 1
}
