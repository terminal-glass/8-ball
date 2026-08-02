# P4 Workload Profiles

P4 defines static workload assumptions for NoCloudGPT internal planning. These profiles describe what common customer workloads generally require before any provider-plan scoring, exact Ollama model matching, pricing, ordering, fulfillment, or installer authoring happens.

The values in this dataset are conservative planning estimates, not performance guarantees. They are intended to help later compatibility logic reason about workload fit separately from provider fit, model fit, and storage fit.

```text
Provider fit
+ Model fit
+ Storage fit
+ Workload fit
= Final recommendation in P5
```

## Scope

P4 does not select exact models and does not assign Ollama tags. Exact model selection is deferred to `P5-Compatibility-Estimator`.

P4 does not select cloud-provider plans or calculate provider compatibility. Infrastructure prices remain in provider datasets, while model download sizes remain in the separate Ollama metadata catalog.

P4 does not create installers, generate `8.sh`, modify Passport, or implement checkout, ordering, fulfillment, or agent execution logic.

## Dataset contents

The workload profiles are stored as individual JSON records in `data/`:

- `personal-chat.json`
- `documents-rag.json`
- `coding-assistant.json`
- `small-business.json`
- `multi-user-office.json`
- `vision-documents.json`
- `agents-automation.json`
- `heavy-ai-research.json`

`data/workloads.json` is a lightweight index. It intentionally duplicates only summary fields needed for discovery and does not duplicate full workload records.

## Capability vocabulary

P4 uses one normalized capability vocabulary aligned with the available metadata categories:

- `text`
- `coding`
- `embedding`
- `vision`
- `tools`
- `thinking`
- `audio`

## Resource assumptions

Each profile distinguishes workload-specific expectations for:

- minimum RAM
- recommended RAM
- minimum vCPU
- recommended vCPU
- base appliance disk
- customer-data reserve
- CPU support
- GPU recommendation
- expected user count
- expected concurrency

These workload resources do not duplicate P1 appliance overhead. The future compatibility engine combines the datasets as follows:

```text
P1 appliance overhead
+ P2 provider specifications
+ P3 Ollama metadata
+ P4 workload profile
= P5 compatibility result
```

Customer workload fit is separate from storage fit and model fit. For example, a deployment may have enough disk for customer documents but still be a poor workload fit if concurrency, RAM, vCPU, or capability needs are not met.

## Agent vocabulary

The `agents-automation` profile uses the terminal.glass vocabulary consistently:

- Glass Agent: an action-capable worker.
- Jet Agent: cloud-model-powered work.
- NoCloudGPT and YourCloudGPT: customer-facing deployment/product vocabulary.

P4 only describes static workload assumptions for Glass Agent and automation-style workloads; it does not implement OpenClaw or agent execution.

## Validation

Run the offline validator:

```bash
python3 AGENTS/data-science/P4-Workload-Profiles/scripts/validate-workloads.py
```

If `pytest` is available, run:

```bash
pytest -q AGENTS/data-science/P4-Workload-Profiles/tests
```
