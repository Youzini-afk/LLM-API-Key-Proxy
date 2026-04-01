# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from proxy_app.admin_schemas import (
    AdminConfig,
    ChannelConfig,
    ChannelKeyConfig,
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

    @staticmethod
    def _normalize_api_base(raw_api_base: str) -> str:
        s = (raw_api_base or "").strip().rstrip("/")
        if not s:
            raise ValueError("api_base is required")
        if not (s.startswith("http://") or s.startswith("https://")):
            raise ValueError("api_base must start with http:// or https://")

        parsed = urlparse(s)
        path = parsed.path or ""
        # If user pasted full completions endpoint, normalize to provider base
        if path.endswith("/chat/completions"):
            path = path[: -len("/chat/completions")]
        if path.endswith("/embeddings"):
            path = path[: -len("/embeddings")]

        normalized = f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")
        return normalized

    @staticmethod
    def _sanitize_channel_id(v: str) -> str:
        s = (v or "").strip().lower()
        # 仅允许 ASCII: a-z, 0-9, _
        # 注意: Python 的 str.isalnum() 对中文也会返回 True，这会导致后续 schema 校验失败。
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789_"
        s = "".join(ch if ch in allowed else "_" for ch in s)
        while "__" in s:
            s = s.replace("__", "_")
        return s.strip("_")

    def _generate_channel_id(self, req: ChannelCreateRequest, cfg: AdminConfig) -> str:
        base = self._sanitize_channel_id(req.display_name or req.provider_type or "channel") or self._sanitize_channel_id(req.provider_type or "") or "channel"
        existing = {c.id for c in cfg.channels}
        if base not in existing:
            return base
        idx = 2
        while f"{base}_{idx}" in existing:
            idx += 1
        return f"{base}_{idx}"

    @staticmethod
    def _dedupe_channel_keys(keys: List[ChannelKeyConfig]) -> List[ChannelKeyConfig]:
        deduped: List[ChannelKeyConfig] = []
        seen_ids = set()
        value_index: Dict[str, int] = {}

        for item in keys or []:
            if isinstance(item, ChannelKeyConfig):
                key = item
            else:
                payload = item.model_dump() if hasattr(item, "model_dump") else item
                key = ChannelKeyConfig(**payload)
            key_id = (key.id or "").strip()
            key_value = (key.value or "").strip()

            if not key_id or not key_value:
                continue

            if key_id in seen_ids:
                raise ValueError(f"Duplicate key id '{key_id}' is not allowed in the same channel")

            if key_value in value_index:
                existing_idx = value_index[key_value]
                existing = deduped[existing_idx]
                deduped[existing_idx] = existing.model_copy(
                    update={"enabled": existing.enabled or key.enabled}
                )
                continue

            normalized = key.model_copy(update={"id": key_id, "value": key_value})
            seen_ids.add(key_id)
            value_index[key_value] = len(deduped)
            deduped.append(normalized)

        return deduped

    @staticmethod
    def _build_effective_models(channel: ChannelConfig) -> Dict[str, dict]:
        effective: Dict[str, dict] = {}

        for model_name in channel.provided_models or []:
            if model_name:
                effective[model_name] = {"id": model_name}

        for alias, cfg in (channel.models or {}).items():
            alias_name = (alias or "").strip()
            if not alias_name:
                continue
            if isinstance(cfg, str):
                effective[alias_name] = {"id": cfg}
                continue
            data = dict(cfg or {})
            data["id"] = (data.get("id") or alias_name).strip()
            effective[alias_name] = data

        return effective

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
            effective_models = self._build_effective_models(ch)
            if ch.enabled and not effective_models:
                warnings.append(f"Enabled channel '{ch.id}' has no provided models or mappings")

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
        channel_id = self._sanitize_channel_id(req.id or "")
        if not channel_id:
            channel_id = self._generate_channel_id(req, cfg)
        if any(c.id == channel_id for c in cfg.channels):
            raise ValueError(f"Channel '{channel_id}' already exists")

        payload = req.model_dump()
        payload["id"] = channel_id
        payload["api_keys"] = [
            key.model_dump() for key in self._dedupe_channel_keys(req.api_keys)
        ]
        payload["api_base"] = self._normalize_api_base(payload.get("api_base") or "")

        cfg.channels.append(ChannelConfig(**payload))
        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))
        self._cfg = save_admin_config(cfg)
        out = self.get_config_masked()
        out["created_channel_id"] = channel_id
        return out

    def update_channel(self, channel_id: str, req: ChannelUpdateRequest) -> Dict:
        cfg = self.get_config()
        target_idx = next((idx for idx, c in enumerate(cfg.channels) if c.id == channel_id), None)
        target = cfg.channels[target_idx] if target_idx is not None else None
        if not target:
            raise ValueError(f"Channel '{channel_id}' not found")

        upd = req.model_dump(exclude_none=True)
        next_channel_id = channel_id

        if "id" in upd:
            requested_id = self._sanitize_channel_id(upd.pop("id") or "")
            if requested_id and requested_id != channel_id:
                if any(c.id == requested_id and c.id != channel_id for c in cfg.channels):
                    raise ValueError(f"Channel '{requested_id}' already exists")
                next_channel_id = requested_id

        if "api_base" in upd:
            upd["api_base"] = self._normalize_api_base(upd["api_base"])

        updated_payload = target.model_dump()
        updated_payload.update(upd)
        updated_payload["id"] = next_channel_id
        updated_channel = ChannelConfig(**updated_payload)

        if next_channel_id != channel_id:
            for _, vm in cfg.virtual_models.items():
                new_targets = []
                for t in vm.targets:
                    if t.model.startswith(f"{channel_id}/"):
                        _, model_name = t.model.split("/", 1)
                        t = t.model_copy(update={"model": f"{next_channel_id}/{model_name}"})
                    new_targets.append(t)
                vm.targets = new_targets

        cfg.channels[target_idx] = updated_channel

        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))

        self._cfg = save_admin_config(cfg)
        out = self.get_config_masked()
        out["updated_channel_id"] = next_channel_id
        return out

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
        target.api_keys = self._dedupe_channel_keys(target.api_keys)
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

        ch.api_keys = self._dedupe_channel_keys(ch.api_keys)

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
            enabled_keys = [k for k in self._dedupe_channel_keys(ch.api_keys) if k.enabled]
            for idx, k in enumerate(enabled_keys, start=1):
                env[f"{prefix}_API_KEY_{idx}"] = k.value

            # effective models mapping = provided models(identity) + alias mappings
            effective_models = self._build_effective_models(ch)
            if effective_models:
                import json
                env[f"{prefix}_MODELS"] = json.dumps(effective_models, ensure_ascii=False)

            # settings
            env[f"ROTATION_MODE_{prefix}"] = ch.settings.rotation_mode
            env[f"MAX_CONCURRENT_REQUESTS_PER_KEY_{prefix}"] = str(
                ch.settings.max_concurrent_requests_per_key
            )
            env[f"AUTO_DISABLE_LONG_UNAVAILABLE_{prefix}"] = (
                "true" if ch.settings.auto_disable_long_unavailable else "false"
            )
            env[f"AUTO_DISABLE_UNAVAILABLE_HOURS_{prefix}"] = str(ch.settings.auto_disable_unavailable_hours)
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

        self._last_reload_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
