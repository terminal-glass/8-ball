# Repository layout and cleanup

## Start with the data you need

| Need | Location |
| --- | --- |
| Browse hardware assumptions, observations, provider plans, and lanes | [Hardware guide](../hardware/README.md) |
| Search model sizes and target lanes | [Profile matrix](../profiles/index.csv) |
| Understand runtime-facing profiles | [Profile contract](../profiles/README.md) |
| Read normalized model and hardware records | [Canonical records](../data/normalized/) |
| Inspect original hardware inputs | [Hardware source collection](../AGENTS/data-science/profile-mapping/) |
| Run the public trial or inspect platform lanes | [Installer guide](../install/README.md) |
| Find engineering instructions and historical decisions | [AGENTS](../AGENTS/) and [history](../AGENTS/history/README.md) |

The hardware guide is generated from existing records. Source files stay in place
so consumers and provenance links retain their paths. Unknowns, assumptions, and
hardware observations remain distinct from tested model performance.

## Removed material

The November 2026 cleanup removes the unused `v3/asdf.txt` and empty
`AGENTS/data-science/ollama-mapping/asdf.txt` placeholders, the orphaned root JPEG,
and the obsolete `profiles/legacy/c10-lane-skeletons/` tree (14,047 files).
The root README's missing-image reference is removed with the unused image.

The skeleton tree's documented removal condition was validation of the canonical
per-model lanes. `scripts/validate-profiles-from-agents.py` passes against the
canonical matrix, and no active reader consumes the old skeleton tree. The old
files remain recoverable through Git history; this cleanup does not rewrite history.

## Retained compatibility data

Keep `profiles/legacy/c5-root-export/` and `profiles/legacy/c10-model-pages/`.
Compatibility readers and tests still use those paths. They are not the source
for new integrations; see the [legacy migration notes](../profiles/legacy/README.md).
Normalized records, source observations, generated active model/profile matrices,
and installer entry points are preserved.

Existing console, model-manager, and OSAMP draft PRs remain separate work. This
cleanup changes navigation and removes retired exports; it does not merge those
branches or claim that their runtime integrations are ready.

## Updating the readable hardware view

After changing the canonical source data, run:

```bash
python3 scripts/generate-hardware-guide.py
python3 scripts/generate-hardware-guide.py --check
```

For catalog and installer-lane checks, follow [AGENTS.md](../AGENTS.md).
