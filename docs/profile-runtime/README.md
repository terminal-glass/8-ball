# Runtime profile environment contract

This directory documents the **installed runtime** profile artifact contract used by
separate installer work (`0.sh`, `8.2.sh`, `8.3.sh`). Live installers write artifacts
under `/opt/philosopher/profiles`.

This is distinct from the repository's C10 model-selection tree at `profiles/`, which
contains metadata-only model pages and lane stage files for installer selection.

## Example file

- `environment.profile.example.env` — documented variable contract for runtime profile
  directories (`00-instance.env`, `10-platform.env`, etc.)

See `profiles/README.md` for the repository C10 profile namespace.
