"""Load, save, and apply ProdGuardian user settings."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from prodguardian.scan.presets_data import load_all_presets, load_all_rules

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

CONFIG_PATH = Path.home() / ".prodguardian.toml"
PRESETS_RULES_PATH = Path.home() / ".prodguardian_presets.json"
LLM_CACHE_DIR = Path.home() / ".prodguardian_llm_cache"

DEFAULT_SETTINGS: dict[str, Any] = {
    "llm": {
        "model": "gpt-3.5-turbo",
        "max_cost_usd": 0.10,
        "max_tokens": 32000,
        "provider": "api",
        "scan_mode": "mono",
        "analyzer_model": "groq/llama-3.3-70b-versatile",
        "reporter_model": "groq/llama-3.1-8b-instant",
    },
    "scan": {
        "skip_test_dirs": True,
        "parallel": True,
        "workers": 4,
        "ignore_dirs": [],
        "groq_chunk_delay": 6,
    },
    "generator": {
        "auto_confirm": False,
    },
}


def load_user_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "rb") as f:
                return tomllib.load(f)
        except Exception:
            pass
    return {}


def _load_presets_rules_file() -> dict[str, Any]:
    if PRESETS_RULES_PATH.exists():
        try:
            return json.loads(PRESETS_RULES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_presets_rules_file(data: dict[str, Any]) -> None:
    PRESETS_RULES_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_presets() -> list[dict[str, Any]]:
    data = _load_presets_rules_file()
    saved = data.get("presets", [])
    if not saved:
        return load_all_presets()
    return load_all_presets(saved)


def get_rules() -> list[dict[str, Any]]:
    data = _load_presets_rules_file()
    saved = data.get("rules", [])
    if not saved:
        return load_all_rules()
    return load_all_rules(saved)


def save_presets_rules(presets: list[dict[str, Any]], rules: list[dict[str, Any]]) -> None:
    _save_presets_rules_file({"presets": presets, "rules": rules})


def get_settings() -> dict[str, Any]:
    """Return user settings merged with defaults."""
    merged = {
        "llm": dict(DEFAULT_SETTINGS["llm"]),
        "scan": dict(DEFAULT_SETTINGS["scan"]),
        "generator": dict(DEFAULT_SETTINGS["generator"]),
        "presets": get_presets(),
        "rules": get_rules(),
    }
    saved = load_user_config()
    for section in ("llm", "scan", "generator"):
        if section in saved and isinstance(saved[section], dict):
            merged[section].update(saved[section])
    return merged


def write_user_config(config: dict[str, Any]) -> None:
    lines = ["# ProdGuardian configuration\n"]
    for section, values in config.items():
        if section in ("presets", "rules"):
            continue
        lines.append(f"[{section}]")
        if isinstance(values, dict):
            for key, value in values.items():
                if isinstance(value, str):
                    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'{key} = "{escaped}"')
                elif isinstance(value, bool):
                    lines.append(f"{key} = {'true' if value else 'false'}")
                elif value is None:
                    continue
                elif isinstance(value, list):
                    inner = ", ".join(f'"{item}"' for item in value)
                    lines.append(f"{key} = [{inner}]")
                else:
                    lines.append(f"{key} = {value}")
        lines.append("")
    CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")


def get_saved_llm() -> dict[str, str]:
    """Return the user's saved LLM choice (disk is source of truth)."""
    from prodguardian.llm.active_config import get_active_llm_config

    return get_active_llm_config()


def _persist_llm_config(llm_config: dict[str, str], app: Any | None = None) -> dict[str, str]:
    """Normalize, write to disk, sync env, refresh orchestrator."""
    from prodguardian.llm.active_config import normalize_llm_config, sync_llm_env

    normalized = normalize_llm_config(llm_config)
    config = load_user_config()
    existing = config.get("llm", {})
    config["llm"] = {
        **existing,
        **normalized,
        "provider": normalized["provider"],
        "model": normalized["model"],
        "api_key": normalized["api_key"],
        "base_url": normalized["base_url"],
        "scan_mode": str(llm_config.get("scan_mode", existing.get("scan_mode", "mono"))),
        "analyzer_model": str(
            llm_config.get("analyzer_model", existing.get("analyzer_model", ""))
        ),
        "reporter_model": str(
            llm_config.get("reporter_model", existing.get("reporter_model", ""))
        ),
    }
    write_user_config(config)
    sync_llm_env(normalized)

    if app is not None and hasattr(app, "orchestrator"):
        app.orchestrator.update_settings(normalized)
        app.orchestrator._fixer = None
        app.orchestrator.reload_settings()

    _refresh_status_bar(app)
    return normalized


def apply_llm_config(llm_config: dict[str, str], app: Any | None = None) -> None:
    """Save user AI provider choice — only this model is used by the backend."""
    _persist_llm_config(llm_config, app)


def apply_app_settings(settings: dict[str, Any], app: Any | None = None) -> None:
    """Persist all settings sections and refresh the running app."""
    from prodguardian.llm.active_config import normalize_llm_config, sync_llm_env

    config = load_user_config()
    existing_llm = config.get("llm", {})

    for section in ("scan", "generator"):
        if section in settings:
            config.setdefault(section, {}).update(settings[section])

    llm_payload: dict[str, Any] | None = None
    if "llm" in settings:
        merged = {**existing_llm, **settings["llm"]}
        normalized = normalize_llm_config(merged)
        llm_payload = {
            **normalized,
            "max_cost_usd": float(merged.get("max_cost_usd", existing_llm.get("max_cost_usd", 0.10))),
            "max_tokens": int(merged.get("max_tokens", existing_llm.get("max_tokens", 32000))),
            "scan_mode": str(merged.get("scan_mode", existing_llm.get("scan_mode", "mono"))),
            "analyzer_model": str(
                merged.get("analyzer_model", existing_llm.get("analyzer_model", ""))
            ),
            "reporter_model": str(
                merged.get("reporter_model", existing_llm.get("reporter_model", ""))
            ),
        }
        config["llm"] = llm_payload

    write_user_config(config)

    if "presets" in settings and "rules" in settings:
        save_presets_rules(settings["presets"], settings["rules"])

    if llm_payload:
        sync_llm_env(normalized)

    if app is not None and hasattr(app, "orchestrator"):
        app.orchestrator.reload_settings()
        if llm_payload:
            app.orchestrator.update_settings(llm_payload)

    _refresh_status_bar(app)


def is_llm_configured() -> bool:
    from prodguardian.llm.active_config import is_llm_ready

    return is_llm_ready()


def clear_llm_cache() -> int:
    if not LLM_CACHE_DIR.exists():
        LLM_CACHE_DIR.mkdir(exist_ok=True)
        return 0
    files = list(LLM_CACHE_DIR.glob("*.txt"))
    shutil.rmtree(LLM_CACHE_DIR)
    LLM_CACHE_DIR.mkdir(exist_ok=True)
    return len(files)


def _refresh_status_bar(app: Any | None) -> None:
    if app is None:
        return
    try:
        status_bar = app.query_one("#status-bar")
        project_path = getattr(app, "project_path", None)
        status_bar.update_status(project_path)
    except Exception:
        pass