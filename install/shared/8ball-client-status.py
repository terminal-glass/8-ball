#!/usr/bin/env python3
"""Lightweight 8-BALL client status evaluation for 8.3 MOTD (no inference, no pulls)."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PHILOSOPHER_ROOT = "/opt/philosopher"
DEFAULT_OLLAMA_API = "http://127.0.0.1:11434"
FORBIDDEN_LOGIN_COMMANDS = (
    "ollama pull",
    "ollama run",
    "c10-hardware-resolve.py",
    "ubuntu-profile-runtime.py",
)


def philosopher_root() -> Path:
    return Path(os.environ.get("PHILOSOPHER_ROOT", DEFAULT_PHILOSOPHER_ROOT))


def result_json_path(root: Path | None = None) -> Path:
    return (root or philosopher_root()) / "8ball-result.json"


def result_txt_path(root: Path | None = None) -> Path:
    return (root or philosopher_root()) / "8ball-result.txt"


def read_install_result(root: Path | None = None) -> dict[str, Any]:
    root = root or philosopher_root()
    payload: dict[str, Any] = {}
    json_path = result_json_path(root)
    if json_path.is_file():
        try:
            payload.update(json.loads(json_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            payload = {}
    text_path = result_txt_path(root)
    if text_path.is_file():
        for line in text_path.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "Model" and not payload.get("selected_model"):
                payload["selected_model"] = value
            elif key == "Profile" and not payload.get("profile_id"):
                payload["profile_id"] = value
            elif key == "Model test" and not payload.get("test_status"):
                payload["test_status"] = value
            elif key == "Jets status" and not payload.get("jets_status"):
                payload["jets_status"] = value
    if "inference_proven" not in payload:
        status = str(payload.get("test_status", "")).upper()
        payload["inference_proven"] = status == "PASSED"
    return payload


def ollama_api_url() -> str:
    return os.environ.get("OLLAMA_API", DEFAULT_OLLAMA_API).rstrip("/")


def ollama_running(api_url: str | None = None) -> bool:
    api = (api_url or ollama_api_url()).rstrip("/")
    try:
        with urllib.request.urlopen(f"{api}/api/tags", timeout=2) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def list_installed_models(api_url: str | None = None) -> list[str]:
    api = (api_url or ollama_api_url()).rstrip("/")
    try:
        with urllib.request.urlopen(f"{api}/api/tags", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []
    names: list[str] = []
    for entry in payload.get("models", []):
        name = str(entry.get("name", "")).strip()
        if name:
            names.append(name)
    if names:
        return names
    return []


def normalize_model_ref(ref: str) -> str:
    return ref.strip()


def model_matches_selected(selected: str, listed: str) -> bool:
    selected = normalize_model_ref(selected)
    listed = normalize_model_ref(listed)
    if not selected or not listed:
        return False
    if selected == listed:
        return True
    if ":" in selected:
        return False
    return listed == selected or listed.startswith(f"{selected}:")


def model_is_installed(selected: str, installed: list[str]) -> bool:
    selected = normalize_model_ref(selected)
    if not selected:
        return False
    return any(model_matches_selected(selected, listed) for listed in installed)


def derive_local_model_status(
    *,
    selected_model: str,
    ollama_available: bool,
    model_installed: bool,
    inference_proven: bool,
) -> str:
    selected_model = normalize_model_ref(selected_model)
    if not selected_model:
        return "NOT CONFIGURED"
    if not ollama_available:
        return "UNAVAILABLE"
    if not inference_proven:
        if model_installed:
            return "PARTIAL"
        return "FAILED"
    if model_installed:
        return "READY"
    return "MISSING"


def derive_jets_status(
    *,
    ollama_available: bool,
    eightballjets_installed: bool,
    inference_proven: bool,
    recorded_jets_status: str,
) -> str:
    recorded = recorded_jets_status.strip().upper().replace(" ", "_")
    if not eightballjets_installed:
        return "UNAVAILABLE"
    if not ollama_available:
        return "UNAVAILABLE"
    if not inference_proven:
        return "PARTIAL"
    if recorded in {"READY", "READY_AFTER_SIGNIN"}:
        return "SIGN-IN REQUIRED"
    if recorded:
        return recorded.replace("_", " ")
    return "SIGN-IN REQUIRED"


def evaluate_status(
    *,
    root: Path | None = None,
    api_url: str | None = None,
    installed_models: list[str] | None = None,
    ollama_available: bool | None = None,
    eightballjets_installed: bool | None = None,
) -> dict[str, Any]:
    root = root or philosopher_root()
    result = read_install_result(root)
    selected_model = normalize_model_ref(str(result.get("selected_model") or ""))
    inference_proven = bool(result.get("inference_proven"))
    test_status = str(result.get("test_status") or "").upper()
    if test_status == "PASSED":
        inference_proven = True
    elif test_status == "FAILED":
        inference_proven = False

    api = api_url or ollama_api_url()
    if ollama_available is None:
        ollama_available = ollama_running(api)
    if installed_models is None:
        installed_models = list_installed_models(api) if ollama_available else []
    model_installed = model_is_installed(selected_model, installed_models)

    if eightballjets_installed is None:
        eightballjets_installed = any(
            Path(path, "8balljets").is_file()
            for path in os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin").split(":")
            if path
        )

    local_model_status = derive_local_model_status(
        selected_model=selected_model,
        ollama_available=ollama_available,
        model_installed=model_installed,
        inference_proven=inference_proven,
    )
    jets_status = derive_jets_status(
        ollama_available=ollama_available,
        eightballjets_installed=eightballjets_installed,
        inference_proven=inference_proven,
        recorded_jets_status=str(result.get("jets_status") or ""),
    )
    return {
        "selected_model": selected_model or "unknown",
        "profile_id": str(result.get("profile_id") or ""),
        "inference_proven": inference_proven,
        "model_installed": model_installed,
        "ollama_status": "RUNNING" if ollama_available else "STOPPED",
        "local_model_status": local_model_status,
        "jets_status": jets_status,
        "installed_models": installed_models,
    }


def decrement_temp_alert(root: Path | None = None) -> dict[str, Any]:
    root = root or philosopher_root()
    meta_path = root / "8ball-temp-alert.meta"
    text_path = root / "8ball-temp-alert.txt"
    history_path = root / "8ball-alert-history"
    if not meta_path.is_file() or not text_path.is_file():
        return {"shown": False, "remaining": 0}
    try:
        remaining = int(re.sub(r"\D", "", meta_path.read_text(encoding="utf-8")) or "0")
    except ValueError:
        return {"shown": False, "remaining": 0, "error": "invalid meta"}
    if remaining <= 0:
        return {"shown": False, "remaining": 0}
    message = text_path.read_text(encoding="utf-8")
    remaining -= 1
    meta_path.write_text(f"{remaining}\n", encoding="utf-8")
    if remaining <= 0:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
    return {"shown": True, "remaining": remaining, "message": message}


def motd_env_lines(status: dict[str, Any]) -> str:
    replacements = {
        "OLLAMA_STATUS": status["ollama_status"],
        "MODEL_STATUS": status["local_model_status"],
        "JETS_STATUS": status["jets_status"],
        "SELECTED_MODEL": status["selected_model"],
    }
    return "\n".join(f'{key}="{value}"' for key, value in replacements.items())


def render_motd(template_path: Path, status: dict[str, Any], alert_message: str = "") -> str:
    text = template_path.read_text(encoding="utf-8")
    if alert_message:
        text = f"{alert_message.rstrip()}\n\n{text}"
    replacements = {
        "__OLLAMA_STATUS__": status["ollama_status"],
        "__MODEL_STATUS__": status["local_model_status"],
        "__JETS_STATUS__": status["jets_status"],
        "__SELECTED_MODEL__": status["selected_model"],
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: 8ball-client-status.py evaluate|motd-env|render-motd|decrement-alert",
            file=sys.stderr,
        )
        return 2
    command = sys.argv[1]
    root = philosopher_root()
    if command == "evaluate":
        print(json.dumps(evaluate_status(root=root), indent=2, sort_keys=True))
        return 0
    if command == "motd-env":
        status = evaluate_status(root=root)
        print(motd_env_lines(status))
        return 0
    if command == "render-motd":
        if len(sys.argv) < 3:
            print("render-motd requires TEMPLATE_PATH", file=sys.stderr)
            return 2
        template = Path(sys.argv[2])
        alert = decrement_temp_alert(root=root)
        alert_message = alert.get("message", "") if alert.get("shown") else ""
        status = evaluate_status(root=root)
        print(render_motd(template, status, str(alert_message)))
        return 0
    if command == "decrement-alert":
        print(json.dumps(decrement_temp_alert(root=root), indent=2, sort_keys=True))
        return 0
    print(f"Unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
