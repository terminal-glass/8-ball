# Superseded C10.2 provider-assumptions handoff

This file records the **invalid** C10.2 provider-assumptions approach that was
briefly mandated by `AGENTS/cursorFile.C10.1-1-profiles-directory-cleanup.md`
(move provider assumptions to `data/generated/provider-assumptions/`).

That layer was **not** part of the C7/C10 contract and is superseded by
`AGENTS/cursorFileC10.2-c10-lane-matrix-audit.md`, which establishes:

- `profiles/lanes.json` as the single lane manifest
- direct mapping from `/profiles/<model>/<lane>/` to `/install/<lane>/`
- no `data/generated/provider-assumptions/` JSON layer

Do not restore or validate `data/generated/provider-assumptions/` for C10 work.
