🎱 8-BALL

😎 Private AI with no more guesswork 😎

<p align="center">
  <img src="assets/8ball-ollama-pool.jpg"
       alt="8-BALL for Ollama — private AI without the hardware and model guesswork"
       width="720">
</p>

8-BALL is the free Independent AI path for the computer you already have: detect the hardware, browse models that fit, install a local model, use it, and remove it. That basic workflow does not require a purchase or a paid license key.

8-BALL helps match Ollama models and AI tools to the computer you actually have.

Instead of guessing about RAM, VRAM, GPUs, model sizes, and cloud options, 8-BALL is building a hardware-aware catalog and installation system for local and hybrid AI.

Start with Ollama

Ollama gives you local AI models.

8-BALL helps answer the next question:

What should I run on this machine?

8-BALL maps publicly available Ollama models against hardware profiles, model requirements, deployment types, and installation targets.

The goal is simple:

Machine → right-sized Ollama model → working private AI

Add the tools you recognize

Once Ollama is running, 8-BALL is designed around familiar AI tools rather than replacing them.

💬 Open WebUI

Want a familiar browser-based chat interface?

Open WebUI can turn your Ollama server into a persistent AI workspace with conversations, models, and a modern web interface.

✈️ Ollama Cloud + 8-BALL JETS

Small computer? Big job?

Keep a useful model locally and use Ollama Cloud when larger models make more sense.

8-BALL calls these optional cloud-powered models JETS:

🎱 8-BALL JETS — Tiny server. Serious AI.

Local when practical. Cloud when useful.

🦞 OpenClaw

Want AI that can do more than chat?

OpenClaw adds an agent layer for tool-using and action-oriented AI workflows.

8-BALL is being designed so the machine, models, chat interface, cloud models, and agents can fit together without turning installation into a research project.

One machine. A simple path.

🎱 8-BALL
   │
   ├── Ollama ─────────── Local AI
   │
   ├── Open WebUI ─────── Persistent Chat
   │
   ├── Ollama Cloud ───── 8-BALL JETS
   │
   └── OpenClaw ───────── AI Agents

You don’t need every layer.

Start with the machine you have and add what you need.

⸻

The basic Independent AI workflow stays free. Paid help is optional and does not block browsing, suitability, local install, use, or removal.

🚀 $99 Pilot

Want help turning one machine into a complete 8-BALL system?

The $99 8-BALL Pilot is intended for a single machine and can help connect the appropriate pieces around your hardware and intended use.

Learn about the $99 Pilot → terminal.glass/8-ball

⸻

For developers

8-BALL is also the Terminal.Glass model-intelligence catalog for publicly available Ollama models.

### Try 8-BALL on Ubuntu

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/ubuntu/trial-install.sh -o trial-install.sh
sudo bash trial-install.sh
```

Or pipe directly:

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/install/ubuntu/trial-install.sh | sudo bash
```

Optional flags include `--model`, `--model-slug`, and `--no-motd`.

The repository stores metadata rather than model weights and provides the data needed to reason about:

* Ollama models and exact tags
* Published model sizes
* RAM and VRAM estimates
* CPU and GPU hardware profiles
* Model families and quantizations
* Local versus cloud availability
* Deployment recommendations
* Installer-authoring datasets
* Provenance and confidence
* Validation and coverage

8-BALL does not replace Ollama, Open WebUI, Ollama Cloud, or OpenClaw.

It is the model and hardware intelligence that helps these pieces fit the machine.

⸻

Development

8-BALL is under active development.

The current repository contains the catalog, normalized model metadata, hardware estimates, validation tooling, generated recommendations, and public free/trial installer resources.

Developers and contributors: the canonical catalog is version **2026.08.01** in `data/normalized/`. That tree is the source of truth. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add or correct a model, cite evidence, update fixtures, validate, and open a pull request.

## How the parts fit

| Part | Role | Required | Where |
| --- | --- | --- | --- |
| Catalog | Public model metadata | Required | `data/normalized/` |
| Hardware estimator | Labeled fit estimates | Required for guidance | `src/eight_ball/estimate/` |
| Free trial installer | `trial-install.sh` → `8.1.sh` → `8.2.sh` → `8.3.sh` | Required to install the free path | `install/` |
| Ollama | Local runtime | Required to run a local model | Upstream, installed on the machine |
| Model manager | Browse, suitability, pull, use, list, remove | Planned in this repository | Not a paid entitlement |
| Workspace UI | Customer display | Optional | Generated from validated records, not hand-kept HTML |
| Open WebUI and Ollama Cloud | Chat workspace and hosted models | Optional | External |
| Agent adapters and OSAMP | Tool use and agent mail | Optional | Planned until implemented and tested |

The maintained component record is `config/components.yaml`. The readable inventory is generated at [docs/component-inventory.md](docs/component-inventory.md). Download sizes use decimal SI bytes and are not RAM or VRAM. Cloud-only models are not local downloads.

OSAMP means the Open Source Agent Mail Protocol, AfricaTogether Project by NoCloudGPT. The alignment matrix at [docs/osamp-alignment.md](docs/osamp-alignment.md) labels each item implemented, planned, or unresolved. The local gate is tested. Wire formats and a deployed federation are unresolved. OpenClaw and Hermes adapters are planned, not tested.

This repository has no chosen license. `LICENSE` is a placeholder until Jonathan chooses one.

⸻