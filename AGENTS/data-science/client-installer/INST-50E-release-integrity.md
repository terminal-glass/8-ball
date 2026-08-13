# INST-50E — Release / Bootstrap Integration

**Date:** 2026-08-13  
**Contract:** `AGENTS/INST-client-installer-scaffolding.md`  
**Prior stage:** `INST-50D-client-status.md`  
**Scope:** `trial-install.sh` release coherence and verified remote bootstrap only

---

## Release Identity Mechanism

Production installs default to `EIGHTBALL_RELEASE=v0.8.0` and resolve **one** manifest:

```text
install/releases/v0.8.0/manifest.json
```

The manifest lists 121 repo-relative artifacts under a single `release_tag` and `repository` (`terminal-glass/8-ball`). Ubuntu scripts remain in `scripts` for backward compatibility; all paths are also recorded in `artifacts`.

Remote bootstrap fetches the manifest from:

```text
https://raw.githubusercontent.com/terminal-glass/8-ball/<release>/install/releases/<release>/manifest.json
```

Local checkouts with a complete bundle skip remote fetch when `eightball_local_bundle_ready` succeeds.

---

## Profile / Runtime Delivery Mechanism

Runtime bundle contract: `install/releases/v0.8.0/runtime-bundle.json`

Pinned subset (not the full 72k matrix):

- Ubuntu installer scripts + shared helpers required by 8.1–8.3
- `scripts/c10_common.py`
- `AGENTS/data-science/profile-mapping/8ball-base-pilot-menu.json`
- Release-pinned `install/releases/v0.8.0/install-manifest.json`
- `profiles/lanes.json`, `profiles/manifest.json`, ubuntu provider assumptions
- Profile runtime for `qwen3` and `tinyllama` across `ubuntu/cpu` and `ubuntu/cuda` (`model.json`, `sizes/*.json`, `lane.json`)

Bootstrap stages artifacts under:

```text
${PHILOSOPHER_ROOT}/.8ball-release/${EIGHTBALL_RELEASE}/
```

and exports:

- `EIGHTBALL_REPO_ROOT` → staged tree root
- `EIGHTBALL_MANIFEST` → release-pinned install manifest (unless overridden)

8.2 / `c10-hardware-resolve.py` consume the staged tree via `EIGHTBALL_REPO_ROOT`; production does not silently read mutable `main`.

---

## Checksum Mechanism

Flow:

```text
resolve release
    → obtain manifest
    → download artifact to file
    → SHA-256 verify
    → install / execute
```

- `eightball_verify_artifact_sha` fails closed on missing entries, empty files, or mismatch.
- `eightball_verify_download_sha` no longer skips unknown script entries in production.
- Components are downloaded with `curl -o` then verified; no `curl | bash`.
- `trial-install.sh` self-checks against the manifest before continuing.

---

## Production Behavior

- Default: pinned `v0.8.0` release bundle.
- All runtime scripts, shared helpers, and profile data come from the same manifest.
- No default `MODEL_SLUG=qwen3`; `--model` / `--model-slug` pass through to 8.2.
- `--no-motd` still skips 8.3 while completing 8.1 + 8.2.
- Successful chain writes `${PHILOSOPHER_ROOT}/trial-installed` with `release_tag`; failures clear the marker.

---

## Development / Local Behavior

Preserved overrides (explicit only):

| Override | Effect |
| --- | --- |
| Full local checkout (`profiles/` + `install/` + `scripts/c10_common.py`) | `eightball_local_bundle_ready` → no remote bootstrap |
| `EIGHTBALL_REPO_ROOT` | Use supplied tree; skip release checksum on scripts |
| `EIGHTBALL_RELEASE=main` | Development raw URLs; no verified bootstrap |
| `EIGHTBALL_RAW_BASE` | Explicit HTTPS script base |
| `EIGHTBALL_ALLOW_UNVERIFIED_DOWNLOADS=1` | Skip verified bootstrap |

`scripts/generate-release-manifest.sh` regenerates checksums and syncs the pinned install manifest snapshot.

---

## Tests / Results

| Check | Result |
| --- | --- |
| `bash -n` (`trial-install.sh`, `8ball-release.sh`) | PASS |
| `scripts/test-installer-harness.sh` | PASS |
| `python3 scripts/validate-install-lanes.py` | PASS |
| `bash scripts/validate-catalog.sh` | PASS |
| `pytest tests/test_inst_50e_release_integrity.py` | PASS (17 tests, mocked) |
| Full `pytest` | PASS (413 passed, 8 skipped) |

INST-50E tests cover: single-release artifact identity, profile staging, checksum pass/fail, missing/corrupt/partial download rejection, local bundle, `--model` / no Qwen default, `--no-motd`, completion marker truthfulness, rerun safety.

---

## NEEDS REAL VM TESTING

| Scenario | Why |
| --- | --- |
| Remote `v0.8.0` tag fetch on clean host | Mocked HTTP in CI |
| End-to-end curl-download bootstrap without full repo | Requires network + root VM |
| Profile resolver on staged release tree with real hardware | Requires host |
| Published GitHub release tag alignment | Tag not published from this stage |
| Idempotent re-run after partial failure | Requires root + prior state |

---

## Handoff

INST-50F (Proxmox matrix / real VM validation) is **not** started in this stage.

Regenerate release checksums after installer or runtime-bundle changes:

```bash
bash scripts/generate-release-manifest.sh v0.8.0
```
