C10 — Glass Ball: AGENTS Data → Real Profiles

Work in the real terminal-glass/8-ball repository.

This is an execution task. Do not create another planning or verification-only PR.
The “glass ball” must make the packed AGENTS/ data visible as actual generated
profile output under root /profiles/.

Objective

Read the complete AGENTS/ tree, unpack its model and hardware data, normalize it,
preserve the source of every value, and generate the real model/size/profile matrix.

AGENTS/ is the authoritative input for this pass. Do not guess missing hardware
limits and do not scrape the internet.

1. Inventory AGENTS first

Recursively inspect every file under:

```text
AGENTS/**
```

Prioritize machine-readable data:

```text
*.csv
*.json
*.jsonl
*.yaml
*.yml
```

Also inspect Markdown or text files when they contain tables, model rows, size
records, provider specifications, or hardware limits. Do not treat Cursor prompts,
roadmaps, or prose as model data unless a parsed row can be identified.

Create these actual output files before generating profiles:

```text
profiles/_agent-input-inventory.json
profiles/_agent-input-inventory.csv
profiles/_agent-normalized-records.jsonl
```

The inventory must record, for every inspected source:

```text
source_path,source_type,parse_status,row_count,recognized_model_rows,
recognized_size_rows,recognized_platform_rows,recognized_hardware_fields,
notes
```

The normalized JSONL must preserve the source path and source row/field wherever
possible. Do not silently discard duplicate or conflicting records.

2. Normalize the AGENTS data

Normalize each usable record into these fields when available:

```text
model_id
model_slug
size_slug
ollama_ref
parameter_size
quantization
minimum_ram_gb
recommended_ram_gb
minimum_vram_gb
recommended_vram_gb
minimum_disk_free_gb
target_lane
fit_status
source_kind
source_path
source_locator
```

Rules:

• Preserve every distinct model-size variant found in AGENTS/.
• Deduplicate only exact duplicates; retain provenance for merged records.
• If sources conflict, preserve both values and mark the record conflict.
• Use null for unknown numeric limits.
• Never fabricate RAM, VRAM, disk, CUDA, GPU, provider, or model-size values.
• Keep the model slug separate from the size slug.
• Size slugs are files, never directories.

3. Generate the real root profiles tree

Create or update:

```text
profiles/
  README.md
  manifest.json
  index.csv
  lanes.json
  _agent-input-inventory.json
  _agent-input-inventory.csv
  _agent-normalized-records.jsonl
  <model-slug>/
    model.json
    sizes.csv
    sizes/<size-slug>.json
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

Every model folder found in the normalized AGENTS data must contain one JSON file
for every distinct size variant:

```text
profiles/<model-slug>/sizes/<size-slug>.json
```

Each size JSON must contain the normalized fields above plus provenance. Use null
when AGENTS does not provide a value.

Every model/platform lane must contain:

```text
lane.json
profile-sizes.csv
3.sh
4.sh
5.sh
6.sh
7.sh
```

Use .ps1 equivalents in Windows lanes. Reuse or adapt the existing public
installer/stage files; do not redesign the installer in this task.

The lane’s profile-sizes.csv must list every applicable size file and its fit
status for that lane. It must never point to a missing JSON file.

4. Generate the matrix indexes

profiles/index.csv must contain one row for every distinct normalized
model-size-lane combination, with at least:

```text
model_id,model_slug,size_slug,ollama_ref,size_file,target_lane,
profile_lane_path,install_path,fit_status,minimum_ram_gb,
recommended_ram_gb,minimum_vram_gb,recommended_vram_gb,
minimum_disk_free_gb,source_kind,source_path,source_locator
```

The generator must print and write a report containing:

```text
AGENTS files inspected
AGENTS files parsed
model count
distinct model-size count
install lane count
profile lane count
matrix row count
records with unknown limits
records with conflicts
records skipped and why
```

Do not claim a 40,000-row result unless the generated index actually contains that
many rows. The count must come from the data.

5. Use a generator, not hand-created output

Create or update:

```text
scripts/generate-profiles-from-agents.py
scripts/validate-profiles-from-agents.py
```

The generator must be repeatable. Running it twice must not create duplicate rows,
unstable filenames, or unexplained changes.

The validator must fail when:

• AGENTS/ was not inventoried;
• root /profiles/ is missing;
• a model-size record has no corresponding sizes/<size-slug>.json;
• a size slug was created as a directory;
• a required install/profile lane is missing;
• a lane is missing its step 3–7 payload;
• an index references a missing file;
• provenance is missing;
• numeric limits were fabricated;
• matrix counts do not match the generated records.

6. Required execution

Run the generator against the real repository data:

```bash
python3 scripts/generate-profiles-from-agents.py
python3 scripts/validate-profiles-from-agents.py
```

Then run relevant syntax checks:

```bash
find install profiles -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
```

If PowerShell is available, syntax-check the .ps1 files too.

Non-negotiable boundaries

• Create actual /profiles/ output now.
• Pull from AGENTS/ now; do not defer the data extraction.
• Do not hide profiles under AGENTS/data-science/profiles/.
• Do not create install/linux/.
• Do not create model-size directories.
• Do not scrape or invent data.
• Do not turn Cursor prompt files into fake model records.
• Do not replace the entire installer architecture.

Final response required from Cursor

Report:

1. Exact files changed or generated.
2. Exact /profiles/ tree created.
3. AGENTS files inspected and parse results.
4. Model count, model-size count, lane count, and matrix row count.
5. Unknown-limit and conflict counts.
6. Validation commands and pass/fail results.
7. Any remaining missing AGENTS data, with source paths named exactly.

The work is complete only when the generated /profiles/ tree and its indexes are
present in the branch and the validator passes.