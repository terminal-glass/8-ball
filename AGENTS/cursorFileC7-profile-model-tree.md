C7 Cursor Prompt: Create the Full Install/Profile Matrix

We are working in the real terminal-glass/8-ball repository.

This is a creation task, not another verification-only task.

Create the root install/profile matrix now.

Core Rule

Every installer lane under /install/ must have matching profile lanes under /profiles/<model>/.

The shape is:

```text
install/<platform-or-hardware-lane>/*
profiles/<model-slug>/<same-platform-or-hardware-lane>/*
```

Examples:

```text
install/ubuntu/cpu/*
profiles/qwen3-0.6b/ubuntu/cpu/*

install/cloud/digitalocean/gpu-droplet/*
profiles/qwen3-0.6b/cloud/digitalocean/gpu-droplet/*

install/cloud/aws-lightsail/gpu/*
profiles/qwen3-0.6b/cloud/aws-lightsail/gpu/*

install/ubuntu/cuda/*
profiles/qwen3-0.6b/ubuntu/cuda/*
```

Do not create or use:

```text
install/linux/
profiles/linux/
profiles/ubuntu-only-flat-tree/
```

profiles/ is model-first. The platform/hardware path comes after the model.

Required Install Lanes

Create these install lanes in the first commit:

```text
install/
  README.md
  ubuntu/
    cpu/
    cuda/
  mac/
    apple-silicon/
    intel/
  windows/
    cpu/
    cuda/
  cloud/
    digitalocean/
      cpu-droplet/
      gpu-droplet/
    aws-lightsail/
      cpu/
      gpu/
```

These lanes are required because the public installer must cover:

• Ubuntu CPU
• Ubuntu CUDA/GPU servers
• Mac
• Windows
• DigitalOcean CPU droplets
• DigitalOcean GPU droplets
• AWS Lightsail CPU
• AWS Lightsail GPU

If the repo has already standardized slightly different lane names, keep the names above unless changing them is absolutely required by existing code. If you must change a lane name, document the exact reason in install/MATRIX-NOTES.md.

Required Files in Every Install Lane

Every install lane must contain the full public installer file set.

For shell-based lanes:

```text
README.md
trial-install.sh
8.1.sh
8.2.sh
8.3.sh
assets/
  first-MOTD.txt
```

Shell-based lanes are:

```text
install/ubuntu/cpu/
install/ubuntu/cuda/
install/mac/apple-silicon/
install/mac/intel/
install/cloud/digitalocean/cpu-droplet/
install/cloud/digitalocean/gpu-droplet/
install/cloud/aws-lightsail/cpu/
install/cloud/aws-lightsail/gpu/
```

For Windows lanes:

```text
README.md
trial-install.ps1
8.1.ps1
8.2.ps1
8.3.ps1
assets/
  first-MOTD.txt
```

Windows lanes are:

```text
install/windows/cpu/
install/windows/cuda/
```

Do not leave a lane with only a README.
Do not leave a lane as an empty directory.
Do not rely only on a top-level script that routes elsewhere.
The files must physically exist inside each lane.

Source Files to Duplicate

Use the actual repo source files if present:

```text
trial-install.sh
8.1.sh
8.2.sh
8.3.sh
first-MOTD.txt
install.sh
```

If the source scripts live in another folder, find them with:

```bash
rg --files | rg '(^|/)(trial-install|8\.1|8\.2|8\.3|first-MOTD|[0-7]|install)\.(sh|ps1|txt)$'
```


For platform-specific lanes:

• Ubuntu CPU can use the direct shell baseline.
• Ubuntu CUDA must include GPU/CUDA detection and GPU-safe notes.
• DigitalOcean CPU droplet can derive from Ubuntu CPU but must be its own file copy.
• DigitalOcean GPU droplet can derive from Ubuntu CUDA but must be its own file copy.
• AWS Lightsail CPU can derive from Ubuntu CPU but must be its own file copy.
• AWS Lightsail GPU can derive from Ubuntu CUDA but must be its own file copy.
• Mac lanes must be real Mac shell files, not Ubuntu scripts pretending to be Mac.
• Windows lanes must be PowerShell files, not .sh files.

If a platform cannot be fully functional yet, create the full lane anyway and make the script exit with a clear message naming the missing implementation. Do not silently omit the file.

Required Profiles Root

Create root-level /profiles/ in the first commit:

```text
profiles/
  README.md
  manifest.json
  index.csv
```

profiles/README.md must explain:

• profiles/ is model-first.
• Each model folder mirrors the /install/ platform/hardware matrix.
• The duplicated step files under each model/platform lane are the profile-specific installer payload for steps 3 through 7.
• Generated profile data is derived from canonical catalog data.
• The public installer consumes /profiles/<model>/<platform-or-hardware-lane>/.

profiles/manifest.json must list:

• schema version
• generated timestamp
• source catalog path
• total models
• target lane list
• model slug mapping

profiles/index.csv must list:

```text
model_id,model_slug,target_lane,profile_path,install_path,status,source_path
```

Required Profile Matrix

For every model in the canonical catalog, create a model folder:

```text
profiles/<model-slug>/
```

Inside every model folder, duplicate the full platform/hardware target matrix:

```text
profiles/<model-slug>/
  README.md
  manifest.json
  ubuntu/
    cpu/
    cuda/
  mac/
    apple-silicon/
    intel/
  windows/
    cpu/
    cuda/
  cloud/
    digitalocean/
      cpu-droplet/
      gpu-droplet/
    aws-lightsail/
      cpu/
      gpu/
```

Every leaf profile lane must contain files for steps 3 through 7.

For shell-based profile lanes:

```text
README.md
profile.json
3-CPU
4-RAM
5-Hard-Disk
6-CPU-Only
7-Video-Card
```

For Windows profile lanes:

```text
README.md
profile.json
3-CPU
4-RAM
5-Hard-Disk
6-CPU-Only
7-Video-Card
```

The step files in /profiles/<model>/<target>/ are allowed to be generated from templates, but they must be real files with the model and target lane wired into them.

Do not create empty model folders.
Do not create only JSON and skip steps 3 through 7.
Do not hide profile-specific data under AGENTS/.
Do not create a flat /profiles/ubuntu/ tree as the main structure.

Canonical Catalog Source

Use the repo-owned canonical generated catalog as input.

Check these locations in order:

```text
data/generated/pages/install-manifest.json
data/generated/pages/
data/generated/
catalog/
AGENTS/data-science/
TG-8Ball-*.csv
```

Rules:

• Use data/generated/pages/install-manifest.json if it exists.
• If the manifest exists, derive model ids and install targets from it.
• If the manifest does not include every target lane listed above, still create the target lanes and mark profile status as missing-target-data.
• If the only available inputs are CSV files, derive the model list from CSV rows and document which CSV was used.
• Do not invent model ids.
• Do not invent model specs.
• Do not invent hardware sizing.
• Do not crawl planning files as if they are profile data.

Slug Rules

Model ids may NOT contain slashes, colons, dots, or spaces. files inside the folders will have the identifying slug files wirhin them laree

BAD model slugs:

```text
qwen3:0.6b        
gemma3:1b         
library/model:tag
```
GOOD model slugs:

qwen3
gemma3



Missing Data Rule

The folders and file lanes still get created even if canonical profile data is incomplete. we are assuming a lot of this ar this stage.

If canonical input is missing, create the folders and leave blamk

These files must state:

• exact files searched
• exact missing source input
• which folders were still created
• which files are working versus placeholders
• exact command or repo task needed to regenerate the missing data

Do not stop after saying “not found.”
Do not make another verification-only PR.

Generator Is Allowed, Output Is Required

You may write a generator script such as:

```text
scripts/generate-install-profile-matrix.py
```

But the PR must commit the generated output tree:

```text
install/**
profiles/**
```

Do not commit only the generator.
Do not tell the user to run the generator later.

Validation Required

Add a validator if one does not exist:

```text
scripts/validate-install-profile-matrix.py
```


Run at least:

```bash
python scripts/validate-install-profile-matrix.py
bash -n $(find install profiles -name '*.sh' -type f)
```

If pwsh is available, also parse/check:

```bash
pwsh -NoProfile -Command "Get-ChildItem -Recurse install,profiles -Filter *.ps1 | ForEach-Object { [scriptblock]::Create((Get-Content -Raw $_.FullName)) | Out-Null }"
```

Run existing repo tests and validators too.

Required Final Report

At the end, report:

• files and folders created
• exact install lanes created
• total models found
• total profile model folders created
• total profile target lanes created
• whether every profile target has steps 3 through 7
• validation commands run
• any missing canonical data
• whether Mac/Windows/GPU lanes are functional or present-but-pending

Non-Negotiables

• One public repo.
• Root /install/.
• Root /profiles/.
• No /install/linux/.
• /profiles/ is model-first.
• Every /install/ platform/hardware lane gets the duplicated installer files.
• Every /profiles/<model>/ tree mirrors /install/.
• Steps 3 through 7 are physically present under every profile target lane.
• Include GPU lanes now: CUDA, DigitalOcean GPU droplet, AWS Lightsail GPU.
• Do not hide this under AGENTS/.
• Do not make another PR that only verifies.