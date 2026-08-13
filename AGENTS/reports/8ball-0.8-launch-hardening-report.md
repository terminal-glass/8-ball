# 8-BALL 0.8 Launch Hardening Report

Date: 2026-08-13  
Branch: `cursor/8ball-launch-hardening-1896`  
Status: **code-complete, locally tested** — not VM-tested, not launch-ready

## COMPLETED

- **Baseline inspection** — documented architecture, profile tree, consumable artifacts, gaps (`AGENTS/reports/8ball-0.8-launch-baseline.md`)
- **8.1 localhost Ollama** — systemd drop-in `OLLAMA_HOST=127.0.0.1:11434`, public-bind detection/correction, `ss` listener verification, improved logging, idempotent optional swap
- **8.2 profile integration** — `c10-hardware-resolve.py` resolves hardware → lane → `profiles/qwen3/<lane>/lane.json` candidates with `8ball-base-pilot-menu.json` fallback; real pull + inference proof; manual `--model` override with disk check; expanded result file
- **8.3 MOTD fix** — READY/MISSING based on actual `ollama list` matching (not result file alone); temp alert with `0640` meta; bulletin offline default; trial-installed marker; safe state permissions
- **Version contract** — `EIGHTBALL_SCRIPT_VERSION=0.8.0` + `8ball-version.sh` bundle verification
- **Release pinning** — default `EIGHTBALL_RELEASE=v0.8.0`, SHA-256 manifest at `install/releases/v0.8.0/manifest.json`, `scripts/generate-release-manifest.sh`
- **Ubuntu lane wrappers** — `install/ubuntu/cpu/` and `install/ubuntu/cuda/` delegate to canonical scripts
- **Static validation** — `bash -n` on all modified scripts; offline harness at `scripts/test-installer-harness.sh`
- **Proxmox matrix** — `docs/proxmox-launch-test-matrix.md` with collection commands
- **Tests** — `tests/test_installer_hardening.py`; lane conformance updated for modernized Ubuntu lanes

## PARTIALLY COMPLETED

- **Cloud lane scripts** — still use legacy full copies; not wired to shared hardened modules (debt tracked in `validate-install-lanes.py`)
- **Release SHA verification** — manifest exists for v0.8.0; tag not yet published on GitHub (verification skipped when `EIGHTBALL_RELEASE=main`)
- **8.3 bulletin refresh** — install-time only when `EIGHTBALL_BULLETIN_URL` set; login remains offline

## BLOCKED

- None for code work. Public `v0.8.0` git tag creation requires human release action.

## NEEDS REAL VM TESTING

- First install on clean Ubuntu 4/8/16/24+ GB VMs
- Idempotent re-run (swap, Ollama, existing models preserved)
- Ollama already installed with public bind correction
- CUDA lanes with real NVIDIA hardware
- DigitalOcean / AWS Lightsail profile detection
- MOTD READY state after successful install
- Manual `--model` failure path
- Model pull/inference failure fallback chain

## FILES MODIFIED

| Area | Files |
| --- | --- |
| Shared libs | `install/shared/8ball-version.sh`, `ollama-localhost.sh`, `8ball-model-test.sh`, `8ball-release.sh`, `c10-hardware-resolve.py` |
| Ubuntu canonical | `install/ubuntu/{trial-install,8.1,8.2,8.3}.sh` |
| Ubuntu lanes | `install/ubuntu/cpu/*.sh`, `install/ubuntu/cuda/*.sh` (wrappers) |
| Release | `install/releases/v0.8.0/manifest.json`, `scripts/generate-release-manifest.sh` |
| Tests/docs | `scripts/test-installer-harness.sh`, `tests/test_installer_hardening.py`, `docs/proxmox-launch-test-matrix.md` |
| Validation | `scripts/validate-install-lanes.py`, `tests/test_install_lane_conformance.py` |
| Reports | `AGENTS/reports/8ball-0.8-launch-baseline.md`, this file |

## TEST RESULTS

| Check | Result |
| --- | --- |
| `bash -n` all ubuntu scripts | PASS |
| `scripts/test-installer-harness.sh` | PASS (8 pass, 0 fail, 11 not tested) |
| `pytest tests/test_installer_hardening.py` | PASS |
| `pytest tests/test_install_lane_conformance.py` | PASS |
| `python3 scripts/validate-install-lanes.py` | PASS |
| `bash scripts/validate-catalog.sh` | PASS (full suite) |
| ShellCheck | NOT TESTED (not installed) |
| Live VM install | NOT TESTED |

## KNOWN RISKS

1. **Ollama localhost drop-in** may conflict with user-managed `ollama.service` overrides; script fails closed on uncorrectable public bind.
2. **Profile lane fit** uses assumed provider hardware in lane JSON; runtime RAM may differ — inference test remains authority.
3. **Cloud lane scripts** still legacy; only Ubuntu canonical path fully hardened.
4. **MOTD temp-alert decrement** requires root-writable `8ball-temp-alert.meta` (`0640`); MOTD runs as root via `update-motd.d`.
5. **Release manifest hashes** must be regenerated before tagging `v0.8.0`.

## RECOMMENDED NEXT STEP

1. Run Proxmox matrix (`docs/proxmox-launch-test-matrix.md`) on Ubuntu 4/8/16 GB CPU VMs.
2. Regenerate manifest: `bash scripts/generate-release-manifest.sh v0.8.0`
3. Tag `v0.8.0` and verify `EIGHTBALL_RELEASE=v0.8.0` curl install path.
4. Port shared modules to cloud lane scripts after Ubuntu matrix passes.
