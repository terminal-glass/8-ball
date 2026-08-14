🎱 8-BALL

😎 Private AI with no more guesswork 😎

<p align="center">
  <img src="assets/8ball-ollama-pool.jpg"
       alt="8-BALL for Ollama — private AI without the hardware and model guesswork"
       width="720">
</p>

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

🚀 $99 Pilot

Want help turning one machine into a complete 8-BALL system?

The $99 8-BALL Pilot is intended for a single machine and can help connect the appropriate pieces around your hardware and intended use.

Learn about the $99 Pilot → terminal.glass/8-ball

⸻

For developers

8-BALL is also the Terminal.Glass model-intelligence catalog for publicly available Ollama models.

### Try 8-BALL on Ubuntu

```bash
curl -fsSL https://raw.githubusercontent.com/terminal-glass/8-ball/main/trial-install.sh -o trial-install.sh
sudo bash trial-install.sh
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

Developers and contributors: continue below for the repository architecture, catalog recreation workflow, CLI, validation, datasets, and provenance documentation.

⸻