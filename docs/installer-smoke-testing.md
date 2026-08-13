# Installer offline smoke testing (C10.2-5)

The smoke harness exercises public installer entrypoints in **no-mutation** modes only.
It complements the structural conformance gate (`scripts/validate-install-lanes.py`) by
executing `--help`/`-Help` and `--preflight`/`-Preflight` paths under an isolated
environment with blocked package managers, downloaders, and Ollama lifecycle commands.

## What it proves

- Every public shell/Windows entrypoint exposes usable help without mutating the host.
- Preflight modes identify their lane and planned checks without claiming a successful install.
- Mac and Windows lanes stop cleanly on unsupported hosts (for example Linux CI agents).
- Help/preflight paths do not invoke `sudo`, package managers, downloaders, service managers,
  `ollama pull/serve/run`, or model-registry clients under a controlled `PATH`.

## What it does not prove

- No Ollama install, model pull, cloud provisioning, or real inference occurs.
- Windows dynamic checks are **not run** when `pwsh`/`powershell` is unavailable; the JSON
  report records `not_run` with reason `pwsh unavailable` (never counted as `pass`).
- True platform acceptance still requires later disposable Mac/Windows/Linux host testing.

## Running locally

```bash
python3 scripts/validate-install-lanes.py
python3 scripts/smoke-install-lanes.py
python3 scripts/smoke-install-lanes.py --json-out reports/installer-smoke-results.json
python3 -m pytest tests/test_smoke_install_lanes.py -q
```

Determinism check:

```bash
python3 scripts/smoke-install-lanes.py --json-out reports/installer-smoke-results.json
python3 scripts/smoke-install-lanes.py --json-out /tmp/installer-smoke-results-second.json
cmp reports/installer-smoke-results.json /tmp/installer-smoke-results-second.json
```

## Report statuses

| Status | Meaning |
| --- | --- |
| `pass` | Help or preflight behaved correctly under isolation |
| `fail` | Mutation attempt, missing usage, or incorrect preflight contract |
| `unsupported` | Lane correctly rejected this host before installer action |
| `not_run` | Dynamic check skipped (for example Windows without `pwsh`) |

The harness exits `0` when there are no `fail` results. `not_run` and `unsupported`
remain visible in `reports/installer-smoke-results.json` and are never tallied as `pass`.

## Public entrypoint contract

- Shell lanes: `-h`/`--help` and `--preflight`
- Windows lanes: `-Help` and `-Preflight`

Preflight must print the lane id and planned checks, must not claim installation succeeded,
and must exit nonzero on unsupported host/lane combinations without attempting a fallback install.
