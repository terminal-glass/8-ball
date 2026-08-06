Work in terminal-glass/8-ball, on PR 31 branch:

cursor/c10-model-pages-install-matrix-5fd5

This is C10 Layer 4 RAM work—not C11.

First save this complete prompt as:

AGENTS/history/cursorFile.C10.1-4-ram.md

The prompt is being transferred from:

https://github.com/funtech64/gpt2cursor/tree/codex/c10-layer4-ram-2026-08-06/handoffs/c10-layer4-ram

Objective

Complete the existing C10 RAM layer using the repository’s established layout.

Generate and validate:

profiles/<model-slug>/<lane>/4-ram.json

for every existing model and required lane.

Preserve the existing C10 structure, schemas, lane names, model slugs, provenance rules, and generator workflow. Do not create C11 files or a new data hierarchy.

Use only source-backed data under AGENTS/. Never invent RAM requirements, usable memory, provider capacity, or compatibility. Unknown values remain null; unknown RAM must never produce fits: true.

AWS Lightsail GPU RAM may use verified provider-published system RAM only. GPU identity, VRAM, CUDA, and Ollama support remain unknown unless runtime-verified.

Update only the generator, focused validators/tests, and normal generated C10 output.

Run:

python3 scripts/generate-c10-profiles.py
python3 scripts/validate-c10-profiles.py
python3 -m pytest tests/test_profile_platform_tree.py tests/test_c10_profiles.py -q
git diff --check

Confirm deterministic regeneration, complete 4-ram.json coverage, conservative unknown handling, no secrets, and no unrelated changes.

Report changed files, test results, generated counts, known gaps, and the resulting commit SHA. Do not claim PR 31 is merged.
