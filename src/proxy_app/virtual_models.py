# SPDX-License-Identifier: MIT
# Virtual Model Registry – loads VIRTUAL_MODELS env var, provides lookup.

import os
import logging
import re
from typing import Dict, List, Optional

from proxy_app.schemas_virtual import (
    VirtualModelConfig,
    RouteTarget,
    parse_virtual_models_config,
)

logger = logging.getLogger("proxy_app.virtual_models")

# ---------------------------------------------------------------------------
# Module-level singleton registry
# ---------------------------------------------------------------------------
_registry: Dict[str, VirtualModelConfig] = {}
_normalized_lookup: Dict[str, Optional[str]] = {}
_loaded: bool = False


def load_virtual_models() -> Dict[str, VirtualModelConfig]:
    """
    Load virtual model definitions from the VIRTUAL_MODELS environment variable.

    Can be called multiple times – will reload each time.
    Returns the loaded registry dict.
    """
    global _registry, _normalized_lookup, _loaded

    raw = os.getenv("VIRTUAL_MODELS", "").strip()
    if not raw:
        _registry = {}
        _normalized_lookup = {}
        _loaded = True
        logger.debug("No VIRTUAL_MODELS configured.")
        return _registry

    _registry = parse_virtual_models_config(raw)
    _normalized_lookup = _build_normalized_lookup(_registry)
    _loaded = True

    if _registry:
        names = ", ".join(_registry.keys())
        logger.info(
            f"Virtual model registry loaded: {len(_registry)} model(s) – {names}"
        )
    else:
        logger.warning("VIRTUAL_MODELS was set but no valid models were parsed.")

    return _registry


def is_virtual_model(model_name: str) -> bool:
    """
    Check whether *model_name* is a registered virtual model.

    Handles the case where the client sends just the bare name (e.g. "kimi2.5")
    as well as an explicit "virtual/kimi2.5" prefix (which we strip).
    """
    if not _loaded:
        load_virtual_models()
    name = _strip_virtual_prefix(model_name)
    if name in _registry:
        return True
    normalized_name = _normalize_lookup_name(name)
    mapped_name = _normalized_lookup.get(normalized_name)
    return bool(mapped_name and mapped_name in _registry)


def get_virtual_model(model_name: str) -> Optional[VirtualModelConfig]:
    """
    Return the VirtualModelConfig for *model_name*, or None.
    """
    if not _loaded:
        load_virtual_models()
    name = _strip_virtual_prefix(model_name)
    direct = _registry.get(name)
    if direct is not None:
        return direct

    normalized_name = _normalize_lookup_name(name)
    mapped_name = _normalized_lookup.get(normalized_name)
    if mapped_name:
        return _registry.get(mapped_name)
    return None


def get_all_virtual_model_names() -> List[str]:
    """
    Return a list of all registered virtual model names.
    """
    if not _loaded:
        load_virtual_models()
    return list(_registry.keys())


def get_registry() -> Dict[str, VirtualModelConfig]:
    """
    Return the full registry (read-only reference).
    """
    if not _loaded:
        load_virtual_models()
    return _registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _strip_virtual_prefix(model_name: str) -> str:
    """Strip an optional 'virtual/' prefix."""
    if model_name.startswith("virtual/"):
        return model_name[len("virtual/"):]
    return model_name


def _normalize_lookup_name(model_name: str) -> str:
    """
    Normalize model name for tolerant virtual-model lookup.

    Rules:
    - strip optional virtual/ prefix
    - remove leading [tag] prefixes (e.g. [喵喵] kimi-k2.5)
    - lowercase and remove common separators (- _ . space)
    """
    raw = _strip_virtual_prefix(model_name or "").strip().lower()
    if not raw:
        return ""

    raw = re.sub(r"^\[[^\]]+\]\s*", "", raw)
    raw = re.sub(r"[-_\.\s]+", "", raw)
    return raw


def _build_normalized_lookup(
    registry: Dict[str, VirtualModelConfig],
) -> Dict[str, Optional[str]]:
    """
    Build normalized-name -> canonical-name lookup.

    If multiple model names collapse to the same normalized key, mark it as
    ambiguous (None) so callers must use exact name.
    """
    normalized: Dict[str, Optional[str]] = {}
    for model_name in registry.keys():
        norm = _normalize_lookup_name(model_name)
        if not norm:
            continue
        existing = normalized.get(norm)
        if existing is None and norm in normalized:
            continue
        if existing and existing != model_name:
            normalized[norm] = None
        elif norm not in normalized:
            normalized[norm] = model_name
    return normalized
