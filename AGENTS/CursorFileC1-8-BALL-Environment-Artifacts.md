CursorFileC1 - 8-BALL Environment Artifacts

Purpose

Create a clean environment-artifact process so 8.2 can make intelligent install decisions without guessing.

The current installer history already has useful deployment work: /opt/philosopher/instance.env, network detection, swap checks, Linux package setup, Passport/RecordsCore flow, and prior bare-metal/cloud thinking. What is missing is a stable profile contract that 8.2, 8.3, Mac importers, Windows importers, and the website selector can all understand.

This file defines the next safe step: create a profiles directory and teach 8.2 to load environment artifacts from it, unless an earlier folder was explicitly designated.

Design Rule

Do not make 8.2 guess all model/instance sizing.

8.2 may measure hardware. It may load known profile facts. It may select from a sizing manifest once that manifest exists. It must not invent unsupported RAM, CPU, GPU, disk, provider, or model-family sizing rules.

Runtime Directory

Create this runtime directory during bootstrap:

```bash
/opt/philosopher/profiles
```

Keep this legacy file for backward compatibility:

```bash
/opt/philosopher/instance.env
```

The repo should also contain a source scaffold:

```bash
profiles/
```

The repo-side profiles/ directory is documentation/templates only. The live installer writes to /opt/philosopher/profiles.

Profile Directory Precedence

8.2 should resolve the profile directory in this order:

1. --profile-dir <path> argument, if added to the script.
2. EIGHTBALL_PROFILE_DIR, if already exported.
3. NCGPT_PROFILE_DIR, if already exported.
4. PROFILE_DIR or EIGHTBALL_PROFILE_DIR loaded from /opt/philosopher/instance.env.
5. Default: /opt/philosopher/profiles.

If none of the profile artifacts exist, 8.2 should fall back to the legacy behavior of sourcing /opt/philosopher/instance.env.

Artifact Files

Use deterministic file names so Mac, Windows, WSL, Linux, AWS Lightsail, DigitalOcean, and bare-metal adapters can all write the same contract.

|File                   |Writer                            |Purpose                                                                        |
|-----------------------|----------------------------------|-------------------------------------------------------------------------------|
|`00-instance.env`      |`0.sh` or platform importer       |Normalized install root, host, network, and URL facts.                         |
|`10-platform.env`      |`8.2` or importer                 |OS, provider, instance class, architecture, virtualization/container facts.    |
|`20-hardware.env`      |`8.2` or importer                 |Measured RAM, CPU threads, disk, GPU, VRAM, and hardware notes.                |
|`30-catalog.env`       |catalog/pinning step              |Catalog version, projection version, sizing-manifest version, and source paths.|
|`40-selection.env`     |website/auth installer or operator|Requested family/model/variant/deployment mode.                                |
|`50-recommendation.env`|`8.2`                             |Recommended install target, fallback target, and reason codes.                 |
|`90-result.env`        |`8.2`                             |Final result that `8.3` can display.                                           |

All files must be shell-safe KEY="value" environment files.

Minimum Variables

Use these names consistently.

|Variable                           |Meaning                                                                         |
|-----------------------------------|--------------------------------------------------------------------------------|
|`EIGHTBALL_PROFILE_SCHEMA_VERSION` |Profile artifact schema version. Start with `1`.                                |
|`EIGHTBALL_PROFILE_DIR`            |Resolved runtime profile directory.                                             |
|`NCGPT_ROOT`                       |Install root, normally `/opt/philosopher`.                                      |
|`INSTANCE_ADDRESS`                 |Browser-accessible host/IP, legacy-compatible.                                  |
|`PRIVATE_IP`                       |Private bind address, legacy-compatible.                                        |
|`HOST_NAME`                        |Machine hostname.                                                               |
|`PUBLIC_BASE_DOMAIN`               |Public base domain or nip.io fallback.                                          |
|`EIGHTBALL_OS_FAMILY`              |`linux`, `macos`, `windows`, `wsl`, or `unknown`.                               |
|`EIGHTBALL_PROVIDER`               |`bare_metal`, `aws_lightsail`, `digitalocean`, `mac`, `windows`, `unknown`, etc.|
|`EIGHTBALL_INSTANCE_CLASS`         |Provider size/shape when known, such as a Lightsail or Droplet plan.            |
|`EIGHTBALL_RAM_MB`                 |Measured RAM in MB.                                                             |
|`EIGHTBALL_CPU_THREADS`            |Measured CPU threads.                                                           |
|`EIGHTBALL_DISK_FREE_GB`           |Free install disk in GB.                                                        |
|`EIGHTBALL_GPU_PRESENT`            |`yes`, `no`, or `unknown`.                                                      |
|`EIGHTBALL_GPU_NAME`               |GPU name if known.                                                              |
|`EIGHTBALL_GPU_VRAM_MB`            |GPU VRAM in MB if known.                                                        |
|`EIGHTBALL_CATALOG_VERSION`        |Pinned 8-BALL catalog/projection version.                                       |
|`EIGHTBALL_SIZING_MANIFEST_VERSION`|Pinned sizing manifest version.                                                 |
|`EIGHTBALL_SELECTED_FAMILY_ID`     |Selected model family ID.                                                       |
|`EIGHTBALL_SELECTED_MODEL_ID`      |Selected canonical model ID.                                                    |
|`EIGHTBALL_SELECTED_VARIANT_TAG`   |Selected Ollama tag/variant.                                                    |
|`EIGHTBALL_INSTALL_MODE`           |`local`, `jet`, `request`, or `unknown`.                                        |

How 0.sh Should Behave

0.sh should still generate /opt/philosopher/instance.env because existing scripts depend on it.

Add this behavior:

1. Create /opt/philosopher/profiles.
2. Write /opt/philosopher/profiles/00-instance.env.
3. Include EIGHTBALL_PROFILE_DIR="/opt/philosopher/profiles" in both files.
4. Keep legacy variables such as INSTANCE_ADDRESS, PRIVATE_IP, HOST_NAME, CHAT_URL, and WIKI_URL.

This keeps the old installer path working while giving new scripts a richer artifact location.

How 8.2 Should Behave

8.2 should do four jobs:

1. Resolve the profile directory.
2. Load existing profile artifacts in deterministic order.
3. Measure missing hardware facts and write 20-hardware.env.
4. Use the future sizing manifest to write 50-recommendation.env and 90-result.env.

Recommended load order:

```bash
/opt/philosopher/instance.env
${EIGHTBALL_PROFILE_DIR}/00-instance.env
${EIGHTBALL_PROFILE_DIR}/10-platform.env
${EIGHTBALL_PROFILE_DIR}/20-hardware.env
${EIGHTBALL_PROFILE_DIR}/30-catalog.env
${EIGHTBALL_PROFILE_DIR}/40-selection.env
```

Later files may override earlier defaults, but 8.2 should log every file it loads.

If required profile data is missing, 8.2 should produce a clear warning and continue only when it can safely fall back. For model sizing, fallback must be explicit and conservative, not invented.

How 8.3 Should Behave

8.3 should read 90-result.env and present the install decision in customer-readable form:

• detected hardware
• selected model/family/variant
• install mode
• whether the choice is recommended, fallback, unavailable, or source-exception retained
• what the customer should do next

8.3 should not recalculate sizing independently. It displays the result from 8.2.

Mac And Windows Import Path

Mac and Windows are separate implementation steps, but they should write the same artifact contract.

Mac/Windows importers should create:

```bash
00-instance.env
10-platform.env
20-hardware.env
40-selection.env
```

They do not need to mimic Linux internals. They only need to provide the normalized variables that 8.2 expects.

Examples:

• Mac can record Apple Silicon/Intel, unified memory, disk free, Ollama install path, and Homebrew/Xcode status.
• Windows can record native Windows vs WSL, CPU/RAM/disk, GPU/VRAM if known, and Ollama install discovery.

Do not blend Mac/Windows sizing into this first Linux profile step. Make the contract portable now; fill platform-specific sizing later.

Security Rules

Profile artifacts must not contain:

• license keys
• install tokens
• Passport JWTs
• Stripe secrets
• S3 presigned URLs
• customer credentials
• database passwords

Profile files are operational facts, not secrets. Use 0644 for non-sensitive facts or 0640 if local policy requires tighter permissions.

Acceptance Criteria

This step is complete when:

1. The repo contains profiles/.
2. 0.sh or the bootstrap plan creates /opt/philosopher/profiles.
3. /opt/philosopher/instance.env still works for legacy scripts.
4. 8.2 can resolve and load a designated profile directory.
5. 8.2 writes measured hardware facts to 20-hardware.env.
6. 8.2 does not hard-code only the old qwen3 ladder as the real sizing system.
7. 8.3 reads 90-result.env instead of recalculating the install result.
8. Mac and Windows can later import into the same artifact names without changing the Linux contract.

Cursor Implementation Prompt

Use this as the implementation prompt:

```text
Work in the 8-BALL installer/script repository.

Create the profile artifact layer for the intelligent 8.2 installer.

Do not invent model/instance sizing rules. Do not generate all-family sizing yet. Do not start Mac or Windows sizing yet. This step only creates the environment artifact contract and loader behavior.

Required changes:

1. Add a repo-side profiles/ directory with a README and example environment profile.

2. Update 0.sh so it creates:
   - /opt/philosopher/profiles
   - /opt/philosopher/profiles/00-instance.env
   - /opt/philosopher/instance.env remains supported

   Both files must include EIGHTBALL_PROFILE_DIR="/opt/philosopher/profiles".

3. Update 8.2.sh so it resolves the profile directory by precedence:
   - --profile-dir argument if implemented
   - EIGHTBALL_PROFILE_DIR
   - NCGPT_PROFILE_DIR
   - PROFILE_DIR or EIGHTBALL_PROFILE_DIR loaded from /opt/philosopher/instance.env
   - /opt/philosopher/profiles

4. Update 8.2.sh so it loads these files in order when present:
   - /opt/philosopher/instance.env
   - 00-instance.env
   - 10-platform.env
   - 20-hardware.env
   - 30-catalog.env
   - 40-selection.env

5. Update 8.2.sh so measured hardware facts are written to:
   - ${EIGHTBALL_PROFILE_DIR}/20-hardware.env

6. Update 8.2.sh so its final selection/output is written to:
   - ${EIGHTBALL_PROFILE_DIR}/90-result.env

7. Keep old /opt/philosopher/8ball-result.txt output for compatibility if current 8.3 still reads it, but make 90-result.env the new source of truth.

8. Update 8.3.sh so it prefers:
   - ${EIGHTBALL_PROFILE_DIR}/90-result.env
   then falls back to:
   - /opt/philosopher/8ball-result.txt

9. Remove any stray non-ASCII corruption characters in installer scripts, especially appended characters after variable assignments.

10. Add tests or shell validation proving:
    - legacy instance.env still works
    - explicit profile directory works
    - missing optional artifacts do not crash 8.2
    - hardware facts are written to 20-hardware.env
    - 8.3 reads 90-result.env when available
    - no secrets are written into profile artifacts

Run:
   - bash -n on every edited shell script
   - shellcheck if available
   - repository test command if one exists
   - git diff --check

Report:
   - exact files changed
   - profile resolution behavior
   - generated artifact names
   - validation results
