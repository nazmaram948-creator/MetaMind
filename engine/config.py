"""Engine settings: engine/config.yaml, with a few environment overrides."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).with_name("config.yaml")
EXTRACTS = ROOT / "data" / "extracts"
CURATED = ROOT / "data" / "curated"


@lru_cache(maxsize=1)
def load_config() -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if os.environ.get("CURATED_VERSION"):
        cfg["curated_version"] = os.environ["CURATED_VERSION"]
    if os.environ.get("SIMILARITY_BACKEND"):
        cfg["parse"]["similarity_backend"] = os.environ["SIMILARITY_BACKEND"]
    if cfg["curated_version"] not in ("v1", "v2"):
        raise ValueError(f"curated_version must be v1 or v2, got {cfg['curated_version']!r}")
    return cfg


def db_path() -> Path:
    cfg = load_config()
    default = ROOT / "data" / f"skillshift_{cfg['curated_version']}.db"
    return Path(os.environ.get("SKILLSHIFT_DB", default))
