# INST-50C — 8.2 Profile / Model Integration

**Date:** 2026-08-13  
**Contract:** `AGENTS/INST-client-installer-scaffolding.md`  
**Prior stage:** `INST-50B-foundation.md`  
**Scope:** 8.2 data-driven profile/model selection only

---

## Implementation Completed

### Canonical resolver (`install/shared/c10-hardware-resolve.py`)

- Uses `scripts/c10_common.py` `evaluate_lane_fit()` for **runtime** hardware evaluation (not static `lane.json` `fit_status` flags).
- Converts detected hardware to C10 lane hardware (`hardware_c10`).
- Resolves model slug from, in order: `--slug` → `EIGHTBALL_MODEL_SLUG` → `--model` prefix → `8ball-base-pilot-menu.json` reference (Y) → `install-manifest.json` reference.
- Builds ordered candidates from `profiles/<slug>/sizes/*.json` (largest-fit-first among runtime `fit` rows).
- Falls back to `install-manifest.json` deployment entries only when profile runtime fit yields no candidates.
- Manual `--model` produces a single candidate with explicit `manual_selection_status` (`approved`, `rejected-by-gates`, `unknown-metadata`).
- Disk thresholds come from `sizes[].estimated.min_disk_gb` (no Qwen regex heuristics).
- Fails closed when slug or approved candidates cannot be resolved.

### 8.2 execution engine (`install/ubuntu/8.2.sh`)

- Removed default `MODEL_SLUG=qwen3`.
- Removed `c10_select_model_slug` collapse that forced a single-model manual path.
- Passes `--manifest` to resolver; writes `${PHILOSOPHER_ROOT}/8ball-result.json` for 8.3 handoff.
- Automatic path consumes ordered resolver candidates with pull + real inference per candidate.
- Disk gate re-check before pull when profile metadata supplies `minimum_disk_mib`.
- Manual `--model` is deterministic: no silent fallback to Qwen; gate rejection fails explicitly.
- Unknown manual metadata proceeds without invented RAM/VRAM/disk requirements.
- Structured attempt log in result JSON (`attempts`, `fallback_chain`, `profile_id`, `inference_succeeded`).
- `8balljets` helper installs to `${EIGHTBALL_BIN_DIR:-/usr/local/bin}` (test-friendly).

### Trial entrypoint (`install/ubuntu/trial-install.sh`)

- Removed default `MODEL_SLUG=qwen3`.
- Passes `--model-slug` only when explicitly provided.

### Model-specific logic removed from Bash

| Removed / reduced | Replacement |
| --- | --- |
| `MODEL_SLUG=qwen3` defaults | Data-driven slug resolution |
| `pilot_menu_candidates()` Qwen ladder as primary path | Runtime profile fit + manifest fallback |
| `lane_fit_candidates()` static `lane.json` flags | `evaluate_profile_candidates()` via `c10_common` |
| `minimum_disk_mib()` Qwen regex heuristics | `sizes[].estimated.min_disk_gb` |
| `c10_select_model_slug` pre-collapse | Resolver candidate chain |

### Retained (execution, not model knowledge)

- `eightball_pull_and_test`, `eightball_remove_if_newly_pulled`, `eightball_models_before_pull`
- Candidate chain loop, manual override path, Ollama API sanity check
- CPU/CUDA thin lane wrappers (delegate to canonical `install/ubuntu/8.2.sh`)

---

## Canonical Interface Used

```text
hardware facts (detected or EIGHTBALL_* env)
        ↓
c10-hardware-resolve.py plan
        ↓
profile_id, candidates[], fallback_chain[], minimum_disk_mib{}
        ↓
8.2.sh: gate → pull → inference → fallback
        ↓
8ball-result.txt + 8ball-result.json
```

Resolver contract fields consumed by 8.2:

- `profile_id`, `model_slug`, `selection_source`
- `candidates` (ordered)
- `minimum_disk_mib`
- `manual_selection_status`, `manual_rejection_reason`
- `fallback_chain` (evidence for 8.3 / logs)

---

## Y / X Status

| Path | Status |
| --- | --- |
| **Y (Qwen reference)** | Automatic installs resolve `qwen3` via `8ball-base-pilot-menu.json` when no slug is given; runtime profile fit selects Qwen sizes. |
| **X (arbitrary approved model)** | `--model-slug tinyllama` (or any profiled slug) uses the same engine with no Qwen branches in 8.2. |
| **Manual X** | `--model <ollama-ref>` is deterministic; no automatic fallback. |

---

## Model #201 Question

**Can model #201 be added through approved data without modifying `8.2.sh`?**

**YES** — with the current profile tree contract.

Adding model #201 requires:

1. `profiles/<slug>/model.json` and `profiles/<slug>/sizes/*.json` with `estimated` resource fields.
2. `profiles/<slug>/<lane>/lane.json` for each supported lane.
3. Optional `install-manifest.json` deployment entries for manifest fallback.

No `8.2.sh` edit is required for a new approved family slug.

**Remaining limitation:** models without profile size records cannot receive invented resource gates; manual `--model` for unknown metadata is marked `unknown-metadata` and proceeds without fake thresholds.

---

## Tests Performed

| Check | Result |
| --- | --- |
| `bash -n` (8.2.sh, trial-install.sh) | PASS |
| `scripts/test-installer-harness.sh` | PASS (8 pass, 11 NOT TESTED) |
| `python3 scripts/validate-install-lanes.py` | PASS |
| `pytest tests/test_inst_50c_profile_integration.py` | PASS (23 tests, mocked) |
| Full `pytest` | PASS (381 passed, 8 skipped) |

### INST-50C test coverage (mocked)

- Resolver runtime fit (Qwen Y, tinyllama X)
- Ordered largest-fit-first candidates
- RAM/disk gates at resolver
- Manual `--model` gate rejection and no-fallback
- Unknown metadata handling
- Missing slug fail-closed
- Pull failure → fallback; inference failure → cleanup + fallback
- Pre-existing model protection
- Result JSON contract for 8.3
- CPU/CUDA wrapper delegation

---

## Data-Contract Gaps

| Gap | Behavior |
| --- | --- |
| Models without `estimated.min_disk_gb` | No disk gate applied (unknown, not invented) |
| `EIGHTBALL_PROFILES_BASE` HTTP remote | Not implemented in resolver (deferred INST-50E) |
| Manifest fallback ordering | Manifest order preserved; not re-ranked by runtime fit |

---

## NEEDS REAL VM TESTING

| Scenario | Why |
| --- | --- |
| Actual model downloads and inference | Mocked in CI |
| Real RAM pressure / swap interaction | Requires host |
| CUDA/VRAM profile resolution on GPU host | Requires NVIDIA VM |
| Fallback after real inference failure | Requires Ollama + weights |
| Provider images (Lightsail, DigitalOcean) | Cloud lane matrix (INST-50F) |
| Idempotent re-run with pre-existing customer models | Requires root + prior state |

---

## Handoff to INST-50D

After successful 8.2:

- `${PHILOSOPHER_ROOT}/8ball-result.txt` — human-readable summary
- `${PHILOSOPHER_ROOT}/8ball-result.json` — machine-readable contract:

```json
{
  "selected_model": "...",
  "test_status": "PASSED|FAILED",
  "profile_id": "<slug>/<lane>",
  "selection_source": "...",
  "inference_succeeded": true,
  "attempts": [...],
  "fallback_chain": [...]
}
```

8.3 should read these artifacts; 8.3 must not re-run model selection.

---

## Revision History

| Date | Notes |
| --- | --- |
| 2026-08-13 | Initial INST-50C implementation record |
