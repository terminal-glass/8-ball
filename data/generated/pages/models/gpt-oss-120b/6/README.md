# gpt-oss — Deployment Type 6

- Ollama identifier: `gpt-oss:120b-cloud`
- Assessment: insufficient_memory
- Hardware profile: cpu-small
- Runtime policy: batch

## Sizing

- Installed storage (bytes est.): 70200000000
- Min system RAM (GB est.): 139.15
- Recommended system RAM (GB est.): 166.98
- Min VRAM (GB est.): 71.5
- Recommended VRAM (GB est.): 139.15
- CPU suitability: practical_for_cpu_inference
- GPU suitability: not_applicable

Estimated memory exceeds CPU-only system RAM.

- Pull: `ollama pull gpt-oss:120b-cloud`
- Run: `ollama run gpt-oss:120b-cloud`