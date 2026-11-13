# 8-BALL

**Independent AI that fits the computer you already have.**

8-BALL is the non-agentic starting point: public Ollama model metadata, hardware
profiles, a free trial installer, and a proposed AI consultation. It assesses and
recommends; the user decides which model, software, and actions to approve. Hardware
estimates are planning guidance; a successful workload test is separate evidence.

## Find what you need

| I want to… | Start here |
| --- | --- |
| See CPU, RAM, GPU, and provider profiles | [Browse hardware](hardware/README.md) |
| Search model sizes across platform lanes | [Profile matrix (CSV)](profiles/index.csv) |
| Understand the generated profile folders | [Profile contract](profiles/README.md) |
| Use the public free/trial installer | [Installer guide](install/README.md) |
| Read normalized model and hardware data | [Canonical data](data/normalized/) |
| Understand which files are active or historical | [Repository layout](docs/repository-layout.md) |
| Contribute or work with an agent | [Repository instructions](AGENTS.md) |

## Hardware and model data

The [hardware guide](hardware/README.md) puts planning profiles, measured hosts,
provider snapshots, and the ten runtime lanes in readable tables with source
links. It is generated from the existing records, so there is no second catalog
to maintain.

The [profile matrix](profiles/index.csv) is the model-size-lane lookup table.
Use [profiles/manifest.json](profiles/manifest.json) for current counts and the
[profile contract](profiles/README.md) for file layout and regeneration.
The catalog page contract remains in
[docs/install-manifest-contract.md](docs/install-manifest-contract.md).

Published download size, estimated runtime memory, actual host capacity, and
measured task performance remain separate. Unknown facts stay unknown. Provider
snapshots do not establish current availability or pricing.

## Try the free Ubuntu installer

Review the [installer guide](install/README.md) and script before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/ubuntu/trial-install.sh -o trial-install.sh
sudo bash trial-install.sh
```

Optional flags include `--model`, `--model-slug`, and `--no-motd`.
See individual [platform lane documentation](install/README.md) for implementation
and test status; a folder's presence is not proof of a successful hardware install.

## Add tools as useful

| Component | Role |
| --- | --- |
| Ollama | Run supported local models |
| Open WebUI | Optional browser-based chat workspace |
| 8-BALL JETS / Ollama Cloud | Optional remote models for workloads better served online |
| OpenClaw / 9-ball | Separate, explicitly chosen agentic assistance |

8-BALL does not autonomously select tools, execute model-directed actions, or enroll
peers. The user makes the choices. Installing or activating a software license does
not grant an agent permission to act.

OpenClaw, unattended agent work, and agent-mail participation belong to a separate
opt-in agentic path through 9-ball or the appropriate COLORS.chat / NoCloudGPT
stack. COLORS.chat retains the choice of non-agentic use. 9-ball focuses on
charitable OpenClaw-and-mail assistance. Proposed integrations are not presented
here as shipped features.

Optional installation assistance: the $99 single-machine pilot is described at
[terminal.glass/8-ball](https://terminal.glass/8-ball).

## Development

This repository stores public metadata and free/trial resources, not model weights.
Paid packaging, license fulfillment, customer records, and production credentials
belong outside this public catalog. Read [AGENTS.md](AGENTS.md) and
[AGENTS/cursorFileA0.md](AGENTS/cursorFileA0.md) before changing code.

```bash
python -m pip install -e ".[dev]"
bash scripts/validate-catalog.sh
python3 scripts/validate-install-lanes.py
pytest
python3 scripts/generate-hardware-guide.py --check
```

See the [data-science workflow](AGENTS/data-science/README.md) for source refreshes,
[hardware import audit](docs/C6-hardware-data-import-audit.md) for provenance,
and [repository layout](docs/repository-layout.md) for cleanup and retained
compatibility paths. Catalog versions and installer versions remain independent.
