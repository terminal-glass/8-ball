<!-- Generated from config/components.yaml by eight_ball.generate.component_display. Do not edit by hand. -->

# 8-BALL component inventory

This page is generated from `config/components.yaml`.
It is the display record for runtime, UI, manager, installer, catalog,
and optional agent adapters. It is not a second model catalog.

Canonical catalog version: `2026.08.01` in `data/normalized/`.
Size unit policy: `decimal` (1 KB = 1000 bytes). Download size is not RAM or VRAM.

The basic Independent AI workflow does not require a paid license.
Planned and untested parts are labeled that way.

| Component | Role | Required | Placement | License | Source | Status | Tested |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Model catalog | catalog | required | local | unchosen | https://github.com/terminal-glass/8-ball | maintained | repository-tests |
| Hardware estimator | hardware | required | local | unchosen | https://github.com/terminal-glass/8-ball | maintained | repository-tests |
| Free trial installer | installer | required | local | unchosen | https://github.com/terminal-glass/8-ball | maintained | repository-tests |
| Ollama runtime | runtime | required | local | upstream-unvendored | https://github.com/ollama/ollama | external | untested |
| Free model manager | manager | optional | local | unchosen | https://github.com/terminal-glass/8-ball | experimental | mock-api |
| Model workspace UI | ui | optional | local | not-applicable | https://github.com/terminal-glass/8-ball | planned | planned |
| Open WebUI | ui | optional | local | upstream-unvendored | https://github.com/open-webui/open-webui | external | untested |
| Ollama Cloud | runtime | optional | hosted | upstream-unvendored | https://ollama.com | external | untested |
| OpenClaw adapter | agent-adapter | optional | local | unchosen | https://github.com/terminal-glass/8-ball | planned | planned |
| Hermes adapter | agent-adapter | optional | local | unchosen | https://github.com/terminal-glass/8-ball | planned | planned |
| OSAMP local gate | agent-adapter | optional | local | unchosen | https://github.com/terminal-glass/8-ball | experimental | repository-tests |

## Notes

- **Model catalog** (`catalog`): Canonical public catalog 2026.08.01 in data/normalized/. Single source of truth. Metadata only. Decimal SI bytes.
  License text: Not chosen. Jonathan must choose a license. This placeholder grants nothing.
- **Hardware estimator** (`hardware-estimator`): Estimates are labeled estimated. Repository tests cover the estimator. Live hardware execution is untested in this change.
  License text: Not chosen. Jonathan must choose a license. This placeholder grants nothing.
- **Free trial installer** (`trial-installer`): Chain is trial-install.sh then 8.1.sh then 8.2.sh then 8.3.sh. No paid license. Lane conformance tests exist. Live installs on macOS, Windows, Lightsail, and DigitalOcean are untested in this change.
  License text: Not chosen. Jonathan must choose a license. This placeholder grants nothing.
- **Ollama runtime** (`ollama-runtime`): Local runtime for list, pull, run, and remove. This repository does not vendor Ollama or download model weights in catalog work. Not started by the catalog tests.
  License text: Upstream license is not vendored and is not relicensed here. Confirm at the source.
- **Free model manager** (`model-manager`): Experimental 8.4a lifecycle for browse, suitability, pull, use, list, and remove. Letter suffix: not part of trial-install.sh then 8.1.sh then 8.2.sh then 8.3.sh. Tested with a mocked Ollama API. Live hardware and a real model download are untested.
  License text: Not chosen. Jonathan must choose a license. This placeholder grants nothing.
- **Model workspace UI** (`workspace-ui`): No free model-manager UI is in this repository. Display records are generated from validated catalog data, not from hand-kept HTML.
  License text: Not applicable until a UI is added. This repository does not grant a license.
- **Open WebUI** (`open-webui`): Optional chat workspace. Not required for the free model workflow.
  License text: Upstream license is not vendored and is not relicensed here. Confirm at the source.
- **Ollama Cloud** (`ollama-cloud`): Optional hosted inference. Cloud-only catalog entries are not local downloads. No cloud purchase is required for the basic local workflow.
  License text: Upstream service terms are not vendored here.
- **OpenClaw adapter** (`openclaw-adapter`): Optional agent adapter. Planned only. Not implemented and not tested.
  License text: Not chosen. An adapter is not implemented, so no adapter license is granted.
- **Hermes adapter** (`hermes-adapter`): Optional agent adapter. Planned only. Not implemented and not tested.
  License text: Not chosen. An adapter is not implemented, so no adapter license is granted.
- **OSAMP local gate** (`osamp-gate`): Optional local gate for OSAMP (Open Source Agent Mail Protocol, AfricaTogether Project by NoCloudGPT). Identity, contract, scope, revocation, replay, expiry, and budget checks are tested. OpenClaw and Hermes adapters stay planned. Wire formats and federation are unresolved. The white paper is a proposal, not a deployed federation.
  License text: Not chosen. Jonathan must choose a license. This placeholder grants nothing.
