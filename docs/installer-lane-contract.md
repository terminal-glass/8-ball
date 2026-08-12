# Installer lane conformance contract (C10.2-4)

This document defines the public installer surface for the ten canonical 8-BALL
runtime lanes. The machine-readable gate is `scripts/validate-install-lanes.py`.

## Lane matrix

| Family | Lane |
| --- | --- |
| Ubuntu | `ubuntu/cpu`, `ubuntu/cuda` |
| macOS | `mac/apple-silicon`, `mac/intel` |
| Windows | `windows/cpu`, `windows/cuda` |
| DigitalOcean | `cloud/digitalocean/cpu-droplet`, `cloud/digitalocean/gpu-droplet` |
| AWS Lightsail | `cloud/aws-lightsail/cpu`, `cloud/aws-lightsail/gpu` |

Each lane directory under `install/<lane>/` must contain:

- `README.md`
- `assets/first-MOTD.txt`
- `trial-install` + `8.1` + `8.2` + `8.3` in the lane’s native script format

Native formats:

- Ubuntu, macOS, and cloud lanes: tracked `.sh` entrypoints
- Windows lanes: tracked `.ps1` entrypoints

## Platform boundaries

### macOS

- User-level install only; no `sudo`, `apt`, `systemctl`, `/proc`, `nproc`, or `ollama serve`
- No NVIDIA/CUDA driver installation or dedicated VRAM claims
- No `/opt/philosopher`, `/usr/local/bin`, or remote `ollama.com/install.sh` pipelines
- WSL is out of scope; use Ubuntu lanes instead

### Windows

- User-level install only; no Linux service manipulation or remote shell install pipelines
- No `ollama serve`; the Ollama Windows app owns lifecycle
- `windows/cpu` must not require CUDA/`nvidia-smi`; CUDA evidence belongs in `windows/cuda`
- `nvidia-smi` is required evidence for the CUDA lane only

### Ubuntu and cloud (Linux shell)

Linux shell behavior such as `apt-get`, `systemctl`, and `ollama serve` may still
exist in legacy payloads. Those lanes are not rewritten by the conformance gate.
Instead, known remote-fetch debt is recorded explicitly (see below).

## Help surfaces

- `trial-install` and `8.2` must expose discoverable `--help`/`-Help` handling
- `8.1` and `8.3` are orchestrated sub-steps invoked by `trial-install`; they do
  not require standalone help flags

## Legacy debt (temporary)

Some Ubuntu/cloud payloads still download helper scripts or pipe
`ollama.com/install.sh` at runtime. These are **not** ignored. They are listed as
`legacy_debt` in `reports/installer-lane-conformance.json` with:

- exact lane and file path
- waived rule id
- follow-up id `C10.2-Linux-lanes`
- removal condition when the payload is modernized

Mac and Windows lanes may not use `legacy_debt`.

## Running the gate

```bash
python3 scripts/validate-install-lanes.py
python3 scripts/validate-install-lanes.py --json-out reports/installer-lane-conformance.json
```

Exit status:

- `0` — no unresolved conformance violations
- `1` — one or more violations remain

PowerShell syntax parsing uses the PowerShell parser when `pwsh` or `powershell`
is available. When it is not available, the report records `syntax: not_run` for
`.ps1` files without treating that as a successful parse.

The gate is also invoked from `scripts/validate-catalog.sh`.
