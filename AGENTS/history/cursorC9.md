C9 Cursor Prompt: Size Slug Files, Not Size Folders

We are working in the real terminal-glass/8-ball repository.

What This Fixes

C8 incorrectly treated model-size slugs as directories:

```text
profiles/<model-slug>/<size-slug>/<platform-or-hardware-lane>/
```

Do not use that shape.

The corrected shape is:

```text
profiles/<model-slug>/sizes/<size-slug>.json
profiles/<model-slug>/<platform-or-hardware-lane>/
```

The size slug is a file, not a folder.

Goal

Create the public install/profile matrix using:

1. Full duplicated installer folders under root /install/.
2. Model-first profile folders under root /profiles/.
3. Size variants as slug JSON files inside each model folder.
4. Profile/platform folders that mirror /install/.
5. One generated index row for every model-size-lane combination.

This gives us the large matrix, potentially around 40,000 model-size-platform possibilities, without creating 40,000 deeply nested size directories.

Required Install Lanes

Create and populate these exact install leaves:

```text
install/ubuntu/cpu/
install/ubuntu/cuda/
install/mac/apple-silicon/
install/mac/intel/
install/windows/cpu/
install/windows/cuda/
install/cloud/digitalocean/cpu-droplet/
install/cloud/digitalocean/gpu-droplet/
install/cloud/aws-lightsail/cpu/
install/cloud/aws-lightsail/gpu/
```

Do not create install/linux/.

Each install leaf must contain the complete public installer file set for that platform/hardware lane. Do not leave placeholder-only folders.

For shell-based lanes, duplicate/adapt the public shell files already in the repo or supplied bundle.

Expected shell file pattern:

```text
trial-install.sh
8.1.sh
8.2.sh
8.3.sh
```

If the current repo still uses split numbered stage files, also include/adapt:

```text
3.sh
4.sh
5.sh
6.sh
7.sh
```

For Windows lanes, create PowerShell equivalents:

```text
trial-install.ps1
8.1.ps1
8.2.ps1
8.3.ps1
```

If stage files are needed for profile steps, include:

```text
3.ps1
4.ps1
5.ps1
6.ps1
7.ps1
```

Correct Profiles Shape

Create root /profiles/.

The model folder comes first.

Inside each model folder:

```text
profiles/<model-slug>/
  model.json
  sizes.csv
  sizes/
    <size-slug>.json
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

Every platform/hardware profile leaf mirrors /install/.

Example:

```text
install/ubuntu/cpu/
profiles/qwen3/ubuntu/cpu/

install/cloud/digitalocean/gpu-droplet/
profiles/qwen3/cloud/digitalocean/gpu-droplet/

install/cloud/aws-lightsail/gpu/
profiles/gemma3/cloud/aws-lightsail/gpu/
```

Size Slug Files

Model size variants must be files:

```text
profiles/<model-slug>/sizes/<size-slug>.json
```

Examples:

```text
profiles/qwen3/sizes/0.6b.json
profiles/qwen3/sizes/1.7b.json
profiles/qwen3/sizes/4b.json
profiles/qwen3/sizes/8b.json
profiles/qwen3/sizes/14b.json
profiles/llama3.1/sizes/8b.json
profiles/deepseek-r1/sizes/14b.json
```

Do not create:

```text
profiles/qwen3/0.6b/
profiles/qwen3/14b/ubuntu/cuda/
profiles/<model>/<platform>/<size>/
profiles/<model-with-size-baked-in>/<platform>/
```

Each size JSON file must include at least:

```json
{
  "model_id": "",
  "model_slug": "",
  "size_slug": "",
  "ollama_ref": "",
  "parameter_size": "",
  "quantization": "",
  "minimum_ram_gb": null,
  "recommended_ram_gb": null,
  "minimum_vram_gb": null,
  "recommended_vram_gb": null,
  "minimum_disk_free_gb": null,
  "source_kind": "",
  "source_path": ""
}
```

Use null when a limit is genuinely unknown. Do not invent limits.

Profile Lane Files

Every final profile lane must contain the duplicated profile-specific payload files for steps 3 through 7.

Shell lane example:

```text
profiles/qwen3/ubuntu/cpu/
  lane.json
  profile-sizes.csv
  3.sh
  4.sh
  5.sh
  6.sh
  7.sh
```

Windows lane example:

```text
profiles/qwen3/windows/cuda/
  lane.json
  profile-sizes.csv
  3.ps1
  4.ps1
  5.ps1
  6.ps1
  7.ps1
```

profile-sizes.csv lists the size slug files available for that model/lane.

Required columns:

```text
model_id,model_slug,size_slug,ollama_ref,size_file,target_lane,lane_path,fit_status,minimum_ram_gb,recommended_ram_gb,minimum_vram_gb,recommended_vram_gb,minimum_disk_free_gb,source_kind,source_path
```

The profile lane scripts should read/select a size slug file. They should not rely on a size slug directory.

Root Profile Index Files

Create:

```text
profiles/README.md
profiles/manifest.json
profiles/index.csv
profiles/lanes.json
```

profiles/index.csv must contain one row per model-size-lane combination.

Required columns:

```text
model_id,model_slug,size_slug,ollama_ref,size_file,target_lane,profile_lane_path,install_path,fit_status,minimum_ram_gb,recommended_ram_gb,minimum_vram_gb,recommended_vram_gb,minimum_disk_free_gb,source_kind,source_path
```

The expected final matrix count is:

```text
profiles/index.csv row count = total size slug files * install lane count
```

The lane folder count is:

```text
profile lane folder count = model count * install lane count
```

Do not validate against:

```text
model_size_count * install_lane_count folders
```

because size slugs are files, not folders.

Slug Rules

Model slug:

• Start from the model family/name before the Ollama tag size where possible.
• Lowercase.
• Replace spaces and slashes with hyphens.
• Keep meaningful dots when already used by model names, such as llama3.1.
• Do not bake size into model slug when the size can be separated.

Size slug:

• Start from the model tag/size portion.
• Lowercase.
• Preserve readable size labels like 0.6b, 7b, 8b, 14b, 70b.
• Preserve useful suffixes like 7b-instruct.
• Store as a JSON filename under sizes/.

Examples:

```text
qwen3:0.6b           -> profiles/qwen3/sizes/0.6b.json
llama3.1:8b         -> profiles/llama3.1/sizes/8b.json
deepseek-r1:14b     -> profiles/deepseek-r1/sizes/14b.json
mistral:7b-instruct -> profiles/mistral/sizes/7b-instruct.json
```

Data Sources

Do a repo-local data extraction first.

Primary source:

```text
data/generated/pages/install-manifest.json
data/generated/pages/**
```

Secondary source, only if needed:

```text
AGENTS/data-science/*.csv
TG-8Ball-*.csv
```

Reference only:

```text
CursorFile*.md
cursorFile*.md
AGENTS/**/*.md
```

Do not blindly crawl every repo file and call it profile data.

Do not use old prompt files as canonical data.

Does This Need A Data Scrape?

No external scrape for the first Cursor pass.

First, generate the slug files from repo-owned canonical data and CSV exports.

Only create a separate data-refresh task if the repo does not contain enough model-size data to generate profiles/<model>/sizes/*.json.

If data is missing, create:

```text
profiles/DATA-REFRESH-NEEDED.md
```

That file must list:

• missing canonical source files
• missing model-size fields
• which rows could not be generated
• recommended external sources to scrape later

Do not scrape the public internet inside this PR unless explicitly approved.

If a later external scrape is approved, prefer official/model-owned sources first, such as Ollama model/tag pages or upstream model metadata. Keep that as a separate data-refresh PR.

Generator Requirement

Do not hand-create thousands of files.

Create or update generator scripts:

```text
scripts/generate-size-slug-profile-files.py
scripts/validate-size-slug-profile-files.py
```

The generator must:

1. Read canonical model/catalog data.
2. Derive model slugs.
3. Derive size slugs.
4. Create one profiles/<model>/sizes/<size>.json per model-size variant.
5. Create one profile lane folder per model per install lane.
6. Copy/adapt the step 3 through 7 files into every profile lane.
7. Create/update root profile indexes.
8. Create/update per-model sizes.csv.
9. Create/update per-lane profile-sizes.csv.

Validation

Run:

```bash
python scripts/generate-size-slug-profile-files.py
python scripts/validate-size-slug-profile-files.py
bash -n $(find install profiles -name '*.sh' -type f)
```

If PowerShell is available, also run:

```powershell
pwsh -NoProfile -Command "Get-ChildItem -Recurse install,profiles -Filter *.ps1 | ForEach-Object { [scriptblock]::Create((Get-Content -Raw $_.FullName)) | Out-Null }"
```

Validation must fail if:

• install/linux/ exists.
• any required install lane is missing.
• an install lane is empty.
• /profiles/ is missing.
• size slug directories exist as the main shape.
• any size slug file listed in an index is missing.
• any profile lane folder is missing 3 through 7 payload files.
• profiles/index.csv row count does not equal total size slug files * install lane count.
• profile-sizes.csv references missing size JSON files.

Final Output Required From Cursor

Report:

• files changed
• install lane folders created
• model count
• total size slug JSON files created
• install lane count
• total generated matrix rows in profiles/index.csv
• whether any external scrape is needed later
• validation commands run
• remaining blockers

Non-Negotiable Shape

Correct:

```text
install/<platform-or-hardware-lane>/
profiles/<model-slug>/sizes/<size-slug>.json
profiles/<model-slug>/<platform-or-hardware-lane>/
```

Incorrect:

```text
install/linux/
profiles/<model-slug>/<size-slug>/<platform-or-hardware-lane>/
profiles/<model-slug>/<platform-or-hardware-lane>/<size-slug>/
profiles/<model-size-slug>/<platform-or-hardware-lane>/
AGENTS/data-science/profiles/
```