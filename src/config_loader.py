"""Load and validate config from YAML with env overrides."""

import os
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import ValidationError

from src.state import AppConfig


def _env_override(key: str, default: Any = None) -> Any:
    """Get env var; common keys mapped to config fields."""
    v = os.environ.get(key)
    if v is None:
        return default
    if isinstance(default, bool):
        return v.strip().lower() in ("1", "true", "yes")
    if isinstance(default, int):
        try:
            return int(v)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(v)
        except ValueError:
            return default
    return v


def load_config(config_path: Optional[Union[str, Path]] = None) -> AppConfig:
    """Load YAML config, apply env overrides, validate with Pydantic."""
    if config_path is None:
        base = Path(__file__).resolve().parent.parent
        config_path = base / "config" / "config.yaml"
    path = Path(config_path)
    if not path.exists():
        cfg = AppConfig()
    else:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        # Env overrides (top-level only for simplicity)
        if "DATA_PROVIDER" in os.environ:
            data.setdefault("providers", {})["data_provider"] = os.environ["DATA_PROVIDER"]
        if "SENTIMENT_PROVIDER" in os.environ:
            data.setdefault("providers", {})["sentiment_provider"] = os.environ["SENTIMENT_PROVIDER"]
        if "CACHE_DIR" in os.environ:
            data["cache_dir"] = os.environ["CACHE_DIR"]
        if "API_PORT" in os.environ:
            data.setdefault("api", {})["port"] = int(os.environ["API_PORT"])
        try:
            cfg = AppConfig(**data)
        except ValidationError as e:
            raise ValueError(f"Invalid config: {e}") from e

    # Ensure cache_dir is absolute if relative
    if not Path(cfg.cache_dir).is_absolute():
        base = Path(__file__).resolve().parent.parent
        cfg.cache_dir = str(base / cfg.cache_dir)
    return cfg


_config: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """Cached config singleton."""
    global _config
    if _config is None or reload:
        _config = load_config()
    return _config
