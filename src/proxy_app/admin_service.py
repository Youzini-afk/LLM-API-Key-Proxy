# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Tuple

from proxy_app.admin_schemas import (
    AdminConfig,
    ChannelConfig,
    ChannelCreateRequest,
    ChannelUpdateRequest,
    KeyCreateRequest,
    KeyUpdateRequest,
    RuntimeStatus,
    ValidationResult,
    VirtualModelAdminConfig,
)
from proxy_app.admin_store import (
    load_admin_config,
    save_admin_config,
    masked_config_dict,
    merge_masked_key_value,
)


class AdminService:
    def __init__(self):
        self._cfg = load_admin_config()
        self._last_reload_at = None

    # -----------------------
    # Basic getters
    # -----------------------
    def get_config(self) -> AdminConfig:
        self._cfg = load_admin_config()
        return self._cfg

    def get_config_masked(self) -> Dict:
        self._cfg = load_admin_config()
        return masked_config_dict(self._cfg)

    def list_channels(self) -> List[dict]:
        return self.get_config_masked().get("channels", [])

    def list_virtual_models(self) -> Dict[str, dict]:
        return self.get_config_masked().get("virtual_models", {})

    # -----------------------
    # Validation
    # -----------------------
    def validate_config(self, cfg: AdminConfig) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        # Channel ID uniqueness
        ids = [c.id for c in cfg.channels]
        if len(ids) != len(set(ids)):
            errors.append("Duplicate channel ids are not allowed")

        channel_ids = set(ids)

        # Channel minimal checks
        for ch in cfg.channels:
            if ch.enabled and not ch.api_keys:
                warnings.append(f"Enabled channel '{ch.id}' has no API keys")
            if ch.enabled and not ch.models:
                warnings.append(f"Enabled channel '{ch.id}' has empty models mapping")

        # Virtual model target checks
        for vm_name, vm in cfg.virtual_models.items():
            if vm.enabled:
                enabled_targets = [t for t in vm.targets if t.enabled]
                if not enabled_targets:
                    errors.append(f"Virtual model '{vm_name}' has no enabled targets")

                for t in vm.targets:
                    provider, _ = t.model.split("/", 1)
                    if provider not in channel_ids:
                        errors.append(
                            f"Virtual model '{vm_name}' references unknown channel '{provider}'"
                        )

        return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)

    # -----------------------
    # Channel CRUD
    # -----------------------
    def create_channel(self, req: ChannelCreateRequest) -> Dict:
        cfg = self.get_config()
        if any(c.id == req.id for c in cfg.channels):
            raise ValueError(f"Channel '{req.id}' already exists")
        cfg.channels.append(ChannelConfig(**req.model_dump()))
        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))
        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def update_channel(self, channel_id: str, req: ChannelUpdateRequest) -> Dict:
        cfg = self.get_config()
        target = next((c for c in cfg.channels if c.id == channel_id), None)
        if not target:
            raise ValueError(f"Channel '{channel_id}' not found")

        upd = req.model_dump(exclude_none=True)
        for k, v in upd.items():
            setattr(target, k, v)

        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))

        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def delete_channel(self, channel_id: str) -> Dict:
        cfg = self.get_config()
        before = len(cfg.channels)
        cfg.channels = [c for c in cfg.channels if c.id != channel_id]
        if len(cfg.channels) == before:
            raise ValueError(f"Channel '{channel_id}' not found")

        # remove virtual targets referencing this channel
        for _, vm in cfg.virtual_models.items():
            vm.targets = [t for t in vm.targets if not t.model.startswith(f"{channel_id}/")]

        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))

        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    # -----------------------
    # Key CRUD
    # -----------------------
    def add_key(self, channel_id: str, req: KeyCreateRequest) -> Dict:
        cfg = self.get_config()
        target = next((c for c in cfg.channels if c.id == channel_id), None)
        if not target:
            raise ValueError(f"Channel '{channel_id}' not found")
        if any(k.id == req.id for k in target.api_keys):
            raise ValueError(f"Key id '{req.id}' already exists in channel '{channel_id}'")

        target.api_keys.append(req)
        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def update_key(self, channel_id: str, key_id: str, req: KeyUpdateRequest) -> Dict:
        cfg = self.get_config()
        ch = next((c for c in cfg.channels if c.id == channel_id), None)
        if not ch:
            raise ValueError(f"Channel '{channel_id}' not found")
        key = next((k for k in ch.api_keys if k.id == key_id), None)
        if not key:
            raise ValueError(f"Key '{key_id}' not found in channel '{channel_id}'")

        upd = req.model_dump(exclude_none=True)
        if "value" in upd:
            key.value = merge_masked_key_value(key.value, upd["value"])
        if "enabled" in upd:
            key.enabled = upd["enabled"]

        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def delete_key(self, channel_id: str, key_id: str) -> Dict:
        cfg = self.get_config()
        ch = next((c for c in cfg.channels if c.id == channel_id), None)
        if not ch:
            raise ValueError(f"Channel '{channel_id}' not found")

        before = len(ch.api_keys)
        ch.api_keys = [k for k in ch.api_keys if k.id != key_id]
        if len(ch.api_keys) == before:
            raise ValueError(f"Key '{key_id}' not found in channel '{channel_id}'")

        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    # -----------------------
    # Virtual model CRUD
    # -----------------------
    def create_or_update_virtual_model(self, name: str, vm: VirtualModelAdminConfig) -> Dict:
        cfg = self.get_config()
        cfg.virtual_models[name] = vm

        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))

        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def delete_virtual_model(self, name: str) -> Dict:
        cfg = self.get_config()
        if name not in cfg.virtual_models:
            raise ValueError(f"Virtual model '{name}' not found")
        del cfg.virtual_models[name]
        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    # -----------------------
    # Runtime derivation/reload
    # -----------------------
    def build_runtime_env_overlay(self) -> Dict[str, str]:
        """
        Convert admin_config into env-like overlay, reusing existing startup logic.
        """
        cfg = self.get_config()
        env: Dict[str, str] = {}

        for ch in cfg.channels:
            prefix = ch.id.upper()
            env[f"{prefix}_API_BASE"] = ch.api_base

            # keys
            enabled_keys = [k for k in ch.api_keys if k.enabled]
            for idx, k in enumerate(enabled_keys, start=1):
                env[f"{prefix}_API_KEY_{idx}"] = k.value

            # models mapping
            if ch.models:
                import json
                env[f"{prefix}_MODELS"] = json.dumps(ch.models, ensure_ascii=False)

            # settings
            env[f"ROTATION_MODE_{prefix}"] = ch.settings.rotation_mode
            env[f"MAX_CONCURRENT_REQUESTS_PER_KEY_{prefix}"] = str(
                ch.settings.max_concurrent_requests_per_key
            )
            if ch.settings.ignore_models:
                env[f"IGNORE_MODELS_{prefix}"] = ",".join(ch.settings.ignore_models)
            if ch.settings.whitelist_models:
                env[f"WHITELIST_MODELS_{prefix}"] = ",".join(ch.settings.whitelist_models)

        # virtual models -> VIRTUAL_MODELS
        if cfg.virtual_models:
            import json
            env["VIRTUAL_MODELS"] = json.dumps(
                {
                    name: vm.model_dump()
                    for name, vm in cfg.virtual_models.items()
                },
                ensure_ascii=False,
            )

        if cfg.policies.global_timeout is not None:
            env["GLOBAL_TIMEOUT"] = str(cfg.policies.global_timeout)

        return env

    def apply_runtime_overlay(self) -> Dict:
        """
        MVP reload behavior:
        - apply derived env overlay to os.environ
        - reload virtual models registry immediately
        - return status (full RotatingClient live rebuild can be added later)
        """
        overlay = self.build_runtime_env_overlay()
        for k, v in overlay.items():
            os.environ[k] = v

        # reload virtual model registry
        from proxy_app.virtual_models import load_virtual_models
        vm = load_virtual_models()

        self._last_reload_at = datetime.utcnow().isoformat() + "Z"
        cfg = self.get_config()

        return {
            "ok": True,
            "message": "runtime overlay applied",
            "overlay_keys": sorted(list(overlay.keys())),
            "virtual_models_loaded": list(vm.keys()),
            "last_reload_at": self._last_reload_at,
            "config_version": cfg.metadata.version,
        }

    def get_runtime_status(self) -> RuntimeStatus:
        cfg = self.get_config()
        channels_enabled = sum(1 for c in cfg.channels if c.enabled)
        virtual_enabled = sum(1 for _, v in cfg.virtual_models.items() if v.enabled)
        return RuntimeStatus(
            loaded=True,
            config_version=cfg.metadata.version,
            updated_at=cfg.metadata.updated_at,
            channels_enabled=channels_enabled,
            virtual_models_enabled=virtual_enabled,
            last_reload_at=self._last_reload_at,
            message="ok",
        )


admin_service = AdminService()
