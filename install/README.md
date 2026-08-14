# Public 8-BALL trial installers

These are the **public, free/trial** Terminal.Glass 8-BALL installer scripts. Each
profile directory contains a self-contained copy of the same script set so platform-
specific and GPU-optimized flows can diverge later without cross-contamination.

## Profile directories

| Path | Intended target |
| --- | --- |
| `install/ubuntu/` | Ubuntu/Debian Linux (validated trial path) |
| `install/mac/` | macOS (placeholder copy for future profile work) |
| `install/windows/` | Windows / WSL (placeholder copy for future profile work) |
| `install/cloud/aws-lightsail/` | AWS Lightsail instances |
| `install/cloud/digitalocean-droplet/` | DigitalOcean droplets |

Each profile folder contains:

```text
trial-install.sh
8.1.sh
8.2.sh
8.3.sh
assets/first-MOTD.txt
```

Scripts are duplicated per profile today. Customize a profile by editing only that
folder's copies.

## Catalog source of truth

Model and deployment metadata comes from the committed catalog manifest:

```text
data/generated/pages/install-manifest.json
```

`8.2.sh` walks up from its profile directory to locate the repository root and reads
that manifest. Override explicitly when needed:

```bash
export EIGHTBALL_MANIFEST=/path/to/install-manifest.json
```

See `docs/install-manifest-contract.md` for the lookup contract:

```text
manifest.models[model_id].deployments[deployment_type_id]
```

Regenerate after catalog changes:

```bash
python3 -m eight_ball generate
```

## Public / fork-friendly scope

- No Passport, Stripe, S3, or license-activation logic
- No private OpenWebUI or commercial Ollama deployment bundles
- No customer records, fulfillment, or paid entitlement checks
- No secrets or live commercial license endpoints

## What stays in the private installer repository

Paid and commercial install work remains **outside** this public catalog repo:

- Paid packaging and release bundles
- Passport activation and entitlement checks
- Private S3 release artifacts
- Customer install flow and fulfillment
- Commercial OpenWebUI / Ollama deployment assets
- RecordsCore, Stripe, and license-specific automation

## Quick start (Ubuntu)

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/ubuntu/trial-install.sh -o trial-install.sh
sudo bash trial-install.sh
```

Or pipe directly:

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/ubuntu/trial-install.sh | sudo bash
```

From a repository checkout:

```bash
cd install/ubuntu
sudo ./trial-install.sh
```

Optional flags:

```bash
sudo ./trial-install.sh --model qwen3:0.6b
sudo ./trial-install.sh --no-motd
sudo ./trial-install.sh --manifest ../../data/generated/pages/install-manifest.json
```

## Validation

```bash
bash -n install/ubuntu/trial-install.sh install/ubuntu/8.1.sh install/ubuntu/8.2.sh install/ubuntu/8.3.sh
bash tests/test-shell-baseline.sh
bash -n install/ubuntu/cpu/8.1.sh install/ubuntu/cpu/8.2.sh install/ubuntu/cpu/8.3.sh
bash -n install/*/*.sh install/cloud/*/*.sh
shellcheck install/ubuntu/*.sh   # when shellcheck is available
```

## Support contact (public trial only)

The `remember` helper points users to `8ball@terminal.glass` for upgrade questions.
It does not activate paid features from this repository.
