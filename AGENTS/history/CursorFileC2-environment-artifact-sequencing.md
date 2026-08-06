# CursorFileC2 — 8-BALL Environment Artifact Sequencing

## Purpose

Create the first three environment-artifact layers that let `8.2` make an
intelligent install decision without guessing.

C1 created the loader contract:

- where profile artifacts live
- how `8.2` loads them
- how `8.3` reads the final result

C2 defines the first half of the artifact sequence:

1. model family
2. model
3. deployment type

Steps 4–7 are planned in C3 and must not be rushed into this PR.

## Design rule

Do not invent model sizing, provider sizing, or instance disqualification logic.

This step creates the folder structure and catalog-derived metadata needed to
sequence decisions. The actual disk/RAM/CPU/GPU gates are a separate C3 step
after prior bare-metal, AWS Lightsail, DigitalOcean, Jet, Mac, and Windows
knowledge is recovered.

## Source of truth

Use the current authoritative 8-BALL catalog/projection as the source for family
and model identity.

The user expects the first generated folder series to represent the exact real
installable family set. The current planning phrase is “200 exact real families.”
Do not resolve that against the broader projection by guessing. Generate from the
approved family list, and if the approved list differs from 200, 232, or 234,
stop and report the mismatch before continuing.

Do not hand-create fake family folders. Generate family/model artifacts from the
approved catalog input and report any count mismatch before continuing.

Current known catalog context:

- 234 total family records in the public projection
- source exceptions retained separately
- 437 canonical model records
- 7,271 deployment variants

For this C2 step, the important output is not final sizing. The important output
is clean identity and deployment-type metadata that later gates can consume.

## Profile directory layout

Create or preserve this repo-side scaffold:

```text
profiles/
  01-families/
  02-models/
  03-deployment-types/
  04-hard-disk/
  05-ram/
  06-cpu/
  07-gpu/
  generated/
```

The numbered directories are the decision sequence. Human-readable source notes
may use `.md`. Machine-consumed output belongs in `profiles/generated/`.

Do not make Bash parse Markdown. Future `8.2` work should consume generated
`.env` or `.json` artifacts.

## Artifact format rule

| Artifact type | Format | Purpose |
| --- | --- | --- |
| Human-readable source notes | `.md` | Explain family/model/deployment intent and metadata |
| Machine manifest | `.json` | Structured source for `8.2`, website cards, and future Docker routing |
| Installer env export | `.env` | Shell-safe values consumed by `8.2` and `8.3` |
| Raw scratch or recovered notes | `.txt` | Imported source notes only, not the operational contract |

## Step 1 — Family artifacts

```text
profiles/01-families/<family-id>/
  family.md
  metadata.json
```

`metadata.json` should include stable keys for later Docker and installer use:

```json
{
  "schema_version": 1,
  "family_id": "",
  "display_name": "",
  "catalog_version": "",
  "source_exception": false,
  "installable": null,
  "openwebui_docker_family": "",
  "docker_profile_hint": "",
  "notes": []
}
```

Do not fill unknown values with guesses.

## Step 2 — Model artifacts

```text
profiles/02-models/<family-id>/<model-id>/
  model.md
  metadata.json
```

C2 may preserve variants as identity records, but it must not assign
RAM/CPU/GPU/disk gates yet. That belongs to C3.

## Step 3 — Deployment type artifacts

```text
profiles/03-deployment-types/canary.md
profiles/03-deployment-types/bare-metal.md
profiles/03-deployment-types/aws-lightsail.md
profiles/03-deployment-types/digitalocean-droplets.md
profiles/03-deployment-types/jet.md
profiles/03-deployment-types/Mac.md
profiles/03-deployment-types/Windows.md
```

## Generated output contract

C2 should prepare, but not fully populate, these files:

```text
profiles/generated/family-model-index.json
profiles/generated/deployment-types.json
profiles/generated/environment-artifact-index.json
```

Do not create final `sizing-manifest.json` in C2 unless it contains only
identity/deployment placeholders and is clearly marked incomplete for gates 4–7.

## Docker/OpenWebUI metadata

Reserve these fields but leave them blank or null when unknown:

- `openwebui_docker_family`
- `openwebui_docker_model`
- `docker_profile_hint`
- `docker_image_channel`
- `docker_compose_profile`
- `records_core_release_key`

Do not invent image names, release keys, S3 keys, or RecordsCore mappings.

## Acceptance criteria

C2 is complete when:

1. `profiles/01-families/`, `02-models/`, and `03-deployment-types/` exist
2. Family/model artifacts are generated from the approved catalog input
3. Source exceptions are retained as metadata but not marked installable
4. Deployment type files exist for all required lanes
5. Docker/OpenWebUI metadata fields are reserved but not fabricated
6. Generated JSON indexes exist for identity/deployment metadata
7. No disk/RAM/CPU/GPU thresholds are invented in C2
8. The agent reports exact counts and any mismatch with the expected family set

## Cursor implementation prompt

```text
Work in terminal-glass/8-ball.

Implement C2: environment artifact sequencing for steps 1-3 only.

Read AGENTS/CursorFileC1-environment-artifacts.md first and
preserve its loader contract.

This is metadata/catalog work only. Do not edit installer scripts in this repo.
Do not modify Passport, RecordsCore, S3, Stripe, licensing, website SEO pages,
or unrelated repositories.

Do not invent model sizing, instance sizing, RAM thresholds, CPU thresholds,
GPU thresholds, disk thresholds, Docker image names, RecordsCore keys, or S3 keys.

Required work:

1. Preserve the numbered profile scaffold under profiles/.
2. Generate family artifacts from the approved 8-BALL catalog input.
3. Generate model artifacts from the approved 8-BALL catalog input.
4. Preserve deployment variants as identity metadata, but do not assign gates yet.
5. Create deployment type files under profiles/03-deployment-types/.
6. Add reserved Docker/OpenWebUI metadata fields (null/blank when unknown).
7. Generate JSON indexes under profiles/generated/.
8. Do not generate final step 4-7 sizing gates in this PR.

Validation:
   - Confirm exact family count from the approved input.
   - Confirm exact model count from the approved input.
   - Confirm source exceptions are retained and marked not installable.
   - Confirm all deployment type files exist.
   - Confirm generated JSON is valid.
   - Run bash scripts/validate-catalog.sh and pytest.
   - Run git diff --check.

Report:
   - catalog input used
   - family count
   - model count
   - deployment variant count preserved
   - source-exception count
   - deployment type files created
   - generated files
   - validation results

Do not start C3 until C2 is reviewed and approved.
```

## C5 page tree (canonical generated output)

C2 `profiles/01-families/`, `profiles/02-models/`, and `profiles/03-deployment-types/`
were removed after C5. Installer-facing metadata pages are committed under:

```text
data/generated/pages/models/<model-slug>/<3-7>/
```

Do not generate `data/generated/pages/02-models/`. Deployment type folders are
numbered `3` through `7` per `config/deployment_types.yaml`. `8.2` reads
`data/generated/pages/install-manifest.json` — see `docs/install-manifest-contract.md`.
