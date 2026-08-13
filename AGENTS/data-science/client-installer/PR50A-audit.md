# PR50A — 8-BALL Client Installer Audit and Recovery

Date: 2026-08-13  
Audited branch: `cursor/8ball-launch-hardening-1896` (PR #50)  
Base branch: `main`  
Auditor scope: read-only audit; no PR50B–PR50F implementation

---

## 1. PR 50 Summary

PR #50 attempted to move the public 8-BALL trial installer (`trial-install.sh → 8.1 → 8.2 → 8.3`) toward **0.8.0 launch hardening** by:

- Extracting shared modules under `install/shared/` (version contract, Ollama localhost enforcement, model test helpers, hardware resolve, release helpers)
- Hardening canonical `install/ubuntu/{8.1,8.2,8.3,trial-install}.sh`
- Replacing duplicated `install/ubuntu/cpu/` and `install/ubuntu/cuda/` scripts with thin wrappers to the canonical scripts
- Adding release manifest scaffolding (`install/releases/v0.8.0/manifest.json`)
- Adding offline test harness, pytest checks, Proxmox matrix doc, and AGENTS reports

The PR **does not** complete client-installer integration. It introduces a **partial** bridge from C10 profile artifacts into 8.2, but that bridge bypasses several authoritative C10/C10.1 contracts and regresses parts of the prior manifest-based path.

---

## 2. Files Changed

| Category | Paths |
| --- | --- |
| Shared installer libs (new) | `install/shared/8ball-version.sh`, `ollama-localhost.sh`, `8ball-model-test.sh`, `8ball-release.sh`, `c10-hardware-resolve.py` |
| Canonical Ubuntu scripts | `install/ubuntu/8.1.sh`, `8.2.sh`, `8.3.sh`, `trial-install.sh` |
| Ubuntu lane wrappers | `install/ubuntu/cpu/*.sh`, `install/ubuntu/cuda/*.sh` (replaced full copies with `exec` wrappers) |
| Release integrity | `install/releases/v0.8.0/manifest.json`, `scripts/generate-release-manifest.sh` |
| Tests / harness | `scripts/test-installer-harness.sh`, `tests/test_installer_hardening.py`, `tests/test_install_lane_conformance.py` |
| Validation | `scripts/validate-install-lanes.py` (removed ubuntu/cpu+cuda legacy-debt entries) |
| Docs / reports | `AGENTS/reports/8ball-0.8-launch-*.md`, `docs/proxmox-launch-test-matrix.md` |

**Not changed by PR 50:** cloud lane scripts (`install/cloud/**`), Mac/Windows lanes, root `trial-install.sh` dispatcher (beyond what was already on main), C-series AGENTS data, `profiles/` tree, `data/generated/pages/install-manifest.json`.

---

## 3. KEEP

| Item | Rationale |
| --- | --- |
| Shared module extraction pattern (`install/shared/`) | Correct direction; reduces duplication across lanes |
| Version contract skeleton (`8ball-version.sh`, `EIGHTBALL_SCRIPT_VERSION`) | Needed for PR50E; implementation needs tightening |
| `8ball-model-test.sh` inference test + remove-only-newly-pulled-model logic | Matches C4 requirement; preserves pre-existing user models |
| Ubuntu cpu/cuda thin wrappers to canonical scripts | Reduces drift; lane env vars (`EIGHTBALL_INSTALL_LANE`) preserved |
| `generate-release-manifest.sh` + manifest file format | Correct release mechanism shape for PR50E |
| 8.3 MOTD checking `ollama list` for READY/MISSING (vs result-file-only) | Addresses observed customer bug class |
| 8.3 alert meta `0640` instead of world-writable | Permission improvement |
| 8.3 login-time MOTD remains network-free | Correct |
| `remember` helper unchanged and appropriate | SAFE |
| Offline harness + honest NOT TESTED labels in harness output | Good practice |
| Proxmox matrix doc | Useful for PR50F |
| Removal of stale legacy-debt entries for modernized ubuntu/cpu+cuda wrappers | Accurate debt accounting |

---

## 4. REPAIR

| Item | Issue | Required fix stage |
| --- | --- | --- |
| **8.1 localhost verification** | `ollama_verify_listener()` passes if loopback is reachable **or** falls back to `curl` API probe. API reachability at `127.0.0.1:11434` does **not** prove exclusive localhost bind. If `ss` is missing and Ollama listens on `0.0.0.0:11434`, curl to loopback can still succeed. | PR50B |
| **8.1 dual-bind blind spot** | If Ollama listens on both `127.0.0.1:11434` and `0.0.0.0:11434`, current `ss` logic returns success on first loopback match without failing the public listener. | PR50B |
| **8.1 override handling** | Public-bind detection only greps explicit `0.0.0.0`/`[::]` in known config paths. Misses `OLLAMA_HOST=:11434`, unit `EnvironmentFile` indirection, socket activation, or non-systemd installs where `nohup ollama serve` may ignore the drop-in. | PR50B |
| **8.1 ordering** | `ollama_ensure_localhost` runs before `start_ollama`, but `start_ollama` can return early when API already responds **without** re-verifying bind after restart. | PR50B |
| **8.2 default install path** | `trial-install.sh` defaults `MODEL_SLUG=qwen3`, which causes 8.2 to call `c10_select_model_slug`, set a single `REQUESTED_MODEL`, and enter `run_manual_override` — **skipping the candidate fallback chain** on the default customer install. | PR50C |
| **8.2 profile consumption** | Reads `profiles/qwen3/<lane>/lane.json` `size_fit` rows marked `fit`, but those fits are **precomputed against static provider-assumption hardware** (e.g. ubuntu-cpu 16 GB / 9 GB usable), not runtime-observed host facts per C10.1 observation contract. | PR50C |
| **8.2 lane resolution** | `resolve_lane()` is a small hard-coded Bash/Python branch (cloud heuristics + CUDA VRAM ≥ 6 GB). Does not use `profiles/provider-compatibility/*/runtime-observation-contract.json` or taxonomy projections. | PR50C |
| **8.2 RAM bands** | `pilot_menu_candidates()` duplicates RAM ladder logic inline (4096/8192/12288/24576 thresholds) instead of consuming taxonomy band IDs from C10.1-10. | PR50C |
| **8.2 disk gates** | `minimum_disk_mib()` only applied on manual `--model` path; automatic candidate chain does not skip candidates when free disk is insufficient. | PR50C |
| **8.2 result `Profile` field** | `Profile: ${model//[:\/]/-}` is derived from the Ollama tag, not from resolved profile/lane identity. Misleading for support. | PR50C |
| **8.2 `--manifest` flag** | Still parsed and written to result file, but **`install-manifest.json` is no longer used for selection**. Regresses documented contract in `install/README.md` and `docs/install-manifest-contract.md`. | PR50C |
| **8.2 remote/curl install** | `c10-hardware-resolve.py` requires local `profiles/` tree via `find_repo_root()`. Does not honor `EIGHTBALL_PROFILES_BASE` for lane/plan resolution. Curl-only script install cannot select models without full repo checkout. | PR50C / PR50E |
| **trial-install version mismatch** | `verify_local_bundle` logs a warning on mismatch but **continues**. Customer can silently run mixed versions. | PR50E |
| **Release SHA verification** | Only runs when local `install/releases/${EIGHTBALL_RELEASE}/manifest.json` exists. Remote curl bootstrap has no embedded or fetched checksum source; `v0.8.0` tag not published. | PR50E |
| **8.3 MOTD model matching** | Prefix/wildcard matching (`listed == model*`) may false-positive on similarly named models; no digest-level check. | PR50D |
| **8.3 temp-alert decrement** | MOTD runs as root via `update-motd.d`; meta is `0640 root:adm`. Decrement path is fragile (`-w` check, `runuser` fallback) and untested on real login. | PR50D |
| **8.3 bulletin** | No systemd timer; install-time optional curl only. Offline placeholder is fine, but weekly refresh spec from C4 is not implemented. | PR50D (optional) |
| **8.3 `--no-motd` on 8.3.sh** | 8.3 supports `--no-motd` internally, but `trial-install.sh --no-motd` skips calling 8.3 entirely — so trial marker, alerts, and permissions are not applied. | PR50D |

---

## 5. REVERT

| Item | Reason |
| --- | --- |
| **Default `MODEL_SLUG=qwen3` in `trial-install.sh`** | Forces all default installs through `--model-slug` → single-model manual override path. Conflicts with intended candidate-chain + inference-proof architecture. Revert to empty default unless user explicitly requests a slug. |
| **8.2 removal of `install-manifest.json` selection path** | Until profile integration is correct, removing the manifest path breaks the documented catalog contract and curl-friendly fallback. Should be restored as secondary/fallback authority until PR50C fully replaces it. |
| **Overstated claims in `AGENTS/reports/8ball-0.8-launch-hardening-report.md`** | Report states “profile integration” and “launch hardening complete” beyond evidence. Do not treat as authoritative; supersede with this audit. |

No full script revert recommended — most changes are directionally correct but incomplete.

---

## 6. NOT IMPLEMENTED

Required launch-hardening work PR 50 did **not** deliver:

| Area | Gap |
| --- | --- |
| Runtime observation contract | No consumption of `profiles/provider-compatibility/ubuntu/runtime-observation-contract.json` or per-stage evidence (`3-cpu`, `4-ram`, `5-hard_disk`, `7-video_card`) |
| C10.1 taxonomy / band projection | No use of `host-capability-categories.json`, `lane-runtime-contract-projection.json`, or RAM-band IDs |
| `c10-select-model.py` integration | Existing C10 selector not used in default path; only called to collapse selection to one model |
| Provider assumption runtime join | `provider-assumptions/*.json` referenced in output but not used to evaluate fit at install time |
| Cloud lane hardening | `install/cloud/**` unchanged |
| Mac/Windows installer integration | Unchanged |
| Published `v0.8.0` git tag + remote manifest fetch | Manifest exists only in repo checkout |
| Bundle mismatch hard-fail | Version check warns, does not stop |
| Systemd bulletin timer | Not present |
| Jets signed-in vs partial state | MOTD template hardcodes `READY AFTER SIGN-IN`; no PARTIAL detection (user-reported PARTIAL may be from an older/private build — not in PR 50 branch) |
| Real VM / GPU validation | Explicitly not done |
| `trial-installed` marker write from `trial-install.sh` | Only written by 8.3; skipped when `--no-motd` |

---

## 7. Profile Integration Status

### Verdict: **PARTIAL — not genuine C10 consumption**

PR 50 **does read** some C10-generated artifacts:

| Artifact | Used? | How |
| --- | --- | --- |
| `profiles/qwen3.json` | Yes | Size ordering for candidate sort |
| `profiles/qwen3/<lane>/lane.json` | Yes | `size_fit` rows with `fit_status=fit` |
| `AGENTS/.../8ball-base-pilot-menu.json` | Yes | RAM-band fallback candidate list |
| `profiles/provider-assumptions/*.json` | Label only | Path recorded in result file, not evaluated |
| `install/shared/c10-select-model.py` | Marginal | Called on `--model-slug`; collapses to one model |
| `data/generated/pages/install-manifest.json` | **No** | Removed from selection (regression) |
| `profiles/provider-compatibility/**` | **No** | Ignored |
| C10 stage JSON (`3-cpu`, `4-ram`, etc.) | **No** | Ignored |
| C10.1 ubuntu runtime taxonomy / observation contract | **No** | Ignored |
| `scripts/c10_ubuntu_compatibility.py` outputs | **No** | Ignored |

### Critical architectural gaps

1. **Static fit, not runtime fit.** `lane.json` fit rows were generated against assumed client-class hardware (e.g. ubuntu-cpu 9 GB usable RAM). PR 50 treats every `fit_status=fit` row as install-time approved for the **actual** host. On a 4 GB VM, the candidate list can still lead with large qwen3 variants that only fit the assumed class.

2. **Default install bypasses fallback chain.** Because `MODEL_SLUG` defaults to `qwen3`, the installer typically selects one model via `c10_select_model_slug` and runs manual override — **not** the pull → infer → fallback loop across approved candidates.

3. **Profile label is cosmetic.** Result file `Profile:` is derived from the model tag, not from resolved lane/profile identity.

4. **New parallel sizing logic.** `c10-hardware-resolve.py` embeds RAM thresholds, cloud heuristics, and disk heuristics — duplicating C10.1 planning data instead of consuming it as the single source of truth.

**Conclusion for PR50C:** Must wire hardware detection → observation contract → runtime taxonomy/band → existing lane/stage JSON → candidate list → disk gates → pull → inference proof → fallback. Must not rely on static `fit` flags alone. Must restore manifest path as fallback until profile path is proven on VMs.

---

## 8. Customer Installer Status

| Component | Status | Reason |
| --- | --- | --- |
| `trial-install.sh` | **PARTIAL** | Chain 8.1→8.2→8.3 intact; version/SHA scaffolding added but bundle mismatch is non-fatal; default `MODEL_SLUG=qwen3` skews 8.2 behavior; remote curl install still cannot resolve profiles without full repo |
| `8.1.sh` | **PARTIAL** | Good intent on localhost drop-in and logging; cannot **guarantee** exclusive localhost bind; API probe fallback is insufficient proof |
| `8.2.sh` | **FAIL** | Does not genuinely consume C10 profile system at runtime; regresses manifest selection; default path skips fallback chain; curl-only installs broken for model selection |
| `8.3.sh` | **PARTIAL** | Fixes READY/MISSING vs `ollama list` (main bug class); permissions improved; Jets status still static; bulletin/timer incomplete; `--no-motd` skips all 8.3 state setup |

---

## 9. Testing Confidence

| Claim / test | Classification |
| --- | --- |
| `bash -n` on installer scripts | **STATIC TESTED** |
| `pytest tests/test_installer_hardening.py` | **STATIC TESTED** (JSON plan generation in repo checkout only) |
| `c10-hardware-resolve.py plan` | **STATIC TESTED** (no Ollama, no real hardware variance) |
| `scripts/test-installer-harness.sh` | **STATIC TESTED** (explicitly skips live paths) |
| `validate-install-lanes.py` | **STATIC TESTED** |
| `validate-catalog.sh` / full pytest (313) | **STATIC TESTED** (catalog tests, not installer VM tests) |
| ShellCheck | **NOT TESTED** |
| First/idempotent install | **NOT TESTED** |
| Ollama localhost bind enforcement | **NOT TESTED** |
| Profile selection on 4/8/16/24 GB VMs | **NEEDS REAL VM TESTING** |
| CUDA / GPU lane selection | **NEEDS REAL GPU TESTING** |
| MOTD READY after install | **NEEDS REAL VM TESTING** |
| Manual `--model` override | **NEEDS REAL VM TESTING** |
| Release download + SHA on curl path | **NOT TESTED** |
| Cloud provider detection | **NEEDS REAL VM TESTING** |

PR 50’s own report correctly says “not VM-tested, not launch-ready” — but also overstates profile integration completeness. This audit supersedes that conclusion.

---

## Audit Area Details

### Area 1 — trial-install.sh

| Question | Finding |
| --- | --- |
| Executes 8.1 → 8.2 → 8.3? | Yes, when not `--no-motd` |
| Local dev bundles work? | Yes, when full repo checkout present |
| Remote downloads work? | Scripts download via `EIGHTBALL_RELEASE` raw URL; **8.2 still needs local `profiles/`** |
| Version compatibility added? | Yes, but non-fatal on bundle mismatch |
| Immutable release/tag support? | Default `v0.8.0`; override `EIGHTBALL_RELEASE=main` works |
| Download integrity? | SHA only if local manifest file ships with scripts |
| Dev overrides? | `EIGHTBALL_RAW_BASE`, `EIGHTBALL_RELEASE=main` preserved |
| Customer error handling? | Step failure shows log tail — adequate |

### Area 2 — 8.1.sh

| Question | Finding |
| --- | --- |
| Ubuntu/Debian validation | PASS |
| Minimal prerequisites | PASS |
| Swap handling | Added (was absent on main); idempotent |
| Existing/fresh Ollama | Reuses binary; remote `ollama.com/install.sh` unchanged |
| systemd startup | PASS |
| Localhost API verification | PASS (API responds) |
| Localhost bind enforcement | **PARTIAL** — cannot guarantee exclusive bind |
| Existing overrides | Attempts drop-in; may conflict with unmanaged overrides |
| Idempotency | Reasonable |
| Logging | Improved |

**Customer invariant (Ollama not publicly exposed): NOT GUARANTEED by PR 50.**

### Area 3 — 8.2.sh

See Section 7. Inference test remains final authority **when reached**, but default path often tests only one model without fallback.

**Manual `--model`:** Deterministic, fails clearly, no silent substitution — PASS intent.

**Pre-existing models:** `eightball_remove_if_newly_pulled` — PASS.

### Area 4 — 8.3.sh

| Question | Finding |
| --- | --- |
| Fixes MISSING while model shown? | **Likely yes** — main used result-file `Model test: PASSED` for READY without `ollama list`; PR 50 checks `ollama list`. Mismatch could still occur if tag names differ in edge cases. |
| Jets status | Static `READY AFTER SIGN-IN` in template; no PARTIAL logic in PR 50 |
| Bulletin | Offline default; optional install-time fetch; no timer |
| Temp alerts | Added; `0640` meta |
| Login network | MOTD itself is local |
| REMEMBER helper | PASS |

User-reported `PARTIAL` Jets status is **not reproduced** in PR 50 templates — may be from a different build.

### Area 5 — Security and Permissions

| Path | Mode | Classification |
| --- | --- | --- |
| `8ball-trial.log` | 0644 | SAFE |
| `8ball-result.txt` | 0644 | SAFE |
| `8ball-temp-alert.txt` | 0644 | SAFE (world-readable message, not secret) |
| `8ball-temp-alert.meta` | 0640 root:adm | SAFE |
| `8ball-alert-history` | 0640 root:adm | SAFE |
| `8ball-bulletin.txt` | 0644 | SAFE |
| `trial-installed` | 0644 | SAFE |
| MOTD login decrement of meta | root write | **QUESTIONABLE** until VM login test — not world-writable |

No `0666` state found in PR 50. Main branch had no temp-alert files at all.

### Area 6 — Version and Release Integrity

| Item | Status |
| --- | --- |
| Version contract across 8.x scripts | Added (`0.8.0`) |
| Mismatch handling | Warn-only in `verify_local_bundle` |
| Default release | `v0.8.0` (no longer `main`) |
| Deterministic mechanism | Manifest + generator script exist |
| Remote enforcement | **Incomplete** — needs PR50E |

---

## 10. PR50B Recommendation

**Scope: 8.1 foundation and Ollama safety only.** Do not touch 8.2 profile logic or 8.3 MOTD in PR50B.

### PR50B must deliver

1. **Prove exclusive localhost bind**
   - After configuration and restart, require `ss -ltn` (or equivalent) to show `127.0.0.1:11434` (or `::1`) **and** show no `0.0.0.0:11434` / `[::]:11434`
   - Remove or demote curl API probe as bind proof
   - Re-verify bind after `start_ollama` early-return path

2. **Safe handling of existing Ollama configs**
   - Document and test: fresh install, existing localhost install, existing public bind, non-systemd `ollama serve`
   - Fail closed with clear message when public exposure cannot be corrected safely

3. **Idempotency tests on VM**
   - Second run does not break swap, service, or drop-in
   - Existing user Ollama data preserved

4. **Logging contract**
   - Binary path, service active, bind verification result, API response (already partially present — finalize and test)

5. **Revert PR50C items accidentally coupled to 8.1** — none identified; keep 8.1 changes isolated

### PR50B must not

- Change model selection, profile resolution, or MOTD
- Modify `c10-hardware-resolve.py`
- Publish release tags (PR50E)

### PR50B acceptance evidence

- `NEEDS REAL VM TESTING` checklist for: clean Ubuntu, Ollama pre-installed localhost, Ollama pre-installed public bind, second run idempotency
- Static `bash -n` + shellcheck if available

### Handoff to PR50C (document only)

PR50C must fix: default `MODEL_SLUG` behavior, runtime observation contract consumption, manifest fallback, candidate-chain default path, disk gates on all candidates, `EIGHTBALL_PROFILES_BASE` remote support, and cosmetic profile labeling.

---

## Sequence preserved

This audit does **not** implement PR50B–PR50F. Expected follow-on docs:

- `PR50B-foundation.md`
- `PR50C-profile-integration.md`
- `PR50D-client-status.md`
- `PR50E-release-integrity.md`
- `PR50F-validation.md`

---

## References consulted

- `AGENTS/history/cursorFileC7-profile-model-tree.md` — model-first `profiles/<slug>/<lane>/` layout
- `AGENTS/history/cursorC10-glass-ball-execute.md` — C10 profile generation from AGENTS data
- `AGENTS/cursorFile.C10.1-1-executable-install-matrix.md` — install matrix and stage meanings
- `AGENTS/data-science/profile-mapping/ubuntu-runtime-observation-contract.md` — runtime evidence rules
- `AGENTS/history/cursorFileC4-helpers-plan.md` — customer installer requirements
- `install/shared/c10-select-model.py` — pre-PR50 C10 selector (still present, underused)
