import logging
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib


def load_config(root: Optional[Path] = None) -> dict[str, Any]:
    """Load configuration from .prodguardian.toml files."""
    config = {
        "llm": {"model": "gpt-3.5-turbo", "max_cost_usd": 0.10, "max_tokens": 32000},
        "scan": {
            "parallel": False,
            "workers": None,
            "ignore_dirs": [".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", "target"],
            "rules": None,
        },
        "generator": {"auto_confirm": False},
    }

    # Project-level config
    if root is None:
        root = Path.cwd()
    proj_config = root / ".prodguardian.toml"
    if proj_config.exists():
        try:
            with open(proj_config, "rb") as f:
                user_config = tomllib.load(f)
            _merge_config(config, user_config)
            logger.debug(f"Loaded project config from {proj_config}")
        except Exception as e:
            logger.warning(f"Error reading config: {e}")

    # User-level config
    user_config_path = Path.home() / ".prodguardian.toml"
    if user_config_path.exists():
        try:
            with open(user_config_path, "rb") as f:
                user_config = tomllib.load(f)
            _merge_config(config, user_config)
            logger.debug(f"Loaded user config from {user_config_path}")
        except Exception as e:
            logger.warning(f"Error reading user config: {e}")

    return config


def _merge_config(base: dict, override: dict):
    """Deep merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge_config(base[key], value)
        else:
            base[key] = value


def get_config_value(config: dict, *keys, default=None):
    """Get a nested config value by keys."""
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
