# Repository Constitution: Ollama Metadata Catalog

## Purpose

This repository is the authoritative Ollama model metadata catalog used to support separate future installer-authoring work.

It stores metadata only. It must never download, cache, mirror, package, distribute, or otherwise retain Ollama model payloads.

The catalog exists to preserve verifiable metadata about Ollama model families, variants, commands, sizes, capabilities, availability, provenance, indexes, reports, and version history. It does not create customer installers and does not participate in fulfillment.

## Architectural Boundaries

The repository is organized around metadata collection, normalization, validation, indexing, reporting, and offline tests.

Expected responsibilities include:

- source configuration in `config/`;
- JSON schemas in `schemas/`;
- catalog records and compact source snapshots in `data/`;
- family records under `data/families/`;
- generated metadata indexes under `indexes/`;
- validation and generation reports under `data/reports/`;
- source code for crawling, normalization, validation, indexing, and reporting under `src/`;
- maintenance scripts under `scripts/`;
- offline tests and sanitized fixtures under `tests/`;
- scheduled or manually triggered catalog refresh automation under `.github/workflows/`.

The repository must avoid directories or files that imply model-payload storage or installer generation unless they are explicitly documented as small metadata fixtures. Avoid names such as `generated/`, `installers/`, `artifacts/`, `payloads/`, `models/`, `weights/`, `blobs/`, and executable installer names such as `8.sh`.

## Metadata Philosophy

Catalog data must represent verifiable metadata, not inferred model content.

For every verified Ollama tag, the catalog should preserve:

- family slug and display name;
- exact Ollama tag spelling;
- exact `ollama pull <tag>` command;
- exact `ollama run <tag>` command;
- published download size text;
- normalized download size in bytes;
- parameter labels and safely normalized parameter counts;
- architecture information, including mixture-of-experts details when available;
- input and model capabilities;
- local, cloud-capable, and cloud-only availability;
- aliases and duplicate manifests only when verifiable;
- source URLs;
- verification timestamps;
- unresolved fields when values cannot be verified.

Do not invent missing values. When official metadata cannot verify a field, store `null`, record the field as unresolved, and preserve the source or attempted source URL.

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

Do not infer download size from parameter count. Do not flatten mixture-of-experts models into misleading dense parameter counts. Preserve exact suffixes such as `instruct`, `thinking`, `vision`, `cloud`, quantization suffixes, context suffixes, version suffixes, and architecture suffixes.

Only mark two tags as aliases when official metadata supports that conclusion.

## Authoritative Data Sources

Use source priority in this order:

1. Official Ollama model and tag pages.
2. Official Ollama metadata responses when available.
3. `https://nocloudgpt.com/models` as a curated discovery source.
4. `https://terminal.glass/models` as a curated discovery source.

Official Ollama sources are authoritative for exact family slugs, tags, commands, published download sizes, parameter labels, descriptions, capabilities, local availability, cloud availability, tag-specific metadata, and source URLs.

Curated sites may help discover model families, links, categories, and coverage gaps. They are not authoritative for exact Ollama tags, published download sizes, capabilities, or classifications unless they directly reference official Ollama data.

If a curated source is unavailable, record the failure and continue processing. Do not fail the entire catalog solely because a non-required curated source is unavailable.

## Catalog Responsibilities

The catalog should maintain:

- normalized family records;
- aggregate catalog JSON, JSONL, and CSV outputs;
- family-level and variant-level provenance;
- source-attempt and unresolved-field reports;
- change reports that preserve historical visibility;
- indexes by download size, parameter size, capability, family, local availability, cloud availability, and aliases;
- catalog version history independent of installer versions;
- offline fixtures sufficient to test parsing and validation behavior without live internet access.

Indexes are metadata indexes only. They may later support separate installer-authoring agents, but this repository must not generate installer scripts or fulfillment artifacts.

## Source Snapshot Policy

Small source snapshots are allowed only when needed for repeatable parsing or offline tests.

Allowed snapshot content includes:

- sanitized HTML;
- small JSON metadata responses;
- extracted structured metadata;
- compact test fixtures.

Prohibited snapshot content includes:

- model binaries;
- blobs;
- layers;
- GGUF files;
- archives containing model payloads;
- Docker images;
- Ollama model storage directories;
- anything downloaded through `ollama pull`.

Respect the configured snapshot-size limit. Reject, truncate, or omit unexpectedly large responses according to policy, and record the action in reports.

## Validation Philosophy

Validation must protect metadata quality, repository boundaries, and future consumers.

Validation should confirm, at minimum, that:

- family slugs are unique;
- exact tags are unique within each family;
- pull commands match exact tags;
- run commands match exact tags;
- download bytes are integers or `null`;
- download text and normalized bytes follow the repository's documented conversion policy;
- source URLs exist for verified records;
- cloud-only models do not appear in local-only indexes;
- aliases reference valid targets;
- indexes are consistent with catalog records;
- no binary payloads are present;
- no file exceeds the source-snapshot size policy without a documented exception;
- no installer scripts were generated;
- no deployment repositories were modified;
- no credentials, cookies, tokens, or session data are present.

Validation and tests should be runnable offline when validating the existing catalog. Tests must not invoke Ollama, access live internet, download payloads, or generate installers.

Before considering work complete, run the relevant validation commands. At minimum, run:

```bash
bash scripts/validate-catalog.sh
```

## Prohibited Actions

Agents and automation must not:

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
- generate fallback shell arrays for installers;
- modify deployment repositories;
- modify Passport;
- upload artifacts to S3;
- create customer fulfillment logic;
- store credentials, cookies, tokens, or session data;
- invent tags, sizes, commands, capabilities, aliases, or classifications.

This repository is metadata-only.

## Separation From Installers

Catalog versions are independent from installer versions. The catalog may provide metadata that future separate agents use while designing or versioning customer-specific installer scripts, but this repository must not generate those scripts.

Do not create `8.sh`, installer shell scripts, fallback installer arrays, deployment scripts, publishing workflows, customer-specific scripts, or fulfillment artifacts.

Installer versions may later change independently because of changes in Ollama behavior, OpenWebUI behavior, NoCloudGPT behavior, cloud-provider behavior, disk fallback logic, customer fulfillment requirements, or other deployment concerns.

Do not combine catalog versioning with installer versioning.

## Separation From Passport and Fulfillment

This repository must not modify Passport, call Passport services, store Passport credentials, or create customer fulfillment logic.

The catalog may preserve public metadata and source provenance needed for later installer-authoring work, but Passport integration and customer fulfillment belong outside this repository.

## Versioning Philosophy

Use catalog versions independent of any installer or deployment version.

Catalog version format:

```text
YYYY.MM.DD
```

For multiple catalog refreshes on one day, append an incrementing suffix:

```text
YYYY.MM.DD.1
YYYY.MM.DD.2
```

Catalog version changes should reflect metadata refreshes and catalog maintenance. They must not imply an `8.sh` version.

## Quality Standards

Keep changes narrow and intentional.

Before editing:

1. read the root `AGENTS.md` completely;
2. read this constitution completely;
3. inspect `git status`;
4. inspect the relevant files;
5. inspect existing tests, schemas, reports, and source configuration when the task could affect them;
6. summarize intended changes;
7. identify any conflict with repository scope or this constitution;
8. ask before making a change that expands scope.

Do not silently delete existing catalog records. When upstream metadata disappears or changes, report it in the change report and preserve historical visibility for removed or changed model entries.

Avoid unrelated formatting changes and mass rewrites unless explicitly requested.

Documentation should reinforce that this repository stores model metadata only and does not download, cache, mirror, package, or distribute Ollama model payloads.
