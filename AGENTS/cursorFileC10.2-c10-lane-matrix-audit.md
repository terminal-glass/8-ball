C10.2 — Lane-matrix audit and profile/install contract repair

Work in the real terminal-glass/8-ball repository on the current PR33 branch.

This replaces the invalid C10.2 provider-assumptions prompt. Do not create,
restore, require, or validate data/generated/provider-assumptions/. That was
not part of the C7/C10 contract. Do not let an invented JSON layer decide what
is committed.

First save this complete, unchanged prompt as:

```text
AGENTS/cursorFileC10.2-c10-lane-matrix-audit.md
```

Move the superseded C10.2 provider-assumptions handoff to AGENTS/history/ so a
later agent cannot mistake it for active model data or instructions. Do not move
or rewrite any other AGENTS history. Read AGENTS.md, the active C10 handoffs,
and the existing C10 generator and validator before changing files.

Purpose

Preserve PR33’s cleanup and establish one auditable contract between root
/install/ and model-first /profiles/. The goal is to make real AGENTS-backed
profile data map to the exact install targets, without inventing RAM, CPU, GPU,
provider, model, or compatibility data.

This is a narrow C10.2 repair. It is not a new data hierarchy, C11 work, or
a rewrite of the installer architecture.

Freeze the lane contract: exactly 10 lanes

profiles/lanes.json is the single machine-readable source of truth for the
following ten canonical lane IDs and paths. Create or correct it only as needed
to represent this exact list; do not introduce aliases or an eleventh lane.

|Lane ID                   |Install path                             |Relative profile path            |Runtime type|
|--------------------------|-----------------------------------------|---------------------------------|------------|
|`ubuntu-cpu`              |`install/ubuntu/cpu/`                    |`ubuntu/cpu/`                    |shell       |
|`ubuntu-cuda`             |`install/ubuntu/cuda/`                   |`ubuntu/cuda/`                   |shell       |
|`mac-apple-silicon`       |`install/mac/apple-silicon/`             |`mac/apple-silicon/`             |shell       |
|`mac-intel`               |`install/mac/intel/`                     |`mac/intel/`                     |shell       |
|`windows-cpu`             |`install/windows/cpu/`                   |`windows/cpu/`                   |PowerShell  |
|`windows-cuda`            |`install/windows/cuda/`                  |`windows/cuda/`                  |PowerShell  |
|`digitalocean-cpu-droplet`|`install/cloud/digitalocean/cpu-droplet/`|`cloud/digitalocean/cpu-droplet/`|shell       |
|`digitalocean-gpu-droplet`|`install/cloud/digitalocean/gpu-droplet/`|`cloud/digitalocean/gpu-droplet/`|shell       |
|`aws-lightsail-cpu`       |`install/cloud/aws-lightsail/cpu/`       |`cloud/aws-lightsail/cpu/`       |shell       |
|`aws-lightsail-gpu`       |`install/cloud/aws-lightsail/gpu/`       |`cloud/aws-lightsail/gpu/`       |shell       |

The model slug is an outer directory only:

```text
profiles/<model-slug>/<relative-profile-path>/
```

It is not an install lane, and a size slug is a JSON file under
profiles/<model-slug>/sizes/, never a directory or lane.

Freeze the 50-file install payload accounting

There are 50 required operational install payload files:

```text
10 canonical lanes × 5 payload roles = 50 physical files
```

The five roles are:

|Role           |Shell lane filename    |Windows lane filename  |
|---------------|-----------------------|-----------------------|
|Trial bootstrap|`trial-install.sh`     |`trial-install.ps1`    |
|Stage 8.1      |`8.1.sh`               |`8.1.ps1`              |
|Stage 8.2      |`8.2.sh`               |`8.2.ps1`              |
|Stage 8.3      |`8.3.sh`               |`8.3.ps1`              |
|MOTD asset     |`assets/first-MOTD.txt`|`assets/first-MOTD.txt`|

README.md is also required in every lane, but it is documentation. Audit it
as 10 separate README files; do not call the result 50 or silently fold it
into the payload count. Root install.sh, if present, is a top-level bootstrap
source and is not a per-lane payload, so it does not change either count.

All 50 payloads must be real, non-empty, tracked files in their own lane. A
cloud lane may begin from an Ubuntu baseline, but it must be a physical copy in
its own directory. Mac files must be Mac-safe shell files; Windows files must be
PowerShell. A pending platform may exit with an honest explanatory message, but
may not be represented by an empty file, README-only lane, symlink, or a script
for the wrong runtime.

Profile mapping rules

Every generated model folder must mirror all ten relative profile paths and
map each one back to the matching install_path from profiles/lanes.json.
The existing C10 generator/validator schema is authoritative for the exact
profile step filenames (for example the existing C10 4-ram.json layer). Do
not rename stage files merely to reconcile older C7 wording. Instead, make the
generator, lane.json, profile indexes, and validator agree on the five
semantic stages 3 through 7 that the current schema already uses.

For each model/profile lane, require:

```text
lane.json
profile-sizes.csv
five current-schema stage-3-through-7 payload files
```

profile-sizes.csv and profiles/index.csv must reference only existing,
tracked size JSON files. Unknown RAM/CPU/GPU/provider values remain null or
the established conservative unknown status; unknown data must never become a
positive fit claim.

Count the matrix correctly

Write a generated, tracked audit report at:

```text
profiles/_lane-matrix-audit.json
profiles/_lane-matrix-audit.csv
```

The report must include the lane table above and these separately named counts:

```text
required_install_lane_count             # always 10
actual_install_lane_count
required_install_payload_file_count     # always 50
actual_install_payload_file_count
required_install_readme_count           # always 10
actual_install_readme_count
model_slug_count
model_size_count
expected_profile_lane_count             # model_slug_count × 10
actual_profile_lane_count
profile_matrix_row_count                # model_size_count × 10, if C10 index is model-size-lane
profile_stage_payload_file_count        # model_slug_count × 10 × 5, if stages are model-lane payloads
unknown_limit_count
conflict_count
```

Do not call any of these counts “12,000 installs” without showing the exact
formula and the observed inputs. 12,000 is a number to verify, not a number to
manufacture. It could describe model-size-lane index rows or model-lane stage
payload files, which are different objects. If the current source-backed counts
do not produce 12,000 for the claimed category, report the discrepancy, its
formula, and the exact source input count; do not pad the matrix or fabricate
models, sizes, lanes, or hardware limits to reach it.

Required implementation and validation

Extend the existing C10 generator and validator; do not create a parallel
generator, a second lane list, or a hand-maintained set of profile mappings.
The validator must fail when any of these are true:

	1.	The canonical lane list is not exactly the ten rows above.
	2.	Any install lane is missing a required README or one of its five correct
runtime-specific payload files.

	3.	The physical tracked install payload count is not exactly 50, or the tracked
lane README count is not exactly 10.

	4.	A generated model tree is missing a canonical profile lane, lane.json,
profile-sizes.csv, a required stage 3–7 payload, or its matching
install_path mapping.

	5.	An index or CSV points to a missing, ignored, or untracked size/profile file.
	6.	A model-size-lane index row is absent, duplicated, or refers to a lane outside
the canonical ten.

	7.	A RAM/CPU/GPU/provider or fit value is fabricated or becomes positive from
unknown input.

Run the repository’s existing C10 generation and validation commands, then run
the focused profile tests and git diff --check. Add a focused regression test
or validator fixture for the 10/50 contract and count it from the canonical lane
manifest rather than a duplicated hard-coded path list.

Before committing, stage the generated output and prove it is not ignored:

```bash
git add -A
git check-ignore -q -- install/ubuntu/cpu/trial-install.sh && exit 1 || true
test "$(git ls-files --cached 'install/**/trial-install.*' | wc -l)" -eq 10
test "$(git ls-files --cached 'install/**/8.1.*' | wc -l)" -eq 10
test "$(git ls-files --cached 'install/**/8.2.*' | wc -l)" -eq 10
test "$(git ls-files --cached 'install/**/8.3.*' | wc -l)" -eq 10
test "$(git ls-files --cached 'install/**/assets/first-MOTD.txt' | wc -l)" -eq 10
```

If Git pathspec semantics make a command unreliable on the installed Git
version, use a small portable validation routine instead. It must still prove
the same five-by-ten result and reject ignored files.

Commit only this C10.2 repair after all checks pass. Preserve the existing PR33
cleanup; do not reset, recreate, or expand it with unrelated changes.

Final response required from Cursor

Report:

	1.	The current branch and commit SHA.
	2.	The exact ten lane IDs and their install/profile paths.
	3.	The five payload roles, 50 tracked payload count, and 10 README count.
	4.	Model slug count, model-size count, profile lane count, profile-matrix row
count, profile-stage payload count, and the formula for each.

	5.	Whether 12,000 was observed; if not, the precise discrepancy and why.
	6.	Unknown-limit/conflict counts and any source-backed gaps.
	7.	Validation/test commands and pass/fail results.
	8.	Exact changed files and the resulting commit SHA.

Do not claim the PR is merged.

Please document all of this above prompt in AGENTS, for it to move to history on the next cursorFileC#.md
