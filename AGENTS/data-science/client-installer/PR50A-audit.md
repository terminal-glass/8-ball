# PR50A — 8-BALL Client Installer Audit, Architecture & Recovery

**Date:** 2026-08-13  
**Audited branch:** `cursor/8ball-launch-hardening-1896` (PR #50)  
**Base branch:** `main`  
**Prior audit:** `PR50A-1-audit.md` (superseded by this document)  
**Contract:** `PR50A-installer-scaffolding.md`  
**Scope:** Audit and architecture only — no PR50B–PR50F implementation

---

## PR 50 Summary

PR #50 attempted to harden the public 8-BALL trial installer (`trial-install.sh →
8.1 → 8.2 → 8.3`) toward a **0.8.0** suite release by:

1. Extracting shared modules under `install/shared/` (version contract, Ollama
   localhost helpers, model test helpers, hardware resolve, release helpers)
2. Rewriting canonical `install/ubuntu/{8.1,8.2,8.3,trial-install}.sh`
3. Replacing duplicated `install/ubuntu/cpu/` and `install/ubuntu/cuda/` scripts
   with thin wrappers to the canonical scripts
4. Adding release manifest scaffolding (`install/releases/v0.8.0/manifest.json`)
5. Adding offline harness, pytest checks, Proxmox matrix doc, and AGENTS reports

**Intent:** Bridge C10 profile data into the customer installer while improving
Ollama safety, MOTD accuracy, and release integrity.

**Outcome:** Directionally correct scaffolding, but **not launch-ready**. The
installer still does not genuinely consume C-series profile data at runtime, the
default install path regresses fallback behavior, and critical customer invariants
(localhost-only Ollama, manifest contract, curl-only bootstrap) remain unproven or
broken.

---

## Files Changed

| Area | Paths (relative to repo root) |
| --- | --- |
| **New shared libs** | `install/shared/8ball-version.sh`, `ollama-localhost.sh`, `8ball-model-test.sh`, `8ball-release.sh`, `c10-hardware-resolve.py` |
| **Canonical Ubuntu** | `install/ubuntu/8.1.sh`, `8.2.sh`, `8.3.sh`, `trial-install.sh` |
| **Lane wrappers** | `install/ubuntu/cpu/*.sh`, `install/ubuntu/cuda/*.sh` |
| **Release** | `install/releases/v0.8.0/manifest.json`, `scripts/generate-release-manifest.sh` |
| **Tests** | `scripts/test-installer-harness.sh`, `tests/test_installer_hardening.py` |
| **Validation** | `scripts/validate-install-lanes.py`, `tests/test_install_lane_conformance.py` |
| **Docs** | `docs/proxmox-launch-test-matrix.md`, `AGENTS/reports/8ball-0.8-launch-*.md` |

**Unchanged by PR 50:** `install/cloud/**`, Mac/Windows lanes, root
`trial-install.sh` dispatcher, C-series AGENTS data, `profiles/` tree contents,
`data/generated/pages/install-manifest.json`.

---

## KEEP

| Change | Rationale |
| --- | --- |
| `install/shared/` module extraction | Correct long-term structure; separates execution from data |
| `8ball-model-test.sh` — inference test + remove-only-newly-pulled | Preserves pre-existing customer models; matches C4 invariant |
| `8ball-version.sh` version contract skeleton | Needed for PR50E |
| `generate-release-manifest.sh` + manifest JSON shape | Correct release-integrity mechanism for PR50E |
| Ubuntu cpu/cuda thin wrappers | Reduces lane drift; preserves `EIGHTBALL_INSTALL_LANE` |
| 8.3 MOTD `ollama list` check for READY/MISSING | Addresses observed customer bug class (result-file-only READY) |
| 8.3 alert meta `0640` (not world-writable) | Permission improvement |
| 8.3 login MOTD remains network-free | Correct |
| `remember` helper | Unchanged, appropriate |
| Offline harness with honest NOT TESTED labels | Good practice |
| Proxmox matrix doc | Input for PR50F |
| `c10-select-model.py` (pre-existing, retained) | Generic X-capable selector — underused, not removed |

---

## REPAIR

| Item | Issue | Stage |
| --- | --- | --- |
| **8.1 localhost proof** | `ollama_verify_listener()` can pass via `curl` to loopback without proving exclusive bind; dual-bind (`127.0.0.1` + `0.0.0.0`) not detected | PR50B |
| **8.1 override coverage** | Misses indirect `EnvironmentFile`, `OLLAMA_HOST=:port`, non-systemd `nohup serve` | PR50B |
| **8.1 ordering** | `start_ollama` early-return on API response skips post-restart bind verification | PR50B |
| **Default `MODEL_SLUG=qwen3`** | Forces `--model-slug` on every install; collapses to single-model manual path | PR50C |
| **8.2 static lane fit** | Reads `lane.json` `fit_status=fit` precomputed for assumed hardware, not runtime host | PR50C |
| **8.2 lane resolution** | Hard-coded heuristics in `c10-hardware-resolve.py`; ignores C10.1 observation contract / taxonomy | PR50C |
| **8.2 RAM pilot bands** | Duplicated thresholds in Python; not taxonomy band IDs | PR50C |
| **8.2 disk gates** | Applied only on manual `--model`; automatic chain skips disk check | PR50C |
| **8.2 result `Profile:` field** | Derived from Ollama tag, not resolved profile identity | PR50C |
| **`install-manifest.json` removed** | Regresses documented C5 contract (`docs/install-manifest-contract.md`) | PR50C |
| **Remote/curl bootstrap** | `c10-hardware-resolve.py` requires local `profiles/` tree; no `EIGHTBALL_PROFILES_BASE` | PR50C / PR50E |
| **trial-install version check** | `verify_local_bundle` warns on mismatch but continues | PR50E |
| **Remote SHA verification** | Only when local manifest ships with scripts; `v0.8.0` tag unpublished | PR50E |
| **8.3 MOTD tag matching** | Prefix/wildcard match may false-positive; untested on real login | PR50D |
| **8.3 temp-alert decrement** | Root-only write path fragile; not VM-tested | PR50D |
| **`--no-motd` skips 8.3 entirely** | Trial marker, alerts, permissions not applied | PR50D |
| **8.3 Jets PARTIAL** | Template hardcodes `READY AFTER SIGN-IN`; no signed-in detection | PR50D |

---

## REVERT

| Item | Reason |
| --- | --- |
| **Default `MODEL_SLUG=qwen3` in `trial-install.sh`** | Breaks default candidate-chain + fallback; couples all installs to Qwen slug path |
| **Removal of `install-manifest.json` as selection authority** | Until profile path is correct, this removes the only curl-friendly catalog fallback documented in C5 |
| **Overstated claims in `AGENTS/reports/8ball-0.8-launch-hardening-report.md`** | "Profile integration complete" is not supported by evidence; supersede with this audit |

No full script revert recommended — most changes are directionally sound but incomplete.

---

## NOT IMPLEMENTED

| Required work | Notes |
| --- | --- |
| Runtime observation contract consumption | `profiles/provider-compatibility/*/runtime-observation-contract.json` unused |
| C10.1 taxonomy / band projection | `host-capability-categories.json`, `lane-runtime-contract-projection.json` unused |
| Per-stage evidence JSON (`3-cpu`, `4-ram`, `5-hard_disk`, `7-video_card`) | Present in `profiles/<slug>/<lane>/` but not evaluated at install time |
| Provider-assumption runtime join | Referenced in result file only |
| Cloud lane hardening | `install/cloud/**` unchanged |
| Mac/Windows integration with shared modules | Unchanged |
| Published `v0.8.0` tag + remote manifest fetch | Manifest exists only in checkout |
| Bundle mismatch hard-fail | Warn-only today |
| Systemd bulletin timer | Not present |
| `trial-installed` marker from `trial-install.sh` | Only written when 8.3 runs |
| `8balljets.txt` state file | Not present in PR 50 (user audit list includes it; not implemented) |
| Disk warnings in MOTD | Not implemented |
| Real VM / GPU validation | Explicitly absent |

---

## 8.1 Foundation Status

### **PARTIAL**

| Check | Evidence |
| --- | --- |
| Ubuntu/Debian validation | Present (`require_debian_family`) |
| APT prerequisites, noninteractive | Present |
| Swap — existing / new / idempotent | Added; reasonable logic |
| Existing Ollama reuse | Present |
| Fresh Ollama via `ollama.com/install.sh` | Unchanged from main |
| systemd startup | Present |
| Localhost API verification | Present (`curl` to `127.0.0.1:11434`) |
| **Actual exclusive network bind** | **Not guaranteed** — see `ollama-localhost.sh` fallback |
| Idempotency | Reasonable for swap and drop-in |
| Logging | Improved |
| Failure recovery | Public-bind correction attempts fail-closed; other paths unclear |

**Customer invariant:** Installing 8-BALL must not accidentally expose Ollama
publicly. **PR 50 does not fully enforce this.**

**PR50B must:** Prove exclusive localhost bind with `ss` (no `0.0.0.0:11434`),
remove curl-as-bind-proof, re-verify after all start paths, VM-test existing
configs.

---

## 8.2 Model Engine Status

### **FAIL**

PR 50 **reads** some C10 artifacts but does **not** implement the intended
architecture:

```text
hardware → environment detection → profile resolution → C-series data
  → approved candidates → resource gates → pull → REAL inference → fallback
```

### What PR 50 actually does

```text
hardware (partial) → hard-coded lane heuristics → static lane.json fit flags
  + RAM-band pilot menu (Qwen-specific) → pull → inference → fallback (often skipped)
```

### Evidence

1. **`c10-hardware-resolve.py`** walks `profiles/qwen3/<lane>/lane.json` for
   rows where `fit_status=fit`. Those fits were generated against **assumed**
   provider-class hardware (e.g. ubuntu-cpu 16 GB / 9 GB usable), not the
   actual host at install time (contradicts
   `ubuntu-runtime-observation-contract.md`).

2. **Default install bypasses fallback chain.** `trial-install.sh` defaults
   `MODEL_SLUG=qwen3` → passes `--model-slug qwen3` → `8.2.sh` calls
   `c10_select_model_slug` → sets single `REQUESTED_MODEL` →
   `run_manual_override` → **no candidate chain**.

3. **`install-manifest.json` no longer used for selection** despite C5 contract
   requiring 8.2 to read it.

4. **`Profile:` in result file** is `model tag with punctuation replaced` — not
   profile/lane identity. This is labeling, not resolution.

5. **Inference test remains authoritative when reached** — `8ball-model-test.sh`
   preserves the principle. **Pre-existing models preserved** via
   `eightball_remove_if_newly_pulled`. **Manual `--model`** is deterministic with
   disk check and explicit failure. These are KEEP items undermined by the default
   path.

### Manual `--model` audit

```bash
sudo ./8.2.sh --model <model>
```

| Step | Status |
| --- | --- |
| Validate identifier | PASS (`eightball_validate_model_name`) |
| Resource checks | PARTIAL (disk only on manual path) |
| Pull if needed | PASS |
| Real inference | PASS |
| PASS / explicit failure | PASS (no silent substitution) |

Works when invoked directly. Does not fix default-install behavior.

---

## X/Y Architecture Status

### Y validation readiness: **PARTIAL**

The vertical Y path (hardware → profile → Qwen candidate → pull → infer → fallback
→ result → MOTD) is **structurally sketched** but **not ready for environment
matrix validation** because:

- Default install skips fallback chain
- Static lane fit may select wrong Qwen sizes on low-RAM hosts
- Curl-only bootstrap cannot resolve profiles without full repo
- No real VM evidence exists

Y can be made validation-ready with PR50B (foundation) + PR50C (engine fixes) +
PR50F (VM matrix). No full installer redesign required.

### X integration readiness: **SIGNIFICANT REWORK**

If C-series supplied approved non-Qwen model **X** tomorrow, **significant
rework** of the 8.2 execution path would be required. The data layer is largely
ready; the installer engine is not.

#### Why not READY or MINOR ADAPTATION

| Limitation | Location | Should be |
| --- | --- | --- |
| Default `MODEL_SLUG=qwen3` | `trial-install.sh`, `8.2.sh` | Caller-supplied or catalog-default, not hard-coded Qwen |
| `c10-hardware-resolve.py` default slug `qwen3` | line 330 | Generic; slug from catalog/CLI only |
| `pilot_menu_candidates()` Qwen-only refs | `8ball-base-pilot-menu.json` consumed as Qwen ladder | Generic candidate source per model slug |
| `minimum_disk_mib()` regex heuristics (`:14b`, `:8b`) | `c10-hardware-resolve.py` | Size record `min_disk_gb` from `profiles/<slug>.json` |
| `lane_fit_candidates(repo, model_slug, …)` | Generic function exists | **Sound** — already parameterized by slug |
| `c10-select-model.py` | Pre-existing | **Sound** — generic; picks largest fit for any slug |
| `profiles/<slug>/` tree | 200+ families exist (e.g. `gemma3`, `llama3`) | Data ready for X |
| Result `Profile:` from tag | `8.2.sh` `write_result` | Resolved lane + model slug from data |

#### Functions inspected (user-named equivalents)

PR 50 does not define `build_candidate_list()`, `tier_for_model()`, or
`profile_for_model()` as named functions. Equivalent logic:

| Concept | PR 50 location | Model knowledge? |
| --- | --- | --- |
| `build_candidate_list` | `lane_fit_candidates()` + `pilot_menu_candidates()` + `merge_candidates()` | Pilot menu is Qwen-specific data; lane fit is generic per slug |
| `minimum_disk_mb_for_model` | `minimum_disk_mib()` | **Yes** — regex on tag string; should use `profiles/<slug>.json` `estimated.min_disk_gb` |
| `tier_for_model` | `tier` in `build_plan()` (`LOCAL LITE` / `LOCAL GPU`) | Lane-derived only; no per-model tier from data |
| `profile_for_model` | `Profile:` in result file | **Cosmetic** — derived from tag, not data |

**Installer execution logic should own:** pull, inference test, fallback ordering,
remove-only-newly-pulled, logging, error surfaces.

**Profile/catalog data should own:** candidate list, RAM/VRAM/disk requirements,
fit evaluation against observed host, fallback order, provenance.

---

## Profile Integration Status

### **8.2 does NOT genuinely consume existing C-series profile/model data at runtime.**

It **reads files** from the C10 tree but treats **precomputed static fit flags**
as install-time truth without joining runtime observations to the C10.1
observation contract or stage JSON gates.

### C-series artifacts: consumed vs ignored

| Artifact | Consumed? | How |
| --- | --- | --- |
| `profiles/<slug>.json` | Partial | Size ordering only |
| `profiles/<slug>/<lane>/lane.json` | Partial | Static `size_fit` flags |
| `profiles/<slug>/<lane>/{3-cpu,4-ram,5-hard_disk,7-video_card}.json` | **No** | — |
| `profiles/provider-assumptions/*.json` | Label only | Path in result file |
| `profiles/provider-compatibility/**` | **No** | — |
| `AGENTS/.../8ball-base-pilot-menu.json` | Partial | Qwen RAM-band fallback |
| `data/generated/pages/install-manifest.json` | **No** (regression) | Was primary on `main` |
| `install/shared/c10-select-model.py` | Marginal | Collapses to one model on `--model-slug` |
| `scripts/c10_*_compatibility.py` outputs | **No** | — |

---

## X Data Contract Findings

Investigation of what existing C-series artifacts **already provide** (not
fabricated):

| Contract field | Existing source | Install-time usable today? |
| --- | --- | --- |
| **Model ID / slug** | `profiles/<slug>.json` → `model_slug`; `profiles/manifest.json` index | Yes (if repo present) |
| **Ollama ref** | `profiles/<slug>.json` → `sizes[].ollama_ref` | Yes |
| **Hardware/environment profile** | `profiles/provider-assumptions/<lane>.json`; lane `detection_signals` | Partial — not evaluated at runtime |
| **Candidate priority** | `profiles/<slug>.json` `sizes[]` order; `lane.json` `size_fit[]` | Partial — static fit only |
| **RAM requirement** | `sizes[].estimated.min_system_ram_gb` | **Available in data, unused by PR 50** |
| **VRAM requirement** | `sizes[].estimated.min_vram_gb` | **Available in data, unused** |
| **Disk requirement** | `sizes[].estimated.min_disk_gb`; pilot menu `disk_thresholds_mib` (Qwen only) | Partial — manual path only for pilot thresholds |
| **CPU compatibility** | `profiles/<slug>/<lane>/3-cpu.json` | **Available, unused** |
| **GPU compatibility** | `profiles/<slug>/<lane>/7-video_card.json` | **Available, unused** |
| **Fallback order** | `lane.json` `size_fit` reverse; `c10-select-model.py` `fallback_chain` | Partial — static |
| **Mapping provenance** | `lane.json` `provenance`, `generated_at` | Available; not surfaced to customer |
| **Deployment class** | `install-manifest.json` deployments `3`–`7` | Available; **removed from 8.2 selection** |
| **Runtime taxonomy band** | `profiles/provider-compatibility/ubuntu/host-capability-categories.json` | **Available, unused** |

### Gaps (data does not provide or installer cannot reach)

- **Runtime fit evaluation API** — no single JSON artifact says "given these
  observed facts, here are approved candidates for slug X on lane Y." Must be
  composed from observation contract + stage JSON + size records.
- **Remote profile fetch contract for curl bootstrap** — `EIGHTBALL_PROFILES_BASE`
  works in `c10-select-model.py` but not in `c10-hardware-resolve.py`.
- **Generic pilot menu per model slug** — `8ball-base-pilot-menu.json` is Qwen-only.
- **Catalog-default model slug** — no committed "trial default model" separate
  from Qwen hard-coding.

**PR50C target:** `profile/catalog → approved X candidates → generic 8.2 engine`
without teaching 8.2 every model family.

---

## 8.3 Client Status

### **PARTIAL**

### Observed customer failure (pre-PR50)

```text
Ollama ............. RUNNING
Local Model ........ MISSING        ← status line
...
Local:    ollama run qwen3:1.7b    ← model name line
```

**Root cause on `main`:** MOTD set `model_status=READY` when result file contained
`Model test: PASSED` **without** checking `ollama list`. If result file and
Ollama state diverged, status could be wrong. The specific **MISSING** string did
not exist on `main` (used `UNKNOWN` / `READY`). MISSING may come from an
intermediate/private build or a different MOTD variant. PR 50 adds explicit
MISSING when model not in `ollama list`.

### PR 50 fix assessment

| Check | Assessment |
| --- | --- |
| READY/MISSING from `ollama list` | **Improved** — checks actual Ollama state |
| Selected-model parsing | Reads `Model:` from result file — reasonable |
| `ollama list` matching | Prefix/wildcard — may edge-case; **needs VM test** |
| Ollama service status | `systemctl` + curl fallback — reasonable |
| Jets status | Static `READY AFTER SIGN-IN` in template — **no PARTIAL logic** |
| Bulletin | Offline placeholder; optional install-time fetch; no timer |
| Temp alerts | Added; `0640` meta |
| REMEMBER | PASS |
| Disk warnings | **Not implemented** |
| Offline login | MOTD script itself is local |
| Login latency | No inference; alert decrement is lightweight but untested |

**PARTIAL** — core MISSING/READY bug class addressed in code, but not proven on
real login; Jets PARTIAL not addressed.

---

## trial-install.sh Status

### **PARTIAL**

| Check | Status |
| --- | --- |
| Chain 8.1 → 8.2 → 8.3 | PASS (when not `--no-motd`) |
| Local dev bundle | PASS with full repo checkout |
| Remote script download | PASS via `EIGHTBALL_RELEASE` raw URL |
| Remote **profile** resolution for 8.2 | **FAIL** without full `profiles/` tree |
| `bash -n` before install downloaded scripts | PASS |
| Error handling + log tail | PASS |
| `--model` | PASS (passed to 8.2) |
| `--no-motd` | PASS (skips 8.3 entirely) |
| Source overrides (`EIGHTBALL_RAW_BASE`, `EIGHTBALL_RELEASE=main`) | PASS |
| Logging | PASS |
| Completion marker | PARTIAL — `trial-installed` only via 8.3 |
| Version compatibility | PARTIAL — present, non-fatal on mismatch |
| Immutable release default | PASS — defaults `v0.8.0`, not `main` |
| Download integrity (SHA) | PARTIAL — local manifest only; tag unpublished |

**PR50E must:** Hard-fail version mismatch; fetch remote manifest; verify SHA on
curl path; document `EIGHTBALL_RELEASE=main` dev override.

---

## Security / Permissions Findings

Files under `/opt/philosopher/` (PR 50):

| File | Mode | Classification |
| --- | --- | --- |
| `8ball-trial.log` | 0644 | SAFE |
| `8ball-result.txt` | 0644 | SAFE |
| `8ball-temp-alert.txt` | 0644 | SAFE |
| `8ball-temp-alert.meta` | 0640 root:adm | SAFE |
| `8ball-alert-history` | 0640 root:adm | SAFE |
| `8ball-bulletin.txt` | 0644 | SAFE |
| `trial-installed` | 0644 | SAFE |

| Finding | Classification |
| --- | --- |
| No `0666` world-writable state in PR 50 | SAFE |
| MOTD login decrement of `8ball-temp-alert.meta` | **QUESTIONABLE** until VM login test — root-writable, not world-writable |
| `8balljets.txt` | Not created by PR 50 — N/A |
| Installed helpers `/usr/local/bin/{remember,8balljets}` | 0755 — SAFE |
| No new systemd units | N/A |

---

## Testing Confidence

| Test / claim | Classification |
| --- | --- |
| `bash -n` installer scripts | **STATIC TESTED** |
| `pytest tests/test_installer_hardening.py` | **STATIC TESTED** |
| `c10-hardware-resolve.py plan` in repo checkout | **STATIC TESTED** |
| `scripts/test-installer-harness.sh` | **STATIC TESTED** (skips live paths) |
| `validate-install-lanes.py` | **STATIC TESTED** |
| Full `pytest` (313) | **STATIC TESTED** (catalog/domain, not installer VM) |
| ShellCheck | **NOT TESTED** |
| First / idempotent install | **NOT TESTED** |
| Ollama localhost exclusive bind | **NOT TESTED** |
| MOTD READY/MISSING on real login | **NOT TESTED** |
| Profile selection 4/8/16/24 GB | **NEEDS REAL VM TESTING** |
| CUDA / GPU lanes | **NEEDS REAL GPU TESTING** |
| Cloud provider detection | **NEEDS REAL VM TESTING** |
| Manual `--model` on VM | **NEEDS REAL VM TESTING** |
| Release curl + SHA | **NOT TESTED** |
| Bulletin / temp-alert login flow | **NOT TESTED** |

`bash -n` success ≠ customer installation success.

---

## NEEDS REAL VM TESTING

- Clean Ubuntu install: 4 GB, 8 GB, 16 GB, 24+ GB CPU
- Idempotent re-run (swap, Ollama, drop-in, existing models)
- Ollama pre-installed localhost vs public bind correction
- Ubuntu NVIDIA/CUDA small/medium/large VRAM
- AWS Lightsail CPU/GPU detection and lane resolution
- DigitalOcean CPU/GPU detection and lane resolution
- Default install Qwen Y fallback chain end-to-end
- Manual `--model` success and failure paths
- MOTD READY/MISSING after successful install (login session)
- MOTD temp-alert decrement across logins
- `--no-motd` behavior vs full install state files
- Curl/bootstrap install without full repo checkout
- Release `v0.8.0` download + SHA verification

---

## PR50B Recommendation

**Scope: 8.1 foundation / Ollama safety ONLY.**

### PR50B must deliver

1. **Exclusive localhost bind proof** — after config + restart, `ss -ltn` must
   show `127.0.0.1:11434` (or `::1`) and **no** `0.0.0.0:11434` / `[::]:11434`
2. **Remove curl API probe as bind proof** — API reachability ≠ bind exclusivity
3. **Re-verify bind after every start path** including early-return in
   `start_ollama`
4. **Safe handling** of fresh install, existing localhost, existing public bind,
   non-systemd `ollama serve`
5. **Idempotency VM evidence** — second run does not break swap, service, drop-in
6. **Logging contract finalized** — binary path, service active, bind verified,
   API responding

### PR50B must NOT

- Change 8.2 model selection, profile resolution, or X/Y plumbing
- Change 8.3 MOTD, alerts, or bulletin
- Publish release tags (PR50E)
- Modify C-series data

### PR50B acceptance

- Static: `bash -n`, shellcheck if available
- VM checklist documented in `PR50B-foundation.md` (to be created in PR50B)
- Evidence tables: PASS / FAIL / NOT TESTED per environment

### Handoff notes for PR50C (do not implement in PR50B)

- Revert default `MODEL_SLUG=qwen3`
- Restore `install-manifest.json` as fallback authority
- Runtime observation contract + stage JSON gates
- Generic candidate engine parameterized by `model_slug` only
- `EIGHTBALL_PROFILES_BASE` support in hardware resolve
- Disk gates on all candidates, not manual path only

---

## Final Architectural Test — Four Questions

### Question 1

**Can we successfully prove Y across target client environments without
redesigning the installer?**

**Yes, with focused repair — not today.** The pipeline structure exists. PR50B
(Ollama safety) + PR50C (fix default path, runtime fit, fallback chain, manifest
fallback) + PR50F (VM matrix) can prove Y without architectural redesign. Today
the default path and static fit block reliable Y proof.

### Question 2

**If C-series supplies model X tomorrow, can 8.2 consume it without
model-family-specific code?**

**Not yet.** `lane_fit_candidates()` and `c10-select-model.py` are already
parameterized by slug. Blockers: hard-coded `qwen3` defaults, Qwen-only pilot
menu fallback, regex disk heuristics, and static fit without runtime gates.
**Significant rework in PR50C**, not a new architecture.

### Question 3

**What exact remaining code assumes Y/Qwen where it should consume X/data?**

| Location | Assumption |
| --- | --- |
| `install/ubuntu/trial-install.sh` | `MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-qwen3}"` |
| `install/ubuntu/8.2.sh` | `MODEL_SLUG="${EIGHTBALL_MODEL_SLUG:-qwen3}"` |
| `install/shared/c10-hardware-resolve.py` | Default slug `qwen3`; `pilot_menu_candidates()` from Qwen pilot menu; `minimum_disk_mib()` regex on Qwen-style tags |
| `AGENTS/.../8ball-base-pilot-menu.json` | Qwen-only `pilot_candidates` and bands |
| `install/ubuntu/8.2.sh` `write_result` | `Profile:` derived from tag string |

Generic interfaces to **preserve:** `REQUESTED_MODEL`, `c10_select_model_slug`,
`lane_fit_candidates(slug)`, `eightball_pull_and_test`, candidate chain loop.

### Question 4

**Can model #201 eventually be added through data without changing `8.2.sh`?**

**Not today. Possible after PR50C.**

**Data side:** `profiles/<family>/` trees already exist for 200+ families. Adding
model #201 is primarily a profile generation / promotion task (C-series), not an
installer edit.

**Installer side (PR50C must change):**

1. Remove hard-coded `qwen3` defaults — slug comes from CLI/catalog only
2. Replace `pilot_menu_candidates()` Qwen ladder with slug-agnostic candidate
   source (`lane.json` + stage JSON + `profiles/<slug>.json` estimates)
3. Replace `minimum_disk_mib()` regex with `sizes[].estimated.min_disk_gb`
4. Evaluate fit at runtime against observed host, not static `fit_status` flags
5. Keep `8.2.sh` as orchestration only: load plan JSON → gate → pull → test →
   fallback

After PR50C, adding model #201 should require **profile data update only**,
matching the long-term success criterion.

---

## References Consulted

| Document | Relevance |
| --- | --- |
| `AGENTS/history/cursorFileC7-profile-model-tree.md` | Model-first `profiles/<slug>/<lane>/` layout |
| `AGENTS/history/cursorC10-glass-ball-execute.md` | C10 profile generation from AGENTS data |
| `AGENTS/cursorFile.C10.1-1-executable-install-matrix.md` | Install matrix, stage meanings |
| `AGENTS/history/CursorFileC2-environment-artifact-sequencing.md` | Artifact layers 1–3 for 8.2 |
| `AGENTS/history/CursorFileC3-environment-gates-testing-plan.md` | Gates 4–7 planned |
| `AGENTS/history/cursorFileC4-helpers-plan.md` | Customer installer requirements |
| `AGENTS/data-science/profile-mapping/ubuntu-runtime-observation-contract.md` | Runtime evidence rules |
| `docs/install-manifest-contract.md` | C5 manifest contract (regressed in PR 50) |
| `profiles/manifest.json` | Catalog index and deployment classes |
| `install/shared/c10-select-model.py` | Generic slug selector (pre-PR50) |

---

## Related Documents

| Document | Role |
| --- | --- |
| `PR50A-installer-scaffolding.md` | Contract and PR50A–F sequence |
| `PR50A-1-audit.md` | First-pass audit (superseded) |
| `PR50B-foundation.md` | To be created in PR50B |
| `PR50C-profile-integration.md` | To be created in PR50C |
| `PR50D-client-status.md` | To be created in PR50D |
| `PR50E-release-integrity.md` | To be created in PR50E |
| `PR50F-validation.md` | To be created in PR50F |
