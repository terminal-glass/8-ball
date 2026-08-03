# mistral-large — Deployment Type 6

- Ollama identifier: `mistral-large:123b`
- Assessment: insufficient_memory
- Hardware profile: cpu-small
- Runtime policy: batch

## Sizing

- Installed storage (bytes est.): 78840000000
- Min system RAM (GB est.): 149.6
- Recommended system RAM (GB est.): 179.52
- Min VRAM (GB est.): 80.3
- Recommended VRAM (GB est.): 149.6
- CPU suitability: practical_for_cpu_inference
- GPU suitability: not_applicable

Estimated memory exceeds CPU-only system RAM.

- Pull: `ollama pull mistral-large:123b`
- Run: `ollama run mistral-large:123b`