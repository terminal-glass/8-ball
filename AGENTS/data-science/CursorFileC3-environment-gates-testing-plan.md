# CursorFileC3 — 8-BALL Environment Gates And Testing Plan

## Purpose

Plan the second half of the environment-artifact sequence without turning it
into one massive risky implementation.

C2 covers:

1. model family
2. model
3. deployment type

C3 will cover:

4. hard disk requirement
5. RAM requirement
6. CPU requirement
7. GPU/VRAM requirement

C3 should be split into testable groups before implementation.

## Core rule

Do not guess sizing.

Before creating final disk/RAM/CPU/GPU gates, recover and reconcile prior
NoCloudGPT sizing history for:

- bare metal hosts
- AWS Lightsail
- DigitalOcean Droplets
- Jet instance buckets
- canary baseline install

Mac and Windows artifacts exist from C2, but detailed Mac/Windows sizing is not
required in the first C3 implementation unless explicitly approved.

## Resulting decision chain

| Step | Input | Output |
| ---: | --- | --- |
| 1 | selected or default family | eligible family record |
| 2 | selected or default model | eligible model record |
| 3 | deployment type | local, provider, Jet, canary, unavailable |
| 4 | available hard disk | disk-qualified variants |
| 5 | available RAM | RAM-qualified variants |
| 6 | available CPU threads | CPU-qualified variants |
| 7 | GPU/VRAM facts | GPU-qualified or CPU-safe result |
| Result | all gates | selected model size, fallback, Jet bucket, or disqualification |

## Gate artifact layout

```text
profiles/04-hard-disk/
profiles/05-ram/
profiles/06-cpu/
profiles/07-gpu/
profiles/generated/
```

Human-readable gate sources may be `.md`. Machine-consumed output must be
`.json` plus shell-safe `.env` exports.

Recommended generated outputs:

```text
profiles/generated/sizing-gates.json
profiles/generated/sizing-gates.env
profiles/generated/canary-baseline.json
profiles/generated/jet-buckets.json
profiles/generated/provider-instance-buckets.json
profiles/generated/sizing-test-matrix.json
```

## Proposed testing groups

### Testing Group A — Identity and loader

Prove C1/C2 artifacts load correctly before sizing logic is trusted.

### Testing Group B — Provider baselines

Prove provider lanes are bucketed correctly before all model variants are mapped.

### Testing Group C — Model size gates

Prove model-size decisions work after provider baselines are stable.

### Testing Group D — Full catalog dry run

Prove the complete artifact set works without hand-checking hundreds of folders.

## C3 acceptance criteria

C3 should not be accepted until:

1. prior sizing history has been recovered or missing history is explicitly listed
2. hard disk, RAM, CPU, and GPU/VRAM gate artifacts exist
3. canary baseline and Jet bucket grouping are defined
4. provider baselines exist for bare metal, AWS Lightsail, and DigitalOcean
5. Mac and Windows remain importable lanes without fake sizing
6. generated JSON/env exports are deterministic and shell-safe
7. all selected testing groups pass

## Cursor planning prompt

```text
Do not implement C3 yet.

Plan C3 for 8-BALL environment gates in terminal-glass/8-ball, covering:
4. hard disk requirement
5. RAM requirement
6. CPU requirement
7. GPU/VRAM requirement

Read these files first:
- AGENTS/data-science/CursorFileC1-environment-artifacts.md
- AGENTS/data-science/CursorFileC2-environment-artifact-sequencing.md

Do not guess sizing.
Do not edit installer scripts in this repository.

First identify where prior NoCloudGPT sizing history exists for:
- bare metal
- AWS Lightsail
- DigitalOcean Droplets
- canary baseline
- Jet instance buckets

Create a C3 implementation plan split into 2-4 testing groups before writing
large gate logic.

Do not create final sizing thresholds unless they are recovered from prior
approved project history or clearly marked as unresolved.

Report:
- recovered sources found
- missing sources
- proposed testing groups
- files to create under profiles/
- files to avoid touching
- open questions for approval
```
