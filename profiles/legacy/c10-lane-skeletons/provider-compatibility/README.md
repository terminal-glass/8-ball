

## macOS runtime hosts (C10.1-12)

- `macos/host-capability-categories.json` and `.csv` — runtime host categories
- `macos/runtime-observation-contract.json` — macOS evidence contract
- `macos/lane-runtime-contract-projection.json` — `mac/apple-silicon` and `mac/intel` projections

Source tables:
- `AGENTS/data-science/profile-mapping/macos/runtime-capability-taxonomy.json`
- `AGENTS/data-science/profile-mapping/macos/runtime-observation-contract.md`
- `scripts/macos-observe-host.sh`

Regenerate with `python3 scripts/generate-c10-profiles.py`.
