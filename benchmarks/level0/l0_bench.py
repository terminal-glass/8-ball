#!/usr/bin/env python3
"""Level-0 (Raspberry Pi class) canary benchmark for 8-BALL.

Runs against an Ollama server that the caller has already started inside a
CPU/RAM-constrained cgroup (see run_level0.sh). For each model it does N
runs of a fixed consultation-style prompt and records: load ok, load time,
time to first token (TTFT, wall clock, streaming), prompt and eval tokens/s
(from Ollama's eval_count/eval_duration), and peak RSS of the model runner
(VmHWM) plus the cgroup's memory.peak.

Output: one JSON object per run on stdout (JSON Lines). No secrets, no
hostnames; the only machine facts recorded are CPU model and constraints.
"""
import argparse, json, os, re, subprocess, sys, threading, time, urllib.request

PROMPT = (
    "You are an installer consultant. A customer has a Raspberry Pi class "
    "computer with 4 CPU cores and 2 GB of RAM and wants a private local AI "
    "assistant. In five short bullet points, say what will run well, what "
    "will be slow, and whether they should use a hosted model instead."
)

def runner_pids():
    out = subprocess.run(["pgrep", "-f", "ollama runner|llama-server|ollama_llama_server"],
                         capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if int(p) != os.getpid()]

def vm_hwm_kb(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])
    except OSError:
        return None

class RssSampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.peak_kb = 0; self.stop = False
    def run(self):
        while not self.stop:
            for p in runner_pids():
                v = vm_hwm_kb(p)
                if v and v > self.peak_kb: self.peak_kb = v
            time.sleep(0.2)

def post(host, path, body, stream=False, timeout=900):
    req = urllib.request.Request(f"http://{host}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)

def loaded(host):
    try:
        with urllib.request.urlopen(f"http://{host}/api/ps", timeout=10) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return []

def unload(host, model):
    """Unload every loaded model and wait until no runner process is left, so
    a cold run starts from an empty machine (and RSS is not mixed up)."""
    for m in set(loaded(host) + [model]):
        try:
            post(host, "/api/generate", {"model": m, "keep_alive": 0}).read()
        except Exception:
            pass
    for _ in range(60):
        if not loaded(host) and not runner_pids():
            break
        time.sleep(1)
    time.sleep(2)

NUM_THREAD = len(os.sched_getaffinity(0))

def one_run(host, model, num_ctx, num_predict, cold):
    if cold: unload(host, model)
    sampler = RssSampler(); sampler.start()
    t0 = time.monotonic(); ttft = None; final = None; err = None; text = []
    try:
        r = post(host, "/api/generate", {
            "model": model, "prompt": PROMPT, "stream": True, "keep_alive": "10m",
            "options": {"num_ctx": num_ctx, "num_predict": num_predict,
                        "temperature": 0, "seed": 42, "num_thread": NUM_THREAD}})
        for line in r:
            if not line.strip(): continue
            d = json.loads(line)
            if "error" in d: err = d["error"]; break
            if d.get("response") and ttft is None: ttft = time.monotonic() - t0
            text.append(d.get("response", ""))
            if d.get("done"): final = d
    except Exception as e:  # load failure, OOM kill, timeout
        err = f"{type(e).__name__}: {e}"
    wall = time.monotonic() - t0
    time.sleep(0.5); sampler.stop = True; sampler.join()
    res = {"model": model, "cold": cold, "ok": final is not None and err is None,
           "error": err, "wall_s": round(wall, 2),
           "ttft_s": round(ttft, 2) if ttft else None,
           "runner_peak_rss_mb": round(sampler.peak_kb / 1024, 1) if sampler.peak_kb else None,
           "loadavg": open("/proc/loadavg").read().split()[:3]}
    if final:
        ns = 1e9
        res.update({
            "load_s": round(final.get("load_duration", 0) / ns, 2),
            "prompt_tokens": final.get("prompt_eval_count"),
            "prompt_tok_s": round(final["prompt_eval_count"] / (final["prompt_eval_duration"] / ns), 2)
                if final.get("prompt_eval_duration") else None,
            "eval_tokens": final.get("eval_count"),
            "eval_tok_s": round(final["eval_count"] / (final["eval_duration"] / ns), 2)
                if final.get("eval_duration") else None,
            "output_head": "".join(text)[:160]})
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1:11555")
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-predict", type=int, default=128)
    ap.add_argument("--cgroup", default=None, help="cgroup v2 dir to read memory.peak from")
    ap.add_argument("--profile", default="unnamed")
    ap.add_argument("--num-thread", type=int, default=None,
                    help="threads for llama.cpp; default = CPUs in our affinity mask (a real Pi sees 4)")
    a = ap.parse_args()
    global NUM_THREAD
    if a.num_thread: NUM_THREAD = a.num_thread
    for m in a.model:
        for i in range(a.runs):
            r = one_run(a.host, m, a.num_ctx, a.num_predict, cold=(i == 0))
            r.update({"num_thread": NUM_THREAD, "profile": a.profile, "run": i + 1, "num_ctx": a.num_ctx,
                      "num_predict": a.num_predict})
            if a.cgroup:
                try: r["cgroup_memory_peak_mb"] = round(int(open(f"{a.cgroup}/memory.peak").read()) / 2**20, 1)
                except OSError: pass
                try:
                    ev = dict(l.split() for l in open(f"{a.cgroup}/memory.events"))
                    r["cgroup_oom_kills"] = int(ev.get("oom_kill", 0))
                except OSError: pass
            print(json.dumps(r), flush=True)

if __name__ == "__main__":
    main()
