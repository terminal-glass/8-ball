# llama2 — Deployment Type 6

- Ollama identifier: `llama2:70b`
- Assessment: insufficient_memory
- Hardware profile: cpu-small
- Runtime policy: batch

## Sizing

- Installed storage (bytes est.): 42120000000
- Min system RAM (GB est.): 83.05
- Recommended system RAM (GB est.): 99.66
- Min VRAM (GB est.): 42.9
- Recommended VRAM (GB est.): 83.05
- CPU suitability: practical_for_cpu_inference
- GPU suitability: not_applicable

Estimated memory exceeds CPU-only system RAM.

- Pull: `ollama pull llama2:70b`
- Run: `ollama run llama2:70b`