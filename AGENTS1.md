## Repository Purpose

This repository is the authoritative Ollama model metadata catalog used to support future installer-authoring work.

It stores metadata only.

It must not download, cache, mirror, package, or distribute Ollama model payloads.

The full project requirements are defined in:

`AGENTS/cursorFileA0.md`

All agents must read that file before making changes.

---

## Shared Rules for Cursor, Codex, and Other Agents

### Before editing

1. Read this file completely.
2. Read `AGENTS/cursorFileA0.md` completely.
3. Inspect the current repository structure.
4. Inspect existing tests, schemas, reports, and source configuration.
5. Summarize the intended changes before editing.
6. Identify any conflict between the request and the specification.
7. Ask before making a change that expands scope.

Do not begin implementation from only a partial reading of the specification.

---

## Repository Scope

Allowed work includes:

- collecting Ollama model metadata;
- recording exact Ollama model tags;
- recording exact `ollama pull` commands;
- recording exact `ollama run` commands;
- recording published model download sizes;
- normalizing download sizes into bytes;
- recording parameter labels and architecture information;
- recording capabilities;
- distinguishing local, cloud-capable, and cloud-only models;
- preserving source provenance;
- building metadata indexes;
- generating validation reports;
- building offline tests;
- maintaining catalog version history.

---

## Prohibited Actions

Agents must not:

- run `ollama pull`;
- run `ollama run`;
- install Ollama;
- download model weights;
- download GGUF files;
- download Ollama layers or blobs;
- cache model payloads;
- mirror model binaries;
- package model weights;
- store Ollama model directories;
- generate `8.sh`;
- generate installer scripts;
- modify deployment repositories;
- modify Passport;
- upload artifacts to S3;
- create customer fulfillment logic;
- store credentials, cookies, tokens, or session data;
- invent tags, sizes, commands, capabilities, or classifications.

This repository is metadata-only.

---

## Authoritative Sources

Use source priority in this order:

1. Official Ollama model and tag pages.
2. Official Ollama metadata responses when available.
3. `https://nocloudgpt.com/models` as a curated discovery source.
4. `https://terminal.glass/models` as a curated discovery source.

The curated sites may help discover models, but they are not authoritative for exact Ollama tags or published download sizes.

When official metadata cannot be verified:

- store `null`;
- record the unresolved field;
- preserve the source URL;
- do not estimate or guess.

---

## Data Quality Rules

Keep these concepts separate:

- parameter count;
- published download size;
- normalized download bytes;
- architecture type;
- quantization;
- context length;
- local availability;
- cloud availability;
- cloud-only status.

Do not infer download size from parameter count.

Do not flatten mixture-of-experts models into misleading dense parameter counts.

Preserve exact Ollama tag spelling.

Preserve suffixes such as:

- `instruct`;
- `thinking`;
- `vision`;
- `cloud`;
- quantization suffixes;
- context suffixes;
- version suffixes;
- architecture suffixes.

Only mark two tags as aliases when official metadata supports that conclusion.

---

## Source Snapshot Rules

Small metadata snapshots are allowed only when needed for repeatable parsing or offline tests.

Allowed:

- sanitized HTML;
- small JSON metadata responses;
- extracted structured metadata;
- compact test fixtures.

Not allowed:

- model binaries;
- blobs;
- layers;
- GGUF files;
- archives containing model payloads;
- Docker images;
- Ollama model storage directories.

Respect the configured snapshot-size limit.

Do not commit unexpectedly large source responses.

---

## Versioning

Catalog versions are independent from future installer versions.

Use catalog versions in this format:

`YYYY.MM.DD`

For multiple refreshes on one day:

`YYYY.MM.DD.1`

`YYYY.MM.DD.2`

Do not use catalog versions as `8.sh` versions.

Installer versions may later change independently because of:

- Ollama behavior;
- OpenWebUI behavior;
- NoCloudGPT behavior;
- cloud-provider behavior;
- fulfillment requirements;
- fallback logic.

---

## Change Safety

Keep changes narrow and intentional.

Before editing:

- inspect `git status`;
- inspect the relevant files;
- avoid unrelated formatting changes;
- avoid mass rewrites unless explicitly requested.

Do not silently delete existing catalog records.

When upstream metadata disappears or changes, report it in the change report.

Preserve historical visibility for removed or changed model entries.

---

## Validation

Before calling work complete, run the relevant validation commands.

At minimum:

```bash
bash scripts/validate-catalog.sh
```
