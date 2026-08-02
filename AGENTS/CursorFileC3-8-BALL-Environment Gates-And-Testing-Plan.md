CursorFileC3 - 8-BALL Environment Gates And Testing Plan

Purpose

Plan the second half of the environment-artifact sequence without turning it into one massive risky implementation.

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

Core Rule

Do not guess sizing.

Before creating final disk/RAM/CPU/GPU gates, recover and reconcile prior NoCloudGPT sizing history for:

• bare metal hosts
• AWS Lightsail
• DigitalOcean Droplets
• Jet instance buckets
• canary baseline install

Mac and Windows artifacts exist from C2, but detailed Mac/Windows sizing is not required in the first C3 implementation unless explicitly approved.

Resulting Decision Chain

The final 8.2 selection chain should be:

|Step  |Input                     |Output                                                        |
|------|--------------------------|--------------------------------------------------------------|
|1     |selected or default family|eligible family record                                        |
|2     |selected or default model |eligible model record                                         |
|3     |deployment type           |local, provider, Jet, canary, unavailable                     |
|4     |available hard disk       |disk-qualified variants                                       |
|5     |available RAM             |RAM-qualified variants                                        |
|6     |available CPU threads     |CPU-qualified variants                                        |
|7     |GPU/VRAM facts            |GPU-qualified or CPU-safe result                              |
|Result|all gates                 |selected model size, fallback, Jet bucket, or disqualification|

Gate Artifact Layout

Use these directories:

```text
profiles/04-hard-disk/
profiles/05-ram/
profiles/06-cpu/
profiles/07-gpu/
profiles/generated/
```

Human-readable gate sources may be .md.

Machine-consumed output must be .json plus shell-safe .env exports.

Recommended generated outputs:

```text
profiles/generated/sizing-gates.json
profiles/generated/sizing-gates.env
profiles/generated/canary-baseline.json
profiles/generated/jet-buckets.json
profiles/generated/provider-instance-buckets.json
profiles/generated/sizing-test-matrix.json
```

Step 4 - Hard Disk Gate

Recover or define disk rules from known history. Do not invent them from model names alone.

Hard disk gate should account for:

• Ollama model download/cache space
• OpenWebUI/Docker footprint
• logs and installer working space
• safe minimum free disk
• provider plan disk size
• Jet bucket quantity based on available disk

Output should identify:

• disk-qualified variants
• disk-disqualified variants
• canary fallback eligibility
• Jet bucket recommendation when local disk is insufficient

Step 5 - RAM Gate

Recover or define RAM rules from known history.

RAM gate should account for:

• minimum RAM to pull/run a model
• recommended RAM for usable behavior
• swap policy
• provider plan memory
• canary baseline
• Jet fallback

Output should identify:

• RAM-qualified variants
• RAM-warning variants
• RAM-disqualified variants
• recommended fallback

Step 6 - CPU Gate

Recover or define CPU rules from known history.

CPU gate should account for:

• CPU thread count
• architecture where relevant
• local CPU-only practicality
• provider class limits
• when CPU is allowed but not recommended
• canary fallback
• Jet fallback

Output should identify:

• CPU-qualified variants
• CPU-warning variants
• CPU-disqualified variants
• expected install mode

Step 7 - GPU/VRAM Gate

Recover or define GPU rules from known history.

GPU gate should account for:

• no GPU
• GPU present but unknown VRAM
• known VRAM
• CUDA/Metal/DirectML platform differences later
• GPU-required vs GPU-helpful models
• CPU-safe fallback
• Jet fallback

Do not solve detailed Mac Metal or Windows GPU behavior in this first C3 unless approved. Leave Mac and Windows as structured lanes that can import compatible facts later.

Canary Baseline

Canary must be the known-good default install target.

If a selected model is disqualified by disk/RAM/CPU/GPU, 8.2 should choose one of:

• canary local install
• smaller same-family model when supported by recovered sizing facts
• Jet bucket recommendation
• request/manual review
• unavailable/source-exception retained

It must not silently invent a model size.

Jet Bucket Grouping

Jet buckets should sit beside provider/bare-metal gates.

Jet bucket grouping may be based on:

• available disk quantity
• expected model size class
• provider/host lane
• paid customer Docker/OpenWebUI route later

C3 should reserve the metadata needed for later paid Docker routing without inventing final Docker image names or RecordsCore release keys.

Proposed Testing Groups

Use 2-4 test groups before implementing all C3 gates.

Testing Group A - Identity And Loader

Purpose: prove C1/C2 artifacts load correctly before sizing logic is trusted.

Tests:

• 8.2 resolves the profile directory.
• generated family/model/deployment indexes are valid JSON.
• selected family/model/deployment type can be loaded.
• source exceptions cannot be selected for install.
• 8.3 displays 90-result.env without recalculating.

Testing Group B - Provider Baselines

Purpose: prove provider lanes are bucketed correctly before all model variants are mapped.

Use fixtures for:

• bare metal baseline
• AWS Lightsail small/medium/large representative plans
• DigitalOcean small/medium/large representative droplets
• Jet bucket baseline
• canary baseline

Tests:

• disk/RAM/CPU/GPU facts are normalized.
• impossible combinations are disqualified.
• canary fallback is selected when expected.
• Jet recommendation appears when local install is not appropriate.

Testing Group C - Model Size Gates

Purpose: prove model-size decisions work after provider baselines are stable.

Use a small approved sample before all families:

• canary model
• one small CPU-friendly family
• one medium family
• one large family
• one retained source exception

Tests:

• disk gate narrows variants.
• RAM gate narrows variants.
• CPU gate narrows variants.
• GPU gate improves or disqualifies correctly.
• final selected variant is deterministic.

Testing Group D - Full Catalog Dry Run

Purpose: prove the complete artifact set works without hand-checking hundreds of folders.

Tests:

• every approved family has a gate result or explicit unavailable result.
• every approved model has a gate result or explicit unavailable result.
• every deployment variant is retained in metadata.
• no Markdown is parsed by Bash.
• generated sizing-gates.json is deterministic across two runs.
• generated .env exports are shell-safe.

C3 Acceptance Criteria

C3 should not be accepted until:

1. prior sizing history has been recovered or missing history is explicitly listed;
2. hard disk gate artifacts exist;
3. RAM gate artifacts exist;
4. CPU gate artifacts exist;
5. GPU/VRAM gate artifacts exist;
6. canary baseline is defined;
7. Jet bucket grouping is defined;
8. provider baselines exist for bare metal, AWS Lightsail, and DigitalOcean;
9. Mac and Windows remain importable lanes without fake sizing;
10. 8.2 consumes generated JSON/env, not Markdown;
11. 8.3 displays the final result from 8.2;
12. all selected testing groups pass.

Cursor Planning Prompt

```text
Do not implement C3 yet.

Plan C3 for 8-BALL environment gates, covering:
4. hard disk requirement
5. RAM requirement
6. CPU requirement
7. GPU/VRAM requirement

Read CursorFileC1-environment-artifacts.md and CursorFileC2-environment-artifact-sequencing.md first.

Do not guess sizing.

First identify where prior NoCloudGPT sizing history exists for:
- bare metal
- AWS Lightsail
- DigitalOcean Droplets
- canary baseline
- Jet instance buckets

Mac.md and Windows.md already exist as importable deployment lanes. Do not complete Mac/Windows sizing in this C3 planning pass unless explicitly approved.

Create a C3 implementation plan split into 2-4 testing groups before writing large gate logic.

The plan must define:
- disk gate inputs/outputs
- RAM gate inputs/outputs
- CPU gate inputs/outputs
- GPU/VRAM gate inputs/outputs
- canary fallback behavior
- Jet bucket behavior
- provider baseline fixtures
- source-exception behavior
- generated machine formats
- acceptance tests

Do not create final sizing thresholds unless they are recovered from prior approved project history or clearly marked as unresolved.

Report:
- recovered sources found
- missing sources
- proposed testing groups
- files to create
- files to avoid touching
- open questions for approval
