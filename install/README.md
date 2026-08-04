# Public 8-BALL trial installers

These are the **public, free/trial** Terminal.Glass 8-BALL installer scripts. They are
intended for technical users who want to try local AI on their own Ubuntu/Debian host or
fork the flow for experimentation.

## What lives here

| Path | Role |
| --- | --- |
| `trial-install.sh` | Public entrypoint (`8.1` → `8.2` → `8.3`) |
| `8.1.sh` | Foundation: packages, Ollama install, local API check |
| `8.2.sh` | Model selection and inference test using the catalog manifest |
| `8.3.sh` | Login MOTD and simple helper commands |
| `assets/first-MOTD.txt` | MOTD template installed by `8.3.sh` |

## Catalog source of truth

Model and deployment metadata comes from the committed catalog manifest:

```text
data/generated/pages/install-manifest.json
```

`8.2.sh` reads that file. It does **not** scrape Markdown README files or guess model
identity from folder names. See `docs/install-manifest-contract.md` for the lookup
contract:

```text
manifest.models[model_id].deployments[deployment_type_id]
```

When you clone or fork this repository, the default manifest path is resolved relative
to the repo root. Override with:

```bash
export EIGHTBALL_MANIFEST=/path/to/install-manifest.json
```

Regenerate the manifest after catalog changes:

```bash
python3 -m eight_ball generate
```

## Public / fork-friendly scope

This directory is deliberately small and self-contained:

- No Passport, Stripe, S3, or license-activation logic
- No private OpenWebUI or commercial Ollama deployment bundles
- No customer records, fulfillment, or paid entitlement checks
- No secrets or live commercial license endpoints

A fork should be able to understand the trial flow by reading these scripts and the
manifest contract alone.

## What stays in the private installer repository

Paid and commercial install work remains **outside** this public catalog repo:

- Paid packaging and release bundles
- Passport activation and entitlement checks
- Private S3 release artifacts
- Customer install flow and fulfillment
- Commercial OpenWebUI / Ollama deployment assets
- RecordsCore, Stripe, and license-specific automation

## Quick start (full repo checkout)

```bash
cd install
sudo ./trial-install.sh
```

Optional flags:

```bash
sudo ./trial-install.sh --model qwen3:0.6b
sudo ./trial-install.sh --no-motd
sudo ./trial-install.sh --manifest ../data/generated/pages/install-manifest.json
```

## Validation

```bash
bash -n install/*.sh
shellcheck install/*.sh   # when shellcheck is available
```

## Support contact (public trial only)

The `remember` helper points users to `8ball@terminal.glass` for upgrade questions.
It does not activate paid features from this repository.
