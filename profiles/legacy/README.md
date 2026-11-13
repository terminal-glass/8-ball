# Legacy profile exports (non-runtime compatibility)

These artifacts are retained for migration reference only.
The canonical runtime-facing profile matrix lives at the repository root under `profiles/`.

| Path | Origin | Removal condition |
| --- | --- | --- |
| `c5-root-export/` | C5 `eight-ball generate-root-profiles` | No consumers of C5 entity index remain |
| `c10-model-pages/` | C10 flat `profiles/<slug>.json` pages | 8.x resolver reads canonical model folders only |
| `c10-lane-skeletons/` (optional) | Empty or pre-C10.3 lane trees | Removed after canonical per-model lane validation; recover older copies through Git history |
| `c10-index.json` | C10 model×lane index | Superseded by `profiles/index.csv` matrix |
