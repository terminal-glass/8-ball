Cursor task — C10.1-1 profiles directory cleanup

Work in the real terminal-glass/8-ball repository. terminal-glass is the
public repository and product namespace; funtech64 is internal only and must
not appear in customer-facing repository URLs or commands. Execute the work
and generate the files; do not return another verification-only plan.

## Mandatory self-recording

Before executing this scope, save the entire prompt verbatim—not a summary,
excerpt, or separate copy-paste handoff—in the repository's AGENTS/ directory
at:

```text
AGENTS/cursorFile.C10.1-1-profiles-directory-cleanup.md
```

This file is the active instruction for C10.1-1 profiles directory cleanup.
When a later C10 prompt becomes active, move this file into AGENTS/history/,
preserving its contents and original filename, and record the move in
AGENTS/history/README.md. Do not leave old prompts in working data directories
where a future Cursor run could mistake them for model data.

Do not create a separate end-user copy-paste file for the prompt: the complete
prompt saved in AGENTS/ is the record.

## Target repository

- Repository: `terminal-glass/8-ball` (public)
- Branch: create or continue `cursor/c10-1-1-profiles-directory-cleanup` from
  current `main` (or the latest merged C10 branch that contains Layer 4 RAM
  work)
- Scope: C10.1-1 only — profiles namespace cleanup and generator/validator
  boundary hardening. This is not C11 and not a new catalog collection pass.

## Goal

Make `profiles/` a **C10-only** model-selection and install-lane namespace.
Remove every legacy C5/C7 root-profile export, compatibility shim, and mixed
namespace artifact that predates the C10 executable install matrix. Relocate
runtime profile documentation out of `profiles/`. Move C10 provider
assumptions out of `profiles/` into `data/generated/provider-assumptions/`.
Ensure only `scripts/generate-c10-profiles.py` may write C10 profile output.

The end state must keep the full C10 model/lane matrix intact (model pages,
lane trees, stage files 3–7, `c10-index.json`, installer lane references) while
eliminating obsolete paths that confuse agents, validators, and installers.

## Confirmed current problems

On `main` today, `profiles/` mixes incompatible contracts:

1. **Legacy C5 export tree** still present:
   - `profiles/families/`
   - `profiles/models/`
   - `profiles/deployment-classes/`
   - `profiles/index.csv`
   - `profiles/manifest.json` with `schema_version: profiles.manifest.v1` and
     paths pointing at the legacy tree

2. **C10 provider assumptions in the wrong place**:
   - `profiles/provider-assumptions/` should not exist under `profiles/`
   - lane JSON and install scripts still reference
     `profiles/provider-assumptions/<lane-id>.json`

3. **Runtime contract file in the wrong namespace**:
   - `profiles/environment.profile.example.env` documents
     `/opt/philosopher/profiles` runtime artifacts, not C10 model selection

4. **Dangerous legacy generator still wired**:
   - `eight-ball generate-root-profiles` (module
     `eight_ball.generate.root_profiles`) recursively cleans `profiles/` and
     recreates obsolete C5 compatibility exports, destroying C10 model pages
     and lane trees

5. **README describes the old contract**:
   - `profiles/README.md` still documents C1 runtime locations, C5 page exports,
     and `eight-ball generate-root-profiles`

6. **Platform-tree helper still keys off C5 install manifest**:
   - `scripts/create-profile-platform-tree.sh` reads
     `data/generated/pages/install-manifest.json` instead of the C10 index

These problems cause agent confusion, validator false positives, and risk of
accidental C10 data loss when someone runs the legacy CLI.

## Required final layout

`profiles/` must contain only C10 model-selection artifacts:

```text
profiles/
  README.md
  c10-index.json
  manifest.json                 # optional; C10-only when present
  <model-slug>.json             # one model data page per catalog model
  <model-slug>/
    ubuntu/cpu/
    ubuntu/cuda/
    mac/apple-silicon/
    mac/intel/
    windows/cpu/
    windows/cuda/
    cloud/digitalocean/cpu-droplet/
    cloud/digitalocean/gpu-droplet/
    cloud/aws-lightsail/cpu/
    cloud/aws-lightsail/gpu/
```

Each lane leaf contains:

```text
lane.json
3-cpu.json
4-ram.json
5-hard_disk.json
6-CPU_only.json
7-video_card.json
```

Canonical C5 catalog pages remain under:

```text
data/generated/pages/families/
data/generated/pages/models/
data/generated/pages/deployment-types/<3-7>/
data/generated/pages/install-manifest.json
```

Runtime profile documentation moves to:

```text
docs/profile-runtime/README.md
docs/profile-runtime/environment.profile.example.env
```

## Model pairing contract

For every C10 model slug in `profiles/c10-index.json`:

- exactly one `profiles/<model-slug>.json` model data page exists at the
  profiles root, and
- exactly one `profiles/<model-slug>/` directory exists with the ten install
  lanes above.

The set of model slugs from `*.json` pages (excluding `c10-index.json` and
`manifest.json`) must equal the set of model directories at the profiles root.
No model page without a directory and no directory without a page.

Size belongs in the model page `sizes[]` records — never as directories under
`profiles/<model-slug>/`.

## Forbidden paths

Remove completely from `profiles/` (do not leave empty placeholders):

```text
profiles/families/
profiles/models/
profiles/deployment-classes/
profiles/provider-assumptions/
profiles/index.csv
profiles/environment.profile.example.env
```

Also forbidden at the profiles root:

- any file not on the allowlist below
- any directory whose name is not a model slug
- size directories directly under `profiles/<model-slug>/` (for example
  `profiles/gemma/4b/`)

When `profiles/manifest.json` exists, it must **not** reference legacy paths
(`index_csv`, `families`, `models`, `deployment_classes`,
`profiles/provider-assumptions/`).

## Allowed files

Allowed top-level entries under `profiles/`:

| Path | Purpose |
| --- | --- |
| `README.md` | C10 namespace documentation |
| `c10-index.json` | Installer-facing model/lane index |
| `manifest.json` | Optional C10-only generation manifest |
| `<model-slug>.json` | One model data page per catalog model |
| `<model-slug>/` | Lane tree for that model |

No other top-level files or directories are permitted.

## Runtime environment

`profiles/` is **not** the installed runtime profile directory. Runtime
installers write shell-safe env artifacts under:

```text
/opt/philosopher/profiles/
```

Document that contract only under `docs/profile-runtime/`. Update
`profiles/README.md` to point readers there and to keep C10 selection metadata
separate from runtime env files (`00-instance.env`, `10-platform.env`, etc.).

## Provider-assumption target layout

Generate and validate C10 provider assumptions only here:

```text
data/generated/provider-assumptions/ubuntu-cpu.json
data/generated/provider-assumptions/ubuntu-cuda.json
data/generated/provider-assumptions/mac-apple-silicon.json
data/generated/provider-assumptions/mac-intel.json
data/generated/provider-assumptions/windows-cpu.json
data/generated/provider-assumptions/windows-cuda.json
data/generated/provider-assumptions/cloud-digitalocean-cpu-droplet.json
data/generated/provider-assumptions/cloud-digitalocean-gpu-droplet.json
data/generated/provider-assumptions/cloud-aws-lightsail-cpu.json
data/generated/provider-assumptions/cloud-aws-lightsail-gpu.json
```

Every `lane.json`, install lane script/README, `install/shared/c10-model-hook.sh`,
and `profiles/c10-index.json` row must reference
`data/generated/provider-assumptions/<lane-id>.json` — never
`profiles/provider-assumptions/`.

Add `GENERATED_PROVIDER_ASSUMPTIONS_DIR` to `src/eight_ball/paths.py` when
needed by tests or library code.

## Preserve C10 behavior

Do **not** regress the established C10 executable install matrix:

- Keep all `profiles/<model-slug>.json` pages and descending `sizes[]` order
- Keep all ten install lanes per model with stage files 3–7 populated
- Keep conservative fit semantics (`fit`, `no_fit`, `unknown`; never
  `fits: true` without `fit_status: fit` / `ram_fit_status: fit`)
- Keep Layer 4 RAM `size_ram_fit` arrays in every `4-ram.json`
- Keep `install/shared/c10-select-model.py` behavior and root
  `trial-install.sh` model selection flow
- Keep `profiles/c10-index.json` row counts and lane references valid
- Do not invent hardware limits, provider capacity, or compatibility

Unknown values remain null. Unknown RAM/VRAM must never produce confirmed fits.

## Audit requirements

Use `git rm` / `git mv` for removals and relocations; do not silently delete
tracked legacy trees. The diff must clearly show:

- legacy `profiles/families|models|deployment-classes|provider-assumptions`
  removed
- `profiles/index.csv` removed
- `profiles/environment.profile.example.env` moved to `docs/profile-runtime/`
- provider-assumption path updates across install lanes and profile leaves
- legacy `eight-ball generate-root-profiles` command and module removed

Record the archived prompt move in `AGENTS/history/README.md` when this file
is later rotated to history.

## Generator ownership

Only these tools may write C10 profile namespace output:

```text
scripts/generate-c10-profiles.py
scripts/validate-c10-profiles.py
```

Remove `eight-ball generate-root-profiles` from `src/eight_ball/cli.py` and
delete `src/eight_ball/generate/root_profiles.py`.

Update `scripts/generate-c10-profiles.py` so it:

- writes provider assumptions to `data/generated/provider-assumptions/`
- writes an optional C10-only `profiles/manifest.json` using
  `schema_version: c10.profiles-manifest.v1`
- never recreates forbidden legacy directories or `profiles/index.csv`
- does not erase existing model pages or lane trees when re-run

`scripts/create-profile-platform-tree.sh` must enumerate model slugs from
`profiles/c10-index.json`, not the C5 install manifest.

## Required tests

Update and extend tests so the cleanup cannot regress:

- Rewrite `tests/test_root_profiles.py` to assert forbidden directories/files
  are absent, provider assumptions live under `data/generated/`, model page/dir
  pairing holds, C10 manifest schema is correct, runtime example env moved, and
  legacy CLI/module are removed
- Keep `tests/test_c10_profiles.py` and `tests/test_profile_platform_tree.py`
  passing
- Add/keep a generator idempotence test that sets `C10_BUILD_TIMESTAMP` and
  confirms `profiles/gemma.json` and lane artifacts survive regeneration
- Add/keep lane JSON tests that provider assumption paths use
  `data/generated/provider-assumptions/`
- Add/keep RAM stage retention test for `size_ram_fit`
- Add/keep disposable-copy trial-install selector test using `tmp_path`

Do not add unrelated catalog or installer redesign tests.

## Structural validation

Extend `scripts/validate-c10-profiles.py` to enforce:

- forbidden profiles directories absent
- forbidden root files absent (`index.csv`,
  `environment.profile.example.env`)
- profiles root allowlist (only README, c10-index, manifest, model JSON pages,
  model directories)
- model page ↔ directory pairing
- `profiles/manifest.json` uses `c10.profiles-manifest.v1` without stale legacy
  path keys
- provider assumptions directory exists with all ten lane files
- every `lane.json` and `4-ram.json` retains required fit semantics
- `c10-index.json` rows point at existing files
- install lanes remain non-empty with required scripts/assets

## Expected matrix preservation

After cleanup and regeneration, preserve the current C10 scale (approximately):

- 200+ model pages and matching model directories
- 10 install lanes
- 10 provider-assumption files
- full stage-file coverage (3–7 + `lane.json`) for every model/lane leaf
- `c10-index.json` row count consistent with model × lane coverage

Removing legacy exports must **not** reduce C10 model/lane artifact counts.

## Deterministic generation

Support deterministic regeneration for review:

- honor `C10_BUILD_TIMESTAMP` when writing JSON artifacts (via shared C10
  helpers) so repeated runs with the same timestamp do not churn unrelated
  `generated_at` fields
- running `python3 scripts/generate-c10-profiles.py` twice with the same
  `C10_BUILD_TIMESTAMP` must not delete model pages or lane trees

## Validation commands

Run all of these before calling the task complete:

```bash
python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_root_profiles.py tests/test_c10_profiles.py tests/test_profile_platform_tree.py -q
bash scripts/validate-catalog.sh
git diff --check
```

Confirm:

- validator JSON reports `"valid": true`
- pytest passes
- catalog validation passes
- no trailing whitespace in the diff

## Disposable fixture validation

Keep at least one isolated-copy test that:

- copies `install/`, `profiles/`, and `trial-install.sh` into a temporary
  directory
- sets `EIGHTBALL_REPO_ROOT` to that copy
- runs `install/shared/c10-select-model.py` successfully against
  `data/generated/provider-assumptions/ubuntu-cpu.json`

This proves path rewiring works outside the developer checkout.

## Diff hygiene

- Keep the diff focused on profiles namespace cleanup, provider-assumption
  relocation, runtime docs move, generator/validator/test updates, and install
  lane path rewrites
- Do not regenerate unrelated `data/generated/pages/` trees unless required for
  a broken reference discovered during validation
- Do not commit secrets, credentials, or customer data
- Do not touch Passport, RecordsCore, paid installer packaging, or deployment
  repositories
- Run `git diff --check` and fix trailing whitespace

## Documentation

Update:

- `profiles/README.md` — C10-only namespace, allowed/forbidden paths, regenerate
  commands, pointer to `docs/profile-runtime/`
- `docs/profile-runtime/README.md` — runtime `/opt/philosopher/profiles`
  contract and example env file location

Remove references to `eight-ball generate-root-profiles` and legacy
`profiles/families|models|deployment-classes` exports from active docs.

## Delivery

1. Commit with a clear message describing C10.1-1 profiles directory cleanup
2. Push branch `cursor/c10-1-1-profiles-directory-cleanup`
3. Open a PR against `main` summarizing:
   - removed legacy paths
   - new provider-assumption location
   - runtime docs relocation
   - legacy CLI removal
   - validation results and matrix counts
4. Report changed files, test output, validator stats, and commit SHA

## Acceptance criteria

* `profiles/` contains only the allowed C10 layout; forbidden legacy paths are
  gone
* Provider assumptions exist only under `data/generated/provider-assumptions/`
  and are referenced consistently from profiles and install lanes
* `profiles/environment.profile.example.env` no longer exists; runtime example
  lives under `docs/profile-runtime/`
* `eight-ball generate-root-profiles` and `eight_ball.generate.root_profiles`
  are removed
* `scripts/generate-c10-profiles.py` and
  `scripts/validate-c10-profiles.py` pass on the real repository data
* `tests/test_root_profiles.py`, `tests/test_c10_profiles.py`, and
  `tests/test_profile_platform_tree.py` pass
* C10 model/lane matrix counts are preserved (200+ models, 10 lanes, full
  stage files)
* `git diff --check` is clean
* Required GitHub Actions checks are green.
