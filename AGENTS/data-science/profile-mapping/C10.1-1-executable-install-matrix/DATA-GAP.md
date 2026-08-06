# AWS Lightsail GPU lane — provisional behavior

Working assumption file:

`AGENTS/TG-8Ball-AWS-Lightsail-GPU-Provisional-Behavior.csv`

This is **control/provenance data**, not verified hardware facts. Published vCPU, RAM, and
storage values are copied from `AGENTS/TG-8Ball-AWS-Lightsail-Research-GPU-Plans.csv`.
GPU vendor, model, count, VRAM, CUDA, and Ollama GPU support remain **unknown** until a
real Lightsail GPU probe upgrades the CSV.

## Runtime probe (required before claiming GPU fit)

Run on the target instance and redact credentials, instance identifiers, public IPs,
hostnames with private information, and secrets before committing probe output:

```bash
uname -a
lspci -nn | grep -Ei 'nvidia|amd|vga|3d'
nvidia-smi
lsmod | grep -E '^nvidia'
command -v nvcc && nvcc --version
free -h
lsblk
df -h
ollama --version
```

Perform a safe Ollama smoke test and record whether GPU offload occurred (for example via
`ollama ps` processor evidence).

## Current generator behavior

- Install lane scripts: `install/cloud/aws-lightsail/gpu/`
- Provider assumption: `profiles/provider-assumptions/cloud-aws-lightsail-gpu.json`
- Uses smallest published plan (GPU XL: 4 vCPU, 16 GiB RAM, 50 GiB disk) as conservative baseline
- `total_vram_gb` and `cuda_available` remain null → model fits on this lane are `unknown`, never auto-selected

## Resolution path

1. Run the runtime probe on a Lightsail for Research GPU instance.
2. Update `AGENTS/TG-8Ball-AWS-Lightsail-GPU-Provisional-Behavior.csv` with measured GPU facts.
3. Regenerate: `python3 scripts/generate-c10-profiles.py`
