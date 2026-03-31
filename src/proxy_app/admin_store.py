# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict

from proxy_app.admin_schemas import AdminConfig


def get_default_root() -> Path:
    """Local lightweight root resolver to avoid heavy rotator imports."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path.cwd()


MASK = "********"


def _config_path() -> Path:
    root = get_default_root()
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "admin_config.json"


def load_admin_config() -> AdminConfig:
    p = _config_path()
    if not p.exists():
        return AdminConfig()

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return AdminConfig()

    return AdminConfig(**data)


def save_admin_config(cfg: AdminConfig) -> AdminConfig:
    # bump metadata
    cfg.metadata.version = int(cfg.metadata.version) + 1
    cfg.metadata.updated_at = datetime.utcnow().isoformat() + "Z"

    p = _config_path()
    tmp = p.with_suffix(".json.tmp")
    payload = cfg.model_dump()
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, p)

    return cfg


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return MASK
    return f"{value[:3]}...{value[-3:]}"


def masked_config_dict(cfg: AdminConfig) -> Dict:
    data = cfg.model_dump()
    channels = data.get("channels", [])
    for ch in channels:
        for key in ch.get("api_keys", []):
            key["value"] = mask_secret(key.get("value", ""))
    return data


def merge_masked_key_value(existing_real: str, incoming_value: str) -> str:
    """
    If incoming value looks masked, keep old real secret.
    Else use incoming new value.
    """
    if not incoming_value:
        return existing_real
    if "..." in incoming_value or incoming_value == MASK:
        return existing_real
    return incoming_value
