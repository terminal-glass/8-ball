# INST-50B — 8.1 Foundation / Ollama Safety

**Date:** 2026-08-13  
**Contract:** `AGENTS/INST-client-installer-scaffolding.md`  
**Prior stage:** `INST-50A-audit.md`  
**Scope:** 8.1 foundation and Ollama localhost safety only

---

## Implementation Completed

### Ollama localhost safety (`install/shared/ollama-localhost.sh`)

- **Exclusive bind proof** uses `ss` (or `netstat` fallback) only — curl API reachability is no longer accepted as bind proof.
- **Public/wildcard detection** fails on `0.0.0.0:11434`, `[::]:11434`, and `*:11434`.
- **Dual-bind detection** fails when loopback and public listeners coexist on the service port.
- **Configuration scanning** covers `/etc/default/ollama`, `/etc/sysconfig/ollama`, systemd unit files, drop-ins, `EnvironmentFile` indirection, and bare `:port` `OLLAMA_HOST` values.
- **Idempotent drop-in** at `/etc/systemd/system/ollama.service.d/8ball-localhost.conf` — rewritten only when content changes.
- **8-BALL-owned config:** `OLLAMA_HOST=127.0.0.1:11434` and `OLLAMA_ORIGINS=` via systemd drop-in.

### 8.1 orchestration (`install/ubuntu/8.1.sh`)

Execution order:

```text
OS validate → prerequisites → swap → Ollama install/reuse
  → localhost config → service start → API wait
  → foundation verify (service + exclusive listener + API)
```

- Foundation verification runs **after** service start on every path (no early-return skip).
- Fail-closed: unsafe listener or unavailable API blocks progression to 8.2.
- Logging writes to stdout and `${PHILOSOPHER_ROOT}/8ball-trial.log`.
- Swap: recognizes active swap, avoids unrelated `/swapfile`, checks disk before creation, idempotent fstab entry.
- Packages: installs only missing prerequisites (`ca-certificates`, `curl`, `python3`, `zstd`).

### Lane architecture preserved

- Canonical implementation: `install/ubuntu/8.1.sh`
- Thin wrappers unchanged: `install/ubuntu/cpu/8.1.sh`, `install/ubuntu/cuda/8.1.sh`
- CPU and CUDA receive the same foundation via delegation.

---

## Files Changed

| File | Change |
| --- | --- |
| `install/shared/ollama-localhost.sh` | Exclusive listener verification, expanded config scan, idempotent drop-in |
| `install/ubuntu/8.1.sh` | Reordered gates, improved logging/swap/packages, post-start verification |
| `tests/test_inst_50b_ollama_foundation.py` | New focused INST-50B tests (mocked listener/config) |

**Not changed:** `8.2.sh`, `8.3.sh`, `trial-install.sh`, profile data, C-series AGENTS files.

---

## Tests Performed

| Check | Result |
| --- | --- |
| `bash -n` (ubuntu/shared installer scripts) | PASS |
| `scripts/test-installer-harness.sh` | PASS (8 pass, 11 NOT TESTED) |
| `python3 scripts/validate-install-lanes.py` | PASS |
| `pytest tests/test_inst_50b_ollama_foundation.py` | PASS (21 tests) |
| Full `pytest` | PASS (358 passed, 8 skipped) |

### INST-50B test coverage (mocked)

- Public host value detection (`0.0.0.0`, `[::]`, `:port`)
- `EnvironmentFile` and bare-port config scanning
- Safe loopback-only listener acceptance
- Public bind, IPv6 wildcard, and dual-bind rejection
- Missing `ss`/`netstat` failure
- Drop-in idempotency
- CPU/CUDA wrapper delegation
- 8.1 model-neutrality (no profile/model selection logic)

---

## Behavior Intentionally Deferred

| Item | Stage |
| --- | --- |
| 8.2 profile/model integration | INST-50C |
| 8.3 MOTD / alerts | INST-50D |
| Release pinning / remote manifest | INST-50E |
| Full VM validation matrix | INST-50F |
| Non-systemd `nohup ollama serve` bind proof on exotic hosts | INST-50F (if systemd absent) |

---

## NEEDS REAL VM TESTING

The following require disposable Ubuntu/Debian VMs and are **not** proven by mocked CI tests:

| Scenario | Why |
| --- | --- |
| Fresh Ollama install via `ollama.com/install.sh` | Requires root + network |
| Existing Ollama with public `OLLAMA_HOST` correction | Requires real systemd + service restart |
| systemd drop-in persistence across reboot | Requires real systemd |
| Actual `ss` output after Ollama restart | Mocked in CI only |
| Swap creation on low-RAM host | Requires root + disk |
| Second-run idempotency (packages, swap, drop-in, service) | Requires root + prior install state |
| Ubuntu CUDA lane with NVIDIA present | GPU host matrix (INST-50F) |
| Provider images (Lightsail, DigitalOcean) | Cloud lane matrix (INST-50F) |

---

## Handoff to INST-50C

After successful 8.1:

- Ollama API is available at `http://127.0.0.1:11434`
- Listener is exclusive localhost (verified by `ss`)
- Service is active (systemd or background `ollama serve`)
- `${PHILOSOPHER_ROOT}/8ball-trial.log` contains 8.1 gate events
- 8.2 may proceed; 8.1 does not set model/profile variables

**8.1 environment contract for 8.2:**

```text
OLLAMA_API=http://127.0.0.1:11434   (default)
OLLAMA_LOCAL_HOST=127.0.0.1
OLLAMA_LOCAL_PORT=11434
```

INST-50C should assume this foundation and not re-implement Ollama installation.

---

## Revision History

| Date | Notes |
| --- | --- |
| 2026-08-13 | Initial INST-50B implementation record |
