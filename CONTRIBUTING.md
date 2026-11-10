# Contributing to 8-BALL

The public catalog in this repository is the single source of truth for
Terminal.Glass model metadata. The current canonical version is **2026.08.01**
in `data/normalized/`. Do not create a second hand-maintained catalog in HTML,
and do not import an older private snapshot over this tree.

This repository stores metadata only. Do not add model weights, GGUF files,
Ollama blobs or layers, credentials, customer records, or paid installer
packaging.

The basic Independent AI workflow — detect hardware, browse, check
suitability, install a local model, use it, and remove it — stays free. A
paid product must not become a requirement for that path.

**License:** this repository has no chosen license. See `LICENSE`. Do not
treat a contribution as a license grant. Jonathan must choose the license.

## How the parts fit

| Part | Where it lives | What a contributor edits |
| --- | --- | --- |
| Catalog | `data/normalized/` | Normalized records, with evidence |
| Schemas | `schemas/` | Shape of those records |
| Hardware estimates | `src/eight_ball/estimate/`, `config/hardware_profiles.yaml` | Labeled estimates only |
| Free trial install | `install/` `trial-install.sh` → `8.1.sh` → `8.2.sh` → `8.3.sh` | Keep this numbering |
| Component inventory | `config/components.yaml` | Maintained status, license, placement |
| Generated display | `docs/component-inventory.md` | Do not edit by hand |
| Unresolved fields | `reports/unresolved-fields-summary.json` | Regenerated, not hand-filled |
| Change history | `data/history/catalog-changes.json` | Preserved removals and promotions |

`config/components.yaml` is the maintained component record. The markdown
inventory is generated from it. Model pages under `data/generated/pages/` are
generated from validated catalog records.

Published download sizes use decimal SI units: 1 KB = 1000 bytes,
1 MB = 1,000,000 bytes, 1 GB = 1,000,000,000 bytes. Download size is disk
size. It is not RAM and it is not VRAM.

## Add or correct a model

1. Identify the exact Ollama tag spelling. Official Ollama library pages and
   official metadata responses are authoritative. `nocloudgpt.com/models` and
   `terminal.glass/models` are curated discovery sources only.
2. Put unknown facts in as `null`. Do not guess tags, sizes, commands,
   capabilities, aliases, or licenses. An unresolved field is reported; it is
   not a failure by itself.
3. Keep parameter count, published download size, normalized bytes,
   architecture, quantization, context length, and local / cloud / cloud-only
   availability as separate fields.
4. Cite the evidence URL and the verification time on the record. Mark two
   tags as aliases only when official metadata supports that.
5. Preserve removed or renamed upstream tags in change history. Do not
   silently delete canonical records.
6. If you change parser behavior, update the offline fixture under
   `tests/fixtures/` and the fixture manifest under
   `tests/fixtures/manifests/`. Do not commit `data/raw/`, `data/snapshots/`,
   or live `data/manifests/`.
7. Validate, then open a pull request with the template.

Capability labels must say whether the value is a source claim or a measured
test. Record them in `data/normalized/capability-evidence.json`. A model name
or a parameter count does not make a model agent-ready. Leave the registry
empty until a real source or a measured test exists. The current registry has
no measured tests.

Do not copy private repository content into this public tree. Only sanitized
public metadata belongs here.

## Validate

```bash
python -m pip install -e ".[dev]"
bash scripts/validate-catalog.sh
pytest
```

`bash scripts/validate-catalog.sh` rejects records that break the schema,
identifier rules, decimal size policy, component inventory, or generated
display. Invalid contributions fail this check in CI.

Useful focused commands:

```bash
python3 -m eight_ball.cli validate
python3 -m eight_ball.cli validate-contributions
python3 -m eight_ball.cli unresolved-report
```

## Open a pull request

Use the pull request template. Include:

- the exact tag or field you changed;
- the evidence URL;
- the validation command you ran;
- a note when a platform was not executed.

Do not commit secrets. Do not publish a release from a contribution PR.
