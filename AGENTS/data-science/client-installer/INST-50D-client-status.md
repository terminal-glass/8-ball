# INST-50D — 8.3 Customer Status / MOTD

**Date:** 2026-08-13  
**Contract:** `AGENTS/INST-client-installer-scaffolding.md`  
**Prior stage:** `INST-50C-profile-integration.md`  
**Scope:** 8.3 customer-visible status, MOTD, alerts, bulletin handoff

---

## Implementation Completed

### Authoritative status evaluator (`install/shared/8ball-client-status.py`)

- Consumes INST-50C `${PHILOSOPHER_ROOT}/8ball-result.json` (falls back to `8ball-result.txt`).
- Separates three facts:
  - **Selected model** — from 8.2 result artifact
  - **Installed** — exact match against Ollama `/api/tags` (not loose substring)
  - **Inference proven** — `inference_succeeded` / `Model test: PASSED`
- Derives customer `local_model_status`:
  - `NOT CONFIGURED`, `UNAVAILABLE`, `FAILED`, `PARTIAL`, `MISSING`, `READY`
- Derives independent `jets_status`:
  - `UNAVAILABLE`, `PARTIAL`, `SIGN-IN REQUIRED`
- Login path performs **no** `ollama pull`, `ollama run`, resolver, or network I/O.

### Known regression fixed

**Before:** MOTD could show `Local Model ........ MISSING` while displaying `Local: ollama run qwen3:1.7b` because:
- Model presence used fragile `ollama list` matching (PATH/substring issues)
- Selected / installed / proven states were collapsed

**After:** `READY` requires Ollama running + selected model present (exact API match) + inference proven. `MISSING` only when proven model is no longer installed.

### 8.3 orchestration (`install/ubuntu/8.3.sh`)

- MOTD script calls `8ball-client-status.py render-motd` (local only).
- Bulletin refresh moved to async `8ball-bulletin-refresh.sh` + systemd timer.
- Login displays cached `${PHILOSOPHER_ROOT}/8ball-bulletin.txt` only (no curl at login).
- Temp alert decrement centralized in status helper (root-owned `0640` meta).
- Alert history no longer truncated on repeat `8.3` runs.
- `remember` + status helpers respect `${EIGHTBALL_BIN_DIR}`.
- `${EIGHTBALL_MOTD_TARGET}` override for tests; `${EIGHTBALL_TEST_SKIP_ROOT}` supported.

### MOTD template (`install/ubuntu/assets/first-MOTD.txt`)

- `__JETS_STATUS__` is now dynamic (was hard-coded `READY AFTER SIGN-IN`).

---

## Result Contract Consumed (from INST-50C)

| Field | Use in 8.3 |
| --- | --- |
| `selected_model` | Display + install check target |
| `profile_id` | Support context (not re-derived) |
| `inference_succeeded` / `test_status` | Proven vs failed |
| `jets_status` | Jets line hint |

Human-readable `8ball-result.txt` retained for support workflows.

---

## Generic X Behavior

Status logic is model-family neutral. Tests cover `qwen3:1.7b` (Y regression fixture) and `tinyllama:1.1b` / `gemma2:2b` (X paths) without production branches.

---

## Bulletin / Alert Changes

| Component | Behavior |
| --- | --- |
| `8ball-bulletin-refresh.service` + `.timer` | Async refresh every 6h; oneshot script at `${PHILOSOPHER_ROOT}/bin/` |
| MOTD login | Reads cached bulletin file only |
| `8ball-temp-alert.meta` | `0640` root:adm; decremented via status helper |
| `8ball-alert-history` | Append-only; not reset by idempotent 8.3 |

---

## Tests Performed

| Check | Result |
| --- | --- |
| `bash -n` (8.3.sh, bulletin refresh) | PASS |
| `pytest tests/test_inst_50d_client_status.py` | PASS (14 tests, mocked) |
| Full `pytest` | PASS (395 passed, 8 skipped) |

### Coverage highlights (mocked)

- Qwen `qwen3:1.7b` READY regression + real MISSING case
- Exact tag matching (no `qwen3:0.6b` false positive)
- Generic X (`tinyllama`, `gemma2`)
- Ollama unavailable / inference failed / partial installed
- Jets sign-in vs unavailable
- MOTD script forbids pull/run/resolver/curl at login
- Idempotent 8.3 install
- Temp alert decrement

---

## NEEDS REAL VM TESTING

| Scenario | Why |
| --- | --- |
| Actual SSH login MOTD display | Mocked render only |
| Live `ollama list` / `/api/tags` on customer host | API format edge cases |
| systemd bulletin timer firing | Requires systemd + network |
| Offline login with stale/missing bulletin | Requires disconnected VM |
| Multi-login temp-alert counter | Requires repeated SSH sessions |
| Real Jets signed-in vs signed-out | Per-user Ollama cloud auth state |
| File ownership on `/opt/philosopher` after install | Requires root VM |

---

## Handoff to INST-50E

- Release pinning / remote script SHA verification unchanged (INST-50E scope).
- `8ball-result.json` + `8ball-result.txt` remain the support contract for trial-install integrity checks.
- Bulletin URL configuration (`EIGHTBALL_BULLETIN_URL`) can be wired during release hardening.

---

## Revision History

| Date | Notes |
| --- | --- |
| 2026-08-13 | Initial INST-50D implementation record |
