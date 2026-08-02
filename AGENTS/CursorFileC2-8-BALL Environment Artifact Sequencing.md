CursorFileC2 - 8-BALL Environment Artifact Sequencing

Purpose

Create the first three environment-artifact layers that let 8.2 make an intelligent install decision without guessing.

C1 created the loader contract:

• where profile artifacts live
• how 8.2 loads them
• how 8.3 reads the final result

C2 defines the first half of the artifact sequence:

1. model family
2. model
3. deployment type

Steps 4-7 are planned in C3 and must not be rushed into this PR.

Design Rule

Do not invent model sizing, provider sizing, or instance disqualification logic.

This step creates the folder structure and human-readable metadata needed to sequence decisions. The actual disk/RAM/CPU/GPU gates are a separate C3 step after we reconcile prior bare-metal, AWS Lightsail, DigitalOcean, Jet, Mac, and Windows knowledge.

Source Of Truth

Use the current authoritative 8-BALL catalog/projection as the source for family and model identity.

The user expects the first generated folder series to represent the exact real installable family set. The current planning phrase is “200 exact real families.” Do not resolve that against the broader projection by guessing. Generate from the approved family list, and if the approved list differs from 200, 232, or 234, stop and report the mismatch before continuing.

Do not hand-create fake family folders. Generate family/model artifacts from the approved catalog input and report any count mismatch before continuing.

Current known catalog context:

• 234 total family records in the public projection
• source exceptions retained separately
• 437 canonical model records
• 7,271 deployment variants

For this C2 step, the important output is not final sizing. The important output is clean identity and deployment-type metadata that later gates can consume.

Profile Directory Layout

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

The numbered directories are the decision sequence. They are human-readable source artifacts and should use .md unless a specific file needs to be machine-consumed.

Machine-consumed output belongs in:

```text
profiles/generated/
```

Do not make Bash parse Markdown. 8.2 should consume generated .env or .json artifacts.

Artifact Format Rule

Use this split:

|Artifact Type                 |Format |Purpose                                                                    |
|------------------------------|-------|---------------------------------------------------------------------------|
|Human-readable source notes   |`.md`  |Explain family/model/deployment intent and metadata.                       |
|Machine manifest              |`.json`|Main structured source for `8.2`, website cards, and future Docker routing.|
|Installer env export          |`.env` |Shell-safe values consumed by `8.2` and `8.3`.                             |
|Raw scratch or recovered notes|`.txt` |Allowed only for imported source notes, not as the operational contract.   |

.txt is acceptable for recovered historical notes, but the finished C2/C3 contract should produce .json plus .env for automation.

Step 1 - Family Artifacts

Create one folder per approved real model family:

```text
profiles/01-families/<family-id>/
  family.md
  metadata.json
```

family.md should be readable by humans and include:

• family ID
• display name
• publisher/source status when known
• capability summary from catalog facts
• source-exception status if applicable
• whether family is eligible for local install, Jet routing, both, or neither
• notes for future Docker/OpenWebUI selection

metadata.json should include stable keys for later Docker and installer use:

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

Do not fill unknown values with guesses. Use null, empty strings, or explicit unknown values where appropriate.

Step 2 - Model Artifacts

Create model folders under their family:

```text
profiles/02-models/<family-id>/<model-id>/
  model.md
  metadata.json
```

model.md should include:

• family ID
• canonical model ID
• aliases
• capabilities
• available deployment variants/tags
• known parameter-size labels from the catalog
• source-exception status if applicable
• notes for later selection and Docker/OpenWebUI routing

metadata.json should include:

```json
{
  "schema_version": 1,
  "family_id": "",
  "model_id": "",
  "aliases": [],
  "capabilities": [],
  "variant_count": 0,
  "variants": [],
  "source_exception": false,
  "openwebui_docker_model": "",
  "docker_profile_hint": "",
  "notes": []
}
```

C2 may preserve variants as identity records, but it must not assign RAM/CPU/GPU/disk gates yet. That belongs to C3.

Step 3 - Deployment Type Artifacts

Create these deployment-type files:

```text
profiles/03-deployment-types/canary.md
profiles/03-deployment-types/bare-metal.md
profiles/03-deployment-types/aws-lightsail.md
profiles/03-deployment-types/digitalocean-droplets.md
profiles/03-deployment-types/jet.md
profiles/03-deployment-types/Mac.md
profiles/03-deployment-types/Windows.md
```

Meanings:

|Deployment Type        |Meaning                                                                                       |
|-----------------------|----------------------------------------------------------------------------------------------|
|`canary`               |Baseline safe install used when the system needs a known-good local model.                    |
|`bare-metal`           |Customer-owned physical or VM host with direct resource detection.                            |
|`aws-lightsail`        |AWS Lightsail instance sizing lane from prior NoCloudGPT work.                                |
|`digitalocean-droplets`|DigitalOcean Droplet sizing lane from prior NoCloudGPT work.                                  |
|`jet`                  |Terminal.glass/NoCloudGPT cloud or Jet model routing lane.                                    |
|`Mac`                  |Importable Mac platform lane. Create the artifact now; detailed sizing can come later.        |
|`Windows`              |Importable Windows/WSL platform lane. Create the artifact now; detailed sizing can come later.|

Each deployment file should define:

• supported platform/provider identity
• what facts the platform importer must write
• whether Docker/OpenWebUI routing is local, Jet, or provider-specific
• what C3 must recover before sizing is accepted
• disqualification behavior when required hardware facts are unavailable

Generated Output Contract

C2 should prepare, but not fully populate, these files:

```text
profiles/generated/family-model-index.json
profiles/generated/deployment-types.json
profiles/generated/environment-artifact-index.json
```

These are for later consumption by:

• 8.2
• 8.3
• website menu/model cards
• future authenticated Docker/OpenWebUI routing after customer payment

Do not create final sizing-manifest.json in C2 unless it contains only identity/deployment placeholders and is clearly marked incomplete for gates 4-7.

Docker/OpenWebUI Metadata

Every family/model artifact should reserve metadata fields for future Docker selection.

This is needed so a paying customer can be routed to the correct OpenWebUI Docker later without making the installer guess.

Required reserved fields:

• openwebui_docker_family
• openwebui_docker_model
• docker_profile_hint
• docker_image_channel
• docker_compose_profile
• records_core_release_key

If the value is not known yet, leave it blank or null. Do not invent image names, release keys, S3 keys, or RecordsCore mappings.

Acceptance Criteria

C2 is complete when:

1. profiles/01-families/, 02-models/, and 03-deployment-types/ exist.
2. Family/model artifacts are generated from the approved catalog input, not hand-guessed.
3. Source exceptions are retained as metadata but not marked installable.
4. Deployment type files exist for canary, bare metal, AWS Lightsail, DigitalOcean Droplets, Jet, Mac, and Windows.
5. Docker/OpenWebUI metadata fields are reserved but not fabricated.
6. Generated JSON indexes exist for identity/deployment metadata.
7. No disk/RAM/CPU/GPU thresholds are invented in C2.
8. The agent reports exact counts and any mismatch with the expected real-family set before proceeding.

Cursor Implementation Prompt

```text
Work in the 8-BALL installer/script repository.

Implement C2: environment artifact sequencing for steps 1-3 only.

Read CursorFileC1-environment-artifacts.md first and preserve its loader contract.

Do not modify Passport, RecordsCore, S3, Stripe, licensing, website SEO pages, or unrelated repositories.

Do not invent model sizing, instance sizing, RAM thresholds, CPU thresholds, GPU thresholds, disk thresholds, Docker image names, RecordsCore keys, or S3 keys.

Required work:

1. Create the numbered profile scaffold:
   - profiles/01-families/
   - profiles/02-models/
   - profiles/03-deployment-types/
   - profiles/04-hard-disk/
   - profiles/05-ram/
   - profiles/06-cpu/
   - profiles/07-gpu/
   - profiles/generated/

2. Generate family artifacts from the approved 8-BALL catalog input:
   - profiles/01-families/<family-id>/family.md
   - profiles/01-families/<family-id>/metadata.json

3. Generate model artifacts from the approved 8-BALL catalog input:
   - profiles/02-models/<family-id>/<model-id>/model.md
   - profiles/02-models/<family-id>/<model-id>/metadata.json

4. Preserve deployment variants as identity metadata, but do not assign gates yet.

5. Create deployment type files:
   - profiles/03-deployment-types/canary.md
   - profiles/03-deployment-types/bare-metal.md
   - profiles/03-deployment-types/aws-lightsail.md
   - profiles/03-deployment-types/digitalocean-droplets.md
   - profiles/03-deployment-types/jet.md
   - profiles/03-deployment-types/Mac.md
   - profiles/03-deployment-types/Windows.md

6. Add reserved metadata fields for later Docker/OpenWebUI routing:
   - openwebui_docker_family
   - openwebui_docker_model
   - docker_profile_hint
   - docker_image_channel
   - docker_compose_profile
   - records_core_release_key

7. Generate:
   - profiles/generated/family-model-index.json
   - profiles/generated/deployment-types.json
   - profiles/generated/environment-artifact-index.json

8. Do not generate final step 4-7 sizing gates in this PR.

Validation:
   - Confirm exact family count from the approved input.
   - Confirm exact model count from the approved input.
   - Confirm source exceptions are retained and marked not installable.
   - Confirm all deployment type files exist.
   - Confirm generated JSON is valid.
   - Run repo tests if available.
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
