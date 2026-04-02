# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Dict, Optional

from proxy_app.admin_schemas import AdminConfig


def get_default_root() -> Path:
    """Local lightweight root resolver to avoid heavy rotator imports."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path.cwd()


MASK = "********"

_LAST_LOAD_ERROR: Optional[str] = None
_LAST_CORRUPT_EVIDENCE_PATH: Optional[str] = None


def _set_store_health(error: Optional[str], evidence_path: Optional[str]) -> None:
    global _LAST_LOAD_ERROR, _LAST_CORRUPT_EVIDENCE_PATH
    _LAST_LOAD_ERROR = error
    _LAST_CORRUPT_EVIDENCE_PATH = evidence_path


def _capture_corrupt_evidence(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_path = path.with_name(f"{path.stem}.corrupt.{timestamp}{path.suffix}")
    try:
        shutil.copy2(path, evidence_path)
        return str(evidence_path)
    except Exception:
        return None


def _legacy_config_path() -> Path:
    """Backward-compatible legacy location: <root>/admin_config.json."""
    return get_default_root() / "admin_config.json"


def _config_path() -> Path:
    configured_path = (os.getenv("ADMIN_CONFIG_PATH") or "").strip()
    if configured_path:
        candidate = Path(configured_path).expanduser()
        if not candidate.is_absolute():
            candidate = (get_default_root() / candidate).resolve()
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    root = get_default_root()
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "admin_config.json"


def get_admin_store_health() -> Dict[str, Optional[str] | bool]:
    p = _config_path()
    return {
        "ok": _LAST_LOAD_ERROR is None,
        "error": _LAST_LOAD_ERROR,
        "config_path": str(p),
        "corrupt_evidence_path": _LAST_CORRUPT_EVIDENCE_PATH,
    }


def load_admin_config() -> AdminConfig:
    p = _config_path()
    # Backward-compatible migration: if admin_config is only present in the
    # old root location, copy it into the new default data path.
    if (
        not (os.getenv("ADMIN_CONFIG_PATH") or "").strip()
        and not p.exists()
        and str(p).endswith(str(Path("data") / "admin_config.json"))
    ):
        legacy = _legacy_config_path()
        if legacy.exists() and legacy.is_file():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy, p)
            except Exception:
                # If migration fails, continue with normal load logic.
                pass

    if not p.exists():
        _set_store_health(None, None)
        return AdminConfig()

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        evidence_path = _capture_corrupt_evidence(p)
        _set_store_health(
            f"admin_config.json is corrupted and cannot be parsed: {e}",
            evidence_path,
        )
        return AdminConfig()

    try:
        cfg = AdminConfig(**data)
    except Exception as e:
        evidence_path = _capture_corrupt_evidence(p)
        _set_store_health(
            f"admin_config.json is invalid and failed schema validation: {e}",
            evidence_path,
        )
        return AdminConfig()

    _set_store_health(None, None)
    return cfg


def save_admin_config(cfg: AdminConfig) -> AdminConfig:
    health = get_admin_store_health()
    if not health.get("ok"):
        raise RuntimeError(
            "admin_config.json is in corrupted read-only protection mode. "
            f"error={health.get('error')}; evidence={health.get('corrupt_evidence_path')}"
        )

    # bump metadata
    cfg.metadata.version = int(cfg.metadata.version) + 1
    cfg.metadata.updated_at = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    p = _config_path()
    tmp = p.with_suffix(".json.tmp")
    payload = cfg.model_dump()
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, p)
    _set_store_health(None, None)

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
