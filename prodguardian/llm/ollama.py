"""Helpers for discovering and preparing locally installed Ollama models."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Optional

DEFAULT_OLLAMA_HOST = "http://localhost:11434"

RECOMMENDED_SMALL_MODELS: list[dict[str, str]] = [
    {"name": "llama3.2:1b", "size": "1B", "label": "Llama 3.2 1B"},
    {"name": "llama3.2:3b", "size": "3B", "label": "Llama 3.2 3B"},
    {"name": "gemma2:2b", "size": "2B", "label": "Gemma 2 2B"},
    {"name": "qwen2.5:1.5b", "size": "1.5B", "label": "Qwen 2.5 1.5B"},
    {"name": "tinyllama:1.1b", "size": "1.1B", "label": "TinyLlama 1.1B"},
    {"name": "smollm2:1.7b", "size": "1.7B", "label": "SmolLM2 1.7B"},
    {"name": "phi3:mini", "size": "3.8B", "label": "Phi-3 Mini"},
]


def list_ollama_models(
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 5.0,
) -> tuple[list[str], Optional[str]]:
    """
    Return installed Ollama model names and an optional error message.

    Tries the Ollama HTTP API first, then falls back to `ollama list`.
    """
    models, err = _list_via_api(host, timeout)
    if models:
        return models, None
    if err is None:
        return [], "No Ollama models installed yet."

    cli_models, cli_err = _list_via_cli()
    if cli_models:
        return cli_models, None

    return [], err or cli_err


def build_ollama_select_options(
    installed: list[str],
    recommended: list[dict[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """Build dropdown options: installed models first, then downloadable small models."""
    options: list[tuple[str, str]] = []
    recommended = recommended or RECOMMENDED_SMALL_MODELS

    if installed:
        for name in installed:
            options.append((f"{name}  [installed]", name))

    for entry in recommended:
        name = entry["name"]
        if is_model_installed(name, installed):
            continue
        label = entry.get("label", name)
        size = entry.get("size", "")
        options.append((f"{label} ({size}) — download", name))

    return options


def is_model_installed(model: str, installed: list[str]) -> bool:
    """Return True when the model (or an equivalent tag) is already present."""
    if model in installed:
        return True

    model_base, _, model_tag = model.partition(":")
    for inst in installed:
        if inst == model:
            return True
        inst_base, _, inst_tag = inst.partition(":")
        if model_base != inst_base:
            continue
        if not model_tag or not inst_tag:
            return True
        if model_tag == inst_tag:
            return True
    return False


_ollama_serve_started = False


def _start_ollama_serve() -> None:
    """Launch ``ollama serve`` in the background if the API is not up yet."""
    global _ollama_serve_started
    if _ollama_serve_started or not shutil.which("ollama"):
        return
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _ollama_serve_started = True
    except OSError:
        pass


def ensure_ollama_running(
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 30.0,
) -> Optional[str]:
    """Start Ollama if needed and wait until the local API responds."""
    _, err = _list_via_api(host, timeout=2.0)
    if err is None:
        return None

    if not shutil.which("ollama"):
        return "Ollama is not installed. Install it from https://ollama.com"

    _start_ollama_serve()

    try:
        subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Could not start Ollama: {exc}"

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, err = _list_via_api(host, timeout=2.0)
        if err is None:
            return None
        time.sleep(0.5)

    return f"Ollama is not responding at {host}. Open the Ollama app and try again."


def pull_ollama_model(
    model: str,
    on_progress: Callable[[str], None] | None = None,
    timeout: float = 900.0,
) -> Optional[str]:
    """Download a model with `ollama pull`. Returns an error message on failure."""
    if not shutil.which("ollama"):
        return "Ollama CLI not found on PATH."

    try:
        process = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        return f"Could not run `ollama pull {model}`: {exc}"

    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    last_line = ""

    while True:
        if time.monotonic() > deadline:
            process.kill()
            return f"Timed out pulling {model}."

        line = process.stdout.readline()
        if line:
            last_line = line.strip()
            if on_progress and last_line:
                on_progress(last_line)
            continue

        if process.poll() is not None:
            break
        time.sleep(0.1)

    if process.returncode == 0:
        return None

    detail = last_line or f"exit code {process.returncode}"
    return f"Failed to pull {model}: {detail}"


def _list_via_api(host: str, timeout: float) -> tuple[list[str], Optional[str]]:
    url = f"{host.rstrip('/')}/api/tags"
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError:
        return [], f"Ollama is not running at {host}."
    except (TimeoutError, json.JSONDecodeError, KeyError) as exc:
        return [], f"Could not read Ollama models: {exc}"

    models = []
    for entry in payload.get("models", []):
        name = entry.get("name")
        if name:
            models.append(name)
    return sorted(models), None


def _list_via_cli() -> tuple[list[str], Optional[str]]:
    if not shutil.which("ollama"):
        return [], "Ollama CLI not found on PATH."

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"Could not run `ollama list`: {exc}"

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        return [], stderr or "Failed to list Ollama models."

    models = []
    for line in result.stdout.splitlines()[1:]:
        name = line.split()[0] if line.strip() else ""
        if name and name != "NAME":
            models.append(name)
    return sorted(models), None


def ollama_litellm_model(model_name: str) -> str:
    """Map an Ollama model name to the litellm provider prefix."""
    if model_name.startswith("ollama/"):
        return model_name
    return f"ollama/{model_name}"


def prepare_ollama_model(
    model: str,
    on_progress: Callable[[str], None] | None = None,
    host: str = DEFAULT_OLLAMA_HOST,
) -> Optional[str]:
    """
    Ensure Ollama is running and the requested model is available locally.

    Pulls the model automatically when missing. Returns an error message on failure.
    """
    start_error = ensure_ollama_running(host=host)
    if start_error:
        return start_error

    installed, list_error = list_ollama_models(host=host)
    if list_error and not installed:
        return list_error

    if is_model_installed(model, installed):
        return None

    if on_progress:
        on_progress(f"Downloading {model}... This may take a few minutes.")
    return pull_ollama_model(model, on_progress=on_progress)