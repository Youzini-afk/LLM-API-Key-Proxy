# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (c) 2026 Mirrowel

from typing import Dict, Any, Optional

# Fields commonly injected by external relays but not part of OpenAI chat payload.
_RELAY_META_KEYS = frozenset(
    {
        "route",
        "route_name",
        "provider",
        "provider_name",
        "channel",
        "channel_id",
        "target",
        "target_model",
        "retry_count",
        "upstream",
    }
)

# Parameters that frequently break strict OpenAI-compatible upstreams.
_OPENAI_COMPAT_DROP_KEYS = frozenset({"reasoning", "reasoning_effort", "prediction"})


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def sanitize_request_payload(
    payload: Dict[str, Any],
    model: str,
    runtime_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Remove parameters that are known to cause cross-provider incompatibilities.
    """
    sanitized = dict(payload)
    runtime = (runtime_provider or "").strip().lower()

    # Strip relay metadata keys that should never be forwarded upstream.
    for key in _RELAY_META_KEYS:
        sanitized.pop(key, None)

    # Many OpenAI-compatible gateways reject explicit null/empty values.
    for key in list(sanitized.keys()):
        if _is_empty(sanitized.get(key)):
            sanitized.pop(key, None)

    if "dimensions" in sanitized and not model.startswith("openai/text-embedding-3"):
        sanitized.pop("dimensions", None)

    if sanitized.get("thinking") == {"type": "enabled", "budget_tokens": -1}:
        if model not in {"gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash"}:
            sanitized.pop("thinking", None)

    # If there are no tools, drop related fields to avoid provider validation errors.
    if not sanitized.get("tools"):
        sanitized.pop("tools", None)
        sanitized.pop("tool_choice", None)
        sanitized.pop("parallel_tool_calls", None)

    response_format = sanitized.get("response_format")
    if isinstance(response_format, dict):
        rf_type = str(response_format.get("type") or "").strip().lower()
        if not rf_type or rf_type == "text":
            sanitized.pop("response_format", None)

    if runtime in {"openai_compatible", "custom"}:
        for key in _OPENAI_COMPAT_DROP_KEYS:
            sanitized.pop(key, None)

    return sanitized
