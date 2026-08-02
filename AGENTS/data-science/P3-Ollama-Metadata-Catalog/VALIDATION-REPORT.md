# P3 Ollama Metadata Catalog — Validation Report (FAILED)

**Status:** Export blocked — source repository not accessible  
**Report generated (UTC):** 2026-07-16T06:55:00Z  
**Destination repository:** `funtech64/ycgpt-lightsail` (workspace; referenced as `ycgpt-install` in task brief)  
**Source repository (expected):** `funtech64/ycgpt-8.sh`

---

## Executive summary

Validation and export of the Ollama metadata catalog **did not proceed**. The authoritative source repository `funtech64/ycgpt-8.sh` could not be located or cloned from this environment. Per task instructions, the catalog snapshot was **not copied** into `P3-Ollama-Metadata-Catalog/`, and `P1-Estimator/` and `P2-Provider-Datasets/` were left unchanged.

---

## Source repository access attempts

| Method | URL / command | Result |
|--------|---------------|--------|
| `git clone` | `https://github.com/funtech64/ycgpt-8.sh.git` | `remote: Repository not found` (exit 128) |
| `gh repo view` | `funtech64/ycgpt-8.sh` | `Could not resolve to a Repository` |
| GitHub REST API | `GET /repos/funtech64/ycgpt-8.sh` | HTTP 404 `Not Found` |
| Web fetch | `https://github.com/funtech64/ycgpt-8.sh` | HTTP 404 |
| Alternate names tried | `ycgpt-8-sh`, `ycgpt-8`, `ycgpt8`, `8.sh`, `ycgpt-metadata`, `ycgpt-ollama`, `nocloudgpt-8.sh`, `ycgpt-install` | All 404 / not found |
| GitHub search | `user:funtech64 ycgpt` | Only `ycgpt-lightsail` and `support.ycgpt.org-html` returned |

The destination workspace remote is `funtech64/ycgpt-lightsail` (private). No separate `funtech64/ycgpt-install` repository exists on GitHub from this token's perspective.

---

## Source validation steps (not performed)

Because the source tree was unavailable, the following required steps **could not be executed**:

1. Record current `main`-branch commit SHA from `ycgpt-8.sh`
2. Record catalog version
3. Inspect `README.md`, `AGENTS.md`, configuration, schemas, reports, tests, catalog files, family files, and indexes
4. Run:
   - `bash scripts/validate-catalog.sh`
   - `python3 -m pytest -q`
   - `bash scripts/build-indexes.sh`
5. Confirm index rebuild produces no unexplained changes
6. Parse every JSON file intended for export
7. Confirm catalog integrity rules (pull/run commands, sizes, local/cloud classification, alias resolution, absence of installer scripts and model payloads)

---

## Accuracy review (not performed)

The representative sample review against official Ollama pages was **not performed** because no catalog records were available. The following sample categories were planned but not executed:

- 10 highly downloaded families
- 10 randomly selected families
- One dense family, MoE family, embedding family, vision family, coding family, thinking family
- One cloud-only family and one family with local + cloud variants
- Several aliases
- Largest and smallest verified local variants

---

## Destination state

| Path | Status |
|------|--------|
| `P3-Ollama-Metadata-Catalog/` | Contains this failure report only (`.gitkeep` removed) |
| `P3-Ollama-Metadata-Catalog/data/` | **Not created** |
| `P3-Ollama-Metadata-Catalog/schemas/` | **Not created** |
| `P3-Ollama-Metadata-Catalog/indexes/` | **Not created** |
| `P3-Ollama-Metadata-Catalog/reports/` | **Not created** |
| `P3-Ollama-Metadata-Catalog/PROVENANCE.json` | **Not created** |
| `P3-Ollama-Metadata-Catalog/README.md` | **Not created** |
| `P1-Estimator/` | Unchanged |
| `P2-Provider-Datasets/` | Unchanged |

---

## Skipped source files

All source files were skipped because the source repository does not exist or is not accessible to this agent's GitHub credentials.

---

## Required action to unblock

1. Create or publish the `funtech64/ycgpt-8.sh` repository with the metadata catalog, validation scripts, and tests described in the P3 task brief.
2. Grant this environment read access to `funtech64/ycgpt-8.sh`.
3. Re-run P3 validation and export with a recorded source commit SHA.

Until the source repository is available and validation succeeds, **no metadata snapshot should be imported** into the destination.
