# Proxmox Launch Test Matrix — 8-BALL 0.8

Use disposable VM snapshots. After each test, revert the VM and collect artifacts.

## Environments

| ID | Profile | RAM | GPU | Notes |
| --- | --- | --- | --- | --- |
| U1 | ubuntu/cpu | 4 GB | none | Minimum pilot band |
| U2 | ubuntu/cpu | 8 GB | none | pilot-8gb band |
| U3 | ubuntu/cpu | 16 GB | none | pilot-12gb band |
| U4 | ubuntu/cpu | 24+ GB | none | pilot-24gb-plus band |
| U5 | ubuntu/cuda | 16+ GB | NVIDIA small VRAM (<8 GB) | Entry CUDA |
| U6 | ubuntu/cuda | 16+ GB | NVIDIA medium VRAM (8–16 GB) | Mid CUDA |
| U7 | ubuntu/cuda | 32+ GB | NVIDIA large VRAM (16+ GB) | Large CUDA |
| D1 | cloud/digitalocean/cpu-droplet | 4–8 GB | none | DO CPU shape |
| D2 | cloud/digitalocean/gpu-droplet | 16+ GB | NVIDIA | DO GPU if available |
| A1 | cloud/aws-lightsail/cpu | 4–8 GB | none | Lightsail CPU |
| A2 | cloud/aws-lightsail/gpu | 16+ GB | NVIDIA | Lightsail GPU if available |
| B1 | Debian CPU | 8 GB | none | Non-Ubuntu debian family |

## Install Commands

From a clean snapshot with the release branch checked out:

```bash
cd /path/to/8-ball/install/ubuntu
sudo EIGHTBALL_RELEASE=v0.8.0 ./trial-install.sh
```

Variants:

```bash
# Idempotent re-run
sudo ./trial-install.sh

# Skip MOTD
sudo ./trial-install.sh --no-motd

# Manual model
sudo ./8.2.sh --model qwen3:0.6b

# Lane-specific entry
sudo ./cpu/trial-install.sh
```

## Collection Script

Run after install on each VM:

```bash
sudo bash -c '
PH=/opt/philosopher
echo "=== HARDWARE ==="
python3 /path/to/8-ball/install/shared/c10-hardware-resolve.py plan
echo "=== OLLAMA BIND ==="
ss -ltn | grep 11434 || true
echo "=== OLLAMA STATUS ==="
systemctl is-active ollama || true
curl -fsS http://127.0.0.1:11434/api/tags | head -c 500; echo
echo "=== MODEL LIST ==="
ollama list || true
echo "=== RESULT FILE ==="
cat $PH/8ball-result.txt 2>/dev/null || true
echo "=== TRIAL LOG ==="
tail -n 40 $PH/8ball-trial.log 2>/dev/null || true
echo "=== MOTD ==="
run-parts /etc/update-motd.d 2>/dev/null | head -n 30
echo "=== TRIAL MARKER ==="
cat $PH/trial-installed 2>/dev/null || true
'
```

## Pass Criteria per VM

- [ ] `8.1` binds Ollama to `127.0.0.1:11434` only
- [ ] `8.2` result shows detected lane and selection source
- [ ] Model test `PASSED` with inference-verified model
- [ ] MOTD shows `Local Model ........ READY` when model installed
- [ ] MOTD makes no network calls
- [ ] Re-run does not break swap/Ollama/existing models
- [ ] `trial-installed` marker present with suite version

## Snapshot Discipline

1. Revert VM to clean snapshot
2. Run install for matrix row
3. Run collection script, save output as `artifacts/<ID>-<date>.txt`
4. Revert before next row
