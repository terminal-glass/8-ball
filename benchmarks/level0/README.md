# Level-0 benchmark (Raspberry Pi class)

Measures whether the 8-BALL canary (`tinyllama:1.1b`) and `llama3.2:1b` run
on a level-0 machine (`config/hardware_scale.yaml#level-0`), how slow they
are, whether cron keeps firing while the model is busy, and how OpenClaw
behaves when it is the consultant.

Results: [RESULTS.md](RESULTS.md) (findings) and
[RESULTS-TABLE.md](RESULTS-TABLE.md) (generated table). Raw data:
`results/<label>/`.

## Scripts

| Script | Runs on | What it does |
| --- | --- | --- |
| `l0_bench.py` | any host with Ollama | N runs per model of one fixed consultation prompt (temperature 0, seed 42, 128 tokens). Records load ok, load time, TTFT, prompt and eval tok/s, runner peak RSS (VmHWM), cgroup `memory.peak`, OOM kills. The first run per model is cold (all models unloaded first). |
| `cron_test.sh` | any host with cron | Temporary every-minute crontab probe for N minutes while the model generates non-stop; reports fired, missed and late runs. `MODEL=none` tests cron without model load. Restores the user's crontab afterwards. |
| `run_host.sh` | the target | One command per machine: installs Ollama if missing, pulls the models, runs the bench and one cron test per model. Writes `results/<LABEL>/`. |
| `run_remote.sh` | your workstation | Same, over ssh: `SSH="ssh <target>" LABEL=<label> ./run_remote.sh`. Copies the scripts, runs `run_host.sh`, copies the results back. |
| `run_level0.sh` | a Linux server with cgroup v2 + sudo | Emulates level 0 with a cgroup slice (pinned CPUs, `cpu.max`, `memory.max`, no swap) and runs Ollama, the bench, and optionally the cron test inside it. |
| `openclaw_test.sh` | the target | Installs Node 24 and OpenClaw if missing, configures a loopback gateway with only the hosted Meta provider, stops Ollama, measures gateway RAM, tries one consultation turn with no API key, runs the cron probe next to the gateway, and optionally (`LOCAL_MODEL=tinyllama:1.1b`) tries the consultation through OpenClaw on the local canary. |
| `summarize.py` | anywhere | Rebuilds `RESULTS-TABLE.md` from `results/`. Fixed columns, so a host that has not run yet shows "pending". |

## Same run on the arm64 VM

```bash
SSH="ssh <arm64-vm>" LABEL=vm-arm64-2g ./run_remote.sh
# then, on the VM: LABEL=vm-arm64-2g STOP_OLLAMA=1 CRON_MINUTES=5 LOCAL_MODEL=tinyllama:1.1b ./openclaw_test.sh
python3 summarize.py
```

`NUM_THREAD` defaults to `nproc` on the target. Results record only the CPU
model, core and RAM counts, OS, and the constraints used.
