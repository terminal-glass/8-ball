# goliath — Deployment Type 6

- Ollama identifier: `goliath:latest`
- Assessment: insufficient_memory
- Hardware profile: cpu-small
- Runtime policy: batch

## Sizing

- Installed storage (bytes est.): 71280000000
- Min system RAM (GB est.): 74.25
- Recommended system RAM (GB est.): 89.1
- Min VRAM (GB est.): 72.6
- Recommended VRAM (GB est.): 74.25
- CPU suitability: practical_for_cpu_inference
- GPU suitability: not_applicable

Estimated memory exceeds CPU-only system RAM.

- Pull: `ollama pull goliath:latest`
- Run: `ollama run goliath:latest`