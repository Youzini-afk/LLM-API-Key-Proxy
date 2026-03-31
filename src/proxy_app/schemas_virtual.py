# SPDX-License-Identifier: MIT
# Virtual Model Aggregation - Configuration Schemas

import json
import logging
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger("proxy_app.virtual_models")

# ---------------------------------------------------------------------------
# Allowed strategies
# ---------------------------------------------------------------------------
ALLOWED_STRATEGIES = ("sequential", "primary_backup", "weighted_random")


# ---------------------------------------------------------------------------
# Route Target – one candidate backend for a virtual model
# ---------------------------------------------------------------------------
class RouteTarget(BaseModel):
    """A single candidate backend target for a virtual model."""

    model: str = Field(
        ...,
        description="Target in 'provider/model' format, e.g. 'dashscope_a/kimi2.5'",
    )
    weight: int = Field(default=100, ge=1, description="Weight for weighted_random strategy")
    enabled: bool = Field(default=True, description="Whether this target is active")

    @field_validator("model")
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError(
                f"Target model must be in 'provider/model' format, got '{v}'"
            )
        provider, model_name = v.split("/", 1)
        if not provider or not model_name:
            raise ValueError(
                f"Both provider and model name must be non-empty in '{v}'"
            )
        return v

    @property
    def provider(self) -> str:
        return self.model.split("/", 1)[0]

    @property
    def model_name(self) -> str:
        return self.model.split("/", 1)[1]


# ---------------------------------------------------------------------------
# Virtual Model – one logical model with its routing config
# ---------------------------------------------------------------------------
class VirtualModelConfig(BaseModel):
    """Configuration for a single virtual (logical) model."""

    enabled: bool = Field(default=True, description="Whether this virtual model is active")
    strategy: str = Field(
        default="sequential",
        description="Routing strategy: sequential, primary_backup, weighted_random",
    )
    timeout_seconds: int = Field(
        default=90, ge=1, description="Per-target timeout budget in seconds"
    )
    max_target_attempts: Optional[int] = Field(
        default=None,
        description="Max targets to try before giving up (None = try all)",
    )
    targets: List[RouteTarget] = Field(
        ..., min_length=1, description="Ordered list of candidate targets"
    )

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        if v not in ALLOWED_STRATEGIES:
            raise ValueError(
                f"strategy must be one of {ALLOWED_STRATEGIES}, got '{v}'"
            )
        return v

    @property
    def enabled_targets(self) -> List[RouteTarget]:
        """Return only enabled targets."""
        return [t for t in self.targets if t.enabled]


# ---------------------------------------------------------------------------
# Parsing helpers – normalise flexible JSON input into typed config
# ---------------------------------------------------------------------------
def _parse_target(raw: Any) -> RouteTarget:
    """
    Parse a target from either a string or dict.

    Accepts:
      - "provider/model"  (string shorthand)
      - {"model": "provider/model", "weight": 100, "enabled": true}
    """
    if isinstance(raw, str):
        return RouteTarget(model=raw)
    if isinstance(raw, dict):
        return RouteTarget(**raw)
    raise ValueError(f"Target must be a string or dict, got {type(raw).__name__}")


def parse_virtual_models_config(
    raw_json: str,
) -> Dict[str, VirtualModelConfig]:
    """
    Parse the VIRTUAL_MODELS environment variable JSON into typed config.

    Accepts two target formats:
      Simple:  {"kimi2.5": {"targets": ["prov_a/kimi2.5", "prov_b/kimi2.5"]}}
      Full:    {"kimi2.5": {"targets": [{"model": "prov_a/kimi2.5", "weight": 100}]}}

    Returns:
        Dict mapping virtual model name -> VirtualModelConfig
    """
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.error(f"VIRTUAL_MODELS is not valid JSON: {e}")
        return {}

    if not isinstance(raw, dict):
        logger.error(
            f"VIRTUAL_MODELS must be a JSON object, got {type(raw).__name__}"
        )
        return {}

    result: Dict[str, VirtualModelConfig] = {}

    for vmodel_name, vmodel_raw in raw.items():
        try:
            if not isinstance(vmodel_raw, dict):
                logger.warning(
                    f"Virtual model '{vmodel_name}' config must be a dict, skipping"
                )
                continue

            # Parse targets – accept both string and dict formats
            raw_targets = vmodel_raw.get("targets", [])
            if not raw_targets:
                logger.warning(
                    f"Virtual model '{vmodel_name}' has no targets, skipping"
                )
                continue

            parsed_targets = []
            for i, t in enumerate(raw_targets):
                try:
                    parsed_targets.append(_parse_target(t))
                except Exception as te:
                    logger.warning(
                        f"Virtual model '{vmodel_name}' target #{i} invalid: {te}, skipping target"
                    )

            if not parsed_targets:
                logger.warning(
                    f"Virtual model '{vmodel_name}' has no valid targets after parsing, skipping"
                )
                continue

            config_dict = {**vmodel_raw, "targets": parsed_targets}
            config = VirtualModelConfig(**config_dict)
            result[vmodel_name] = config

            enabled_count = len(config.enabled_targets)
            logger.info(
                f"Loaded virtual model '{vmodel_name}': "
                f"strategy={config.strategy}, "
                f"targets={len(config.targets)} ({enabled_count} enabled)"
            )

        except Exception as e:
            logger.warning(
                f"Failed to parse virtual model '{vmodel_name}': {e}, skipping"
            )

    return result
