Cursor task — C10 model pages, lane labels, and executable install matrix

Work in the real terminal-glass/8-ball repository. terminal-glass is the
public repository and product namespace; funtech64 is internal only and must
not appear in customer-facing repository URLs or commands. The C10 working
files described below live in the repository's AGENTS/ directory
(terminal-glass/AGENTS/). This task supersedes the old C6–C10 folder
instructions. Execute the work and generate the files; do not return another
verification-only plan.

0. Immutable base prompt and self-recording rule

This complete prompt is the immutable base instruction. Do not rename, rewrite,
or move this base prompt as part of the task. It is the one exception to the
active Cursor-file naming rule below.

Before executing a later C10 scope, save the entire later prompt verbatim—not a
summary, excerpt, or separate copy-paste handoff—in the repository's
AGENTS/ directory using this convention:

```text
AGENTS/cursorFile<letter>10.<dataset_version>-<stage>-<install-type-or-provider-assumption>.md
```

Examples:

```text
AGENTS/cursorFile.C10.1-1-windows.md
AGENTS/cursorFile.C10.1-2-mac-apple-silicon.md
AGENTS/cursorFile.C10.1-7-mac-apple-silicon-video-card.md
AGENTS/cursorFile.C10.2-1-ubuntu-cuda.md
AGENTS/cursorFile.C10.2-1-cloud-digitalocean-gpu-droplet.md
```

The saved file must contain the whole prompt in its entirety and must be the
active instruction for that stage and scope. When a later prompt becomes
active, move the previous active prompt into AGENTS/history/, preserving its
contents and original filename. Do not leave old prompts in working data
directories where a future Cursor run could mistake them for model data.

Do not create a separate end-user copy-paste file for the prompt: the complete
prompt saved in AGENTS/ is the record. Earlier or unrelated prompts must not
remain alongside active working data and confuse the next agent operation.

1. Fixed C10 naming rule for later active files

Except for this immutable base prompt, use this exact identity for C10 work
folders and later active Cursor files:

```text
C10.<generation>-<stage>-<scope>
```

Examples:

```text
cursorFile.C10.1-1-windows.md
cursorFile.C10.1-2-mac-apple-silicon.md
cursorFile.C10.1-7-mac-apple-silicon-video-card.md
cursorFile.C10.2-1-ubuntu-cuda.md
cursorFile.C10.2-1-cloud-digitalocean-gpu-droplet.md
```

Rules:

• <generation> is the first number after C10.. Advance it only when the
source CSV/data foundation for that scope is discarded and rebuilt.
• <stage> is the second number after the hyphen. It is permanently 1–7.
Never renumber it when data is replaced.
• Generation is tracked independently per scope. A GPU restart does not rename
Windows, Ubuntu, Mac, or another provider's work.
• Use lowercase kebab-case for filesystem scopes.
• A normal Cursor revision may use an alphabetic history suffix (-A, -B,
-C) without changing either C10 number.
• Never put C10, 10-b, or a platform name into a model slug.

Fixed stage meanings:

```text
1 = model identity and model data page
2 = size records and promoted Ollama references
3 = CPU
4 = RAM
5 = hard disk
6 = CPU-only fallback
7 = video card, GPU, CUDA, or Apple GPU
```

The existing leaf labels are authoritative and must not be changed:

```text
3-cpu
4-ram
5-hard_disk
6-CPU_only
7-video_card
```

2. Move Cursor instructions into history

Create this directory in the repository root:

```text
AGENTS/history/
```

Move every old Cursor handoff/instruction file matching cursor*.md,
CursorFile*.md, and the old C6–C10 handoff files into
AGENTS/history/. Use git mv; do not silently delete content. Rename them
to the C10 convention only when their scope and stage are known. Preserve the
original filename in AGENTS/history/README.md. Do not move or rename this
immutable base prompt.

Every later active file must use the same convention. Do not leave old prompts
in the working data directories where a future Cursor run could treat them as
model data.

3. Keep the data-science source areas clear

Preserve the existing Ollama mapping source data here:

```text
AGENTS/data-science/ollama-mapping/P1-**/**
AGENTS/data-science/ollama-mapping/P2-**/**
...
AGENTS/data-science/ollama-mapping/P7-**/**
```

Put the C10 working CSVs, reports, and generated mapping evidence here:

```text
AGENTS/data-science/profile-mapping/
```

Keep the Ollama source area and the C10 profile-mapping area separate. Do not
move, rename, overwrite, or treat the P1–P7 source datasets as generated
C10 output.

Use scope-specific C10 directories, for example:

```text
AGENTS/data-science/profile-mapping/C10.1-1-windows/
AGENTS/data-science/profile-mapping/C10.1-2-windows/
AGENTS/data-science/profile-mapping/C10.1-7-windows-video-card/
AGENTS/data-science/profile-mapping/C10.2-1-ubuntu-cuda/
```

Do not create empty placeholder folders. Every created C10 directory must
contain an input, output, report, or explicit DATA-GAP.md. Do not move or
rename the P1–P7 source datasets.

4. Model data pages: files, not size folders

Read the existing CSV/JSON data under
AGENTS/data-science/ollama-mapping/P1-**/** through
AGENTS/data-science/ollama-mapping/P7-**/** and normalize it. Create one
machine-readable model data page per model:

```text
profiles/<model-slug>.json
```

The model page must contain all known size variants in descending parameter
size. Each size record must retain its exact Ollama reference, for example:

```json
{
  "model_slug": "gemma4",
  "sizes": [
    {"size_slug": "30b", "ollama_ref": "gemma4:30b"},
    {"size_slug": "12b", "ollama_ref": "gemma4:12b"},
    {"size_slug": "4b", "ollama_ref": "gemma4:4b"}
  ]
}
```

Rules:

• The model slug is the human-first model name: gemma4, qwen3,
llama3.1, and so on.
• Size belongs in size_slug and ollama_ref; it does not belong in the
model slug or the model page filename.
• Use 30b, not 30-b; never append a C10 or stage label to a model name.
• Do not create profiles/<model>/30b/ or any other size directory.
• Do not create a families/ machine-data tree. Families may remain only as
clearly marked human documentation under AGENTS/history/.
• Do not create empty models/, sizes/, deployment-classes/, or
families/ folders in /profiles/.
• Preserve provenance and conflicting source values. Use null for unknown
measurements; never invent RAM, VRAM, CPU, disk, or provider limits.

5. Mirror the install lanes with real, non-empty profile leaves

Create these exact install lanes, including cloud and GPU lanes:

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

Every install lane must contain the executable installer payload appropriate
to that lane. Do not create install/linux/. Do not leave a lane empty or
filled with placeholder text.

Mirror every model/lane combination under /profiles/:

```text
profiles/<model-slug>/ubuntu/cpu/
profiles/<model-slug>/ubuntu/cuda/
profiles/<model-slug>/mac/apple-silicon/
profiles/<model-slug>/mac/intel/
profiles/<model-slug>/windows/cpu/
profiles/<model-slug>/windows/cuda/
profiles/<model-slug>/cloud/digitalocean/cpu-droplet/
profiles/<model-slug>/cloud/digitalocean/gpu-droplet/
profiles/<model-slug>/cloud/aws-lightsail/cpu/
profiles/<model-slug>/cloud/aws-lightsail/gpu/
```

Each applicable profile leaf must contain actual data files, not empty
directories:

```text
lane.json
3-cpu.json
4-ram.json
5-hard_disk.json
6-CPU_only.json
7-video_card.json
```

If a leaf is not applicable to a platform, keep the file with
"applicable": false and a source-backed reason. Do not silently omit the
stage and do not fabricate a positive capability.

6. Provider assumptions must be explicit and testable

Create one provider-assumption file per install lane:

```text
profiles/provider-assumptions/ubuntu-cpu.json
profiles/provider-assumptions/ubuntu-cuda.json
profiles/provider-assumptions/mac-apple-silicon.json
profiles/provider-assumptions/mac-intel.json
profiles/provider-assumptions/windows-cpu.json
profiles/provider-assumptions/windows-cuda.json
profiles/provider-assumptions/cloud-digitalocean-cpu-droplet.json
profiles/provider-assumptions/cloud-digitalocean-gpu-droplet.json
profiles/provider-assumptions/cloud-aws-lightsail-cpu.json
profiles/provider-assumptions/cloud-aws-lightsail-gpu.json
```

Each file must identify the platform, provider, architecture, hardware signals
to detect, and the source of each assumption. The installer must use these
files to determine the mini platform/provider lane before selecting a model
size. An install smoke test must record whether the lane was actually usable.

7. Customer command and model selection

The public entrypoint must accept a base model slug:

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/trial-install.sh | sh -s -- gemma4
```

Implement this behavior:

1. Install or verify Ollama using the existing public flow.
2. Detect OS, architecture, CPU, RAM, free disk, video card, CUDA/Apple GPU,
and cloud/provider clues.
3. Select the matching install lane and its provider-assumption file.
4. Read profiles/<model-slug>.json.
5. Select the largest listed size that fits the detected lane, starting with
the promoted size and falling back to the next smaller size when needed.
6. Pull and run the exact selected reference, such as:
ollama run gemma4:30b.
7. If a pull fails, try the next smaller valid size and record the fallback.

The end user supplies gemma4, not gemma4:10-b and not a C10-labeled name.

8. Data source and online checks

Use the existing AGENTS/ CSV/JSON data as the primary source. Do not rebuild
the catalog by blindly scraping every Ollama page. If an Ollama page is needed
to resolve an exact model tag or missing source field, use the official model
page, record its URL and retrieval date, and mark the value as fetched. Never
silently replace a measured CSV value with a live guess.

9. Execute and validate

Create or update a repeatable generator and validator. Then run them against
the real repository data. Validate that:

• every model has one <model-slug>.json page;
• sizes are descending and are files/records, never directories;
• no model name contains a C10 label or 10-b suffix;
• every install lane is non-empty;
• every model/lane profile leaf contains the stage files 3–7;
• provider assumptions exist and are referenced;
• /profiles/* mirrors /install/*;
• every ollama_ref is a valid model-plus-tag reference;
• no index points to a missing file;
• provenance exists for every non-null measurement;
• shell files pass bash -n, and PowerShell files are checked when available.

Write the generated counts and any data gaps to:

```text
AGENTS/data-science/profile-mapping/C10-generation-report.md
```

The final Cursor response must list the exact files created/moved, the model
and size counts, the install/profile lane counts, the provider-assumption
smoke-test results, and any unresolved data gaps. The task is complete only
when the actual /profiles/ and /install/ trees exist and are non-empty.
