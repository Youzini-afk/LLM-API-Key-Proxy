# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


RouteStrategy = Literal["sequential", "primary_backup", "weighted_random"]
RotationMode = Literal["balanced", "sequential"]


class AdminMeta(BaseModel):
    version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))


class ChannelKeyConfig(BaseModel):
    id: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    enabled: bool = True


class ChannelSettingsConfig(BaseModel):
    rotation_mode: RotationMode = "balanced"
    max_concurrent_requests_per_key: int = Field(default=1, ge=1)
    ignore_models: List[str] = Field(default_factory=list)
    whitelist_models: List[str] = Field(default_factory=list)


class ChannelConfig(BaseModel):
    id: str = Field(..., min_length=1)
    provider_type: str = Field(default="openai_compatible", min_length=1)
    display_name: Optional[str] = None
    enabled: bool = True
    api_base: str = Field(..., min_length=1)
    api_keys: List[ChannelKeyConfig] = Field(default_factory=list)
    models: Dict[str, dict] = Field(default_factory=dict)
    settings: ChannelSettingsConfig = Field(default_factory=ChannelSettingsConfig)

    @field_validator("id")
    @classmethod
    def validate_channel_id(cls, v: str) -> str:
        s = v.strip().lower()
        if not s:
            raise ValueError("channel id cannot be empty")
        if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in s):
            raise ValueError("channel id must contain only a-z, 0-9, _")
        return s

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, v: str) -> str:
        s = v.strip()
        if not (s.startswith("http://") or s.startswith("https://")):
            raise ValueError("api_base must start with http:// or https://")
        return s.rstrip("/")


class VirtualTargetConfig(BaseModel):
    model: str = Field(..., min_length=3)
    enabled: bool = True
    weight: int = Field(default=100, ge=1)

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError("target model must be provider/model format")
        p, m = v.split("/", 1)
        if not p or not m:
            raise ValueError("target model must be provider/model format")
        return v


class VirtualModelAdminConfig(BaseModel):
    enabled: bool = True
    strategy: RouteStrategy = "sequential"
    targets: List[VirtualTargetConfig] = Field(default_factory=list)


class AdminPolicies(BaseModel):
    global_timeout: Optional[int] = Field(default=None, ge=1)


class AdminConfig(BaseModel):
    channels: List[ChannelConfig] = Field(default_factory=list)
    virtual_models: Dict[str, VirtualModelAdminConfig] = Field(default_factory=dict)
    policies: AdminPolicies = Field(default_factory=AdminPolicies)
    metadata: AdminMeta = Field(default_factory=AdminMeta)


class ValidationResult(BaseModel):
    ok: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RuntimeStatus(BaseModel):
    loaded: bool = True
    config_version: int = 1
    updated_at: Optional[str] = None
    channels_enabled: int = 0
    virtual_models_enabled: int = 0
    last_reload_at: Optional[str] = None
    message: str = "ok"


class ChannelCreateRequest(BaseModel):
    id: Optional[str] = None
    provider_type: str = Field(default="openai_compatible", min_length=1)
    display_name: Optional[str] = None
    enabled: bool = True
    api_base: str = Field(..., min_length=1)
    api_keys: List[ChannelKeyConfig] = Field(default_factory=list)
    models: Dict[str, dict] = Field(default_factory=dict)
    settings: ChannelSettingsConfig = Field(default_factory=ChannelSettingsConfig)




class ChannelUpdateRequest(BaseModel):
    provider_type: Optional[str] = None
    display_name: Optional[str] = None
    enabled: Optional[bool] = None
    api_base: Optional[str] = None
    models: Optional[Dict[str, dict]] = None
    settings: Optional[ChannelSettingsConfig] = None


class KeyCreateRequest(BaseModel):
    id: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    enabled: bool = True


class KeyUpdateRequest(BaseModel):
    value: Optional[str] = None
    enabled: Optional[bool] = None


class VirtualModelCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    config: VirtualModelAdminConfig


class VirtualModelUpdateRequest(VirtualModelAdminConfig):
    pass
