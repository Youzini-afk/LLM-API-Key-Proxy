# SPDX-License-Identifier: MIT
# Virtual Model Registry – loads VIRTUAL_MODELS env var, provides lookup.

import os
import logging
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
_loaded: bool = False


def load_virtual_models() -> Dict[str, VirtualModelConfig]:
    """
    Load virtual model definitions from the VIRTUAL_MODELS environment variable.

    Can be called multiple times – will reload each time.
    Returns the loaded registry dict.
    """
    global _registry, _loaded

    raw = os.getenv("VIRTUAL_MODELS", "").strip()
    if not raw:
        _registry = {}
        _loaded = True
        logger.debug("No VIRTUAL_MODELS configured.")
        return _registry

    _registry = parse_virtual_models_config(raw)
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
    return name in _registry


def get_virtual_model(model_name: str) -> Optional[VirtualModelConfig]:
    """
    Return the VirtualModelConfig for *model_name*, or None.
    """
    if not _loaded:
        load_virtual_models()
    name = _strip_virtual_prefix(model_name)
    return _registry.get(name)


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
