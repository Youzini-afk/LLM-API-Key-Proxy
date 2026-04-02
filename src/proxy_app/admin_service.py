# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from proxy_app.admin_schemas import (
    AdminConfig,
    AdminPolicies,
    AdminPoliciesUpdateRequest,
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
    get_admin_store_health,
    load_admin_config,
    masked_config_dict,
    merge_masked_key_value,
    save_admin_config,
)


class AdminService:
    def __init__(self):
        self._cfg = load_admin_config()
        self._last_reload_at = None
        self._managed_runtime_env_keys: set[str] = set()

    @staticmethod
    def _current_store_health() -> Dict[str, object]:
        return get_admin_store_health()

    def _ensure_store_writable(self) -> None:
        health = self._current_store_health()
        if health.get("ok"):
            return
        raise ValueError(
            "admin_config.json 已进入损坏保护只读模式，已拒绝写入。"
            f" error={health.get('error')}; evidence={health.get('corrupt_evidence_path')}"
        )

    @staticmethod
    def _validate_api_base(raw_api_base: str) -> str:
        s = (raw_api_base or "").strip().rstrip("/")
        if not s:
            raise ValueError("api_base is required")
        if not (s.startswith("http://") or s.startswith("https://")):
            raise ValueError("api_base must start with http:// or https://")

        parsed = urlparse(s)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("api_base must be a valid absolute URL")
        return s

    @staticmethod
    def _normalize_api_base(raw_api_base: str) -> str:
        s = AdminService._validate_api_base(raw_api_base)

        parsed = urlparse(s)
        path = parsed.path or ""

        # 运行时仍需要标准 API base；如果用户粘贴了完整 endpoint，
        # 在真正写入 env overlay / 拉取 /models 时再派生为 provider base。
        if path.endswith("/chat/completions"):
            path = path[: -len("/chat/completions")]
        if path.endswith("/embeddings"):
            path = path[: -len("/embeddings")]
        if path.endswith("/responses"):
            path = path[: -len("/responses")]

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

    @staticmethod
    def _normalize_model_name_for_auto_virtual(model_name: str) -> str:
        """轻量归一化：忽略大小写与常见分隔符差异（-, _, ., 空格）。"""
        raw = (model_name or "").strip().lower()
        if not raw:
            return ""
        return re.sub(r"[-_\.\s]+", "", raw)

    @staticmethod
    def _pick_display_model_name(candidates: List[str]) -> str:
        """优先保留带分隔符的可读名称，其次按长度和字典序稳定选择。"""
        cleaned = [c for c in candidates if (c or "").strip()]
        if not cleaned:
            return ""
        with_separator = [c for c in cleaned if re.search(r"[-_\.]", c)]
        pool = with_separator or cleaned
        return sorted(pool, key=lambda x: (-len(x), x))[0]

    @staticmethod
    def _build_auto_virtual_models(cfg: AdminConfig) -> Dict[str, VirtualModelAdminConfig]:
        """
        自动聚合：
        1) 只要启用渠道里出现的模型，都暴露为公用模型（即使只有 1 个渠道）；
        2) 使用轻量归一化聚合同一模型（如 glm-5 / glm_5 / glm5）；
        3) 默认使用 balanced（均衡）策略。
        """
        normalized_buckets: Dict[str, Dict[str, object]] = {}

        for ch in cfg.channels:
            if not ch.enabled:
                continue
            effective_models = AdminService._build_effective_models(ch)
            for model_name in effective_models.keys():
                normalized = AdminService._normalize_model_name_for_auto_virtual(model_name)
                if not normalized:
                    continue
                bucket = normalized_buckets.setdefault(
                    normalized,
                    {
                        "names": set(),
                        "targets": [],
                    }
                )
                bucket["names"].add(model_name)
                bucket["targets"].append(f"{ch.id}/{model_name}")

        auto_vms: Dict[str, VirtualModelAdminConfig] = {}
        for _, bucket in normalized_buckets.items():
            names = sorted(list(bucket.get("names") or []))
            targets = sorted(set(bucket.get("targets") or []))
            if not targets:
                continue

            display_name = AdminService._pick_display_model_name(names)
            if not display_name:
                continue

            auto_vms[display_name] = VirtualModelAdminConfig(
                enabled=True,
                strategy="balanced",
                targets=[
                    {"model": t, "enabled": True, "weight": 100}
                    for t in targets
                ],
            )

        return auto_vms

    def _get_effective_virtual_models(self, cfg: AdminConfig) -> Dict[str, VirtualModelAdminConfig]:
        auto_vms = self._build_auto_virtual_models(cfg)
        # 手动配置优先：同名时覆盖自动生成结果
        auto_vms.update(cfg.virtual_models)
        return auto_vms

    # -----------------------
    # Basic getters
    # -----------------------
    def get_config(self) -> AdminConfig:
        self._cfg = load_admin_config()
        return self._cfg

    def get_config_masked(self) -> Dict:
        self._cfg = load_admin_config()
        data = masked_config_dict(self._cfg)
        data["_store_health"] = self._current_store_health()
        return data

    def get_policies(self) -> Dict:
        cfg = self.get_config()
        return cfg.policies.model_dump()

    def list_channels(self) -> List[dict]:
        return self.get_config_masked().get("channels", [])

    def list_virtual_models(self) -> Dict[str, dict]:
        cfg = self.get_config()
        effective_vms = self._get_effective_virtual_models(cfg)
        return {
            name: vm.model_dump()
            for name, vm in effective_vms.items()
        }

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
        enabled_channel_ids = {c.id for c in cfg.channels if c.enabled}

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
                    elif provider not in enabled_channel_ids:
                        errors.append(
                            f"Virtual model '{vm_name}' references disabled channel '{provider}'"
                        )

        return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)

    # -----------------------
    # Channel CRUD
    # -----------------------
    def create_channel(self, req: ChannelCreateRequest) -> Dict:
        self._ensure_store_writable()
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
        payload["api_base"] = self._validate_api_base(payload.get("api_base") or "")

        cfg.channels.append(ChannelConfig(**payload))
        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))
        self._cfg = save_admin_config(cfg)
        out = self.get_config_masked()
        out["created_channel_id"] = channel_id
        return out

    def update_channel(self, channel_id: str, req: ChannelUpdateRequest) -> Dict:
        self._ensure_store_writable()
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
            upd["api_base"] = self._validate_api_base(upd["api_base"])

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
        self._ensure_store_writable()
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

    @staticmethod
    def _generate_next_key_id(existing_keys: List[ChannelKeyConfig]) -> str:
        existing_ids = {((k.id or "").strip()) for k in (existing_keys or [])}
        idx = 1
        while True:
            candidate = f"key_{idx}"
            if candidate not in existing_ids:
                return candidate
            idx += 1

    # -----------------------
    # Key CRUD
    # -----------------------
    def add_key(self, channel_id: str, req: KeyCreateRequest) -> Dict:
        self._ensure_store_writable()
        cfg = self.get_config()
        target = next((c for c in cfg.channels if c.id == channel_id), None)
        if not target:
            raise ValueError(f"Channel '{channel_id}' not found")

        req_id = (req.id or "").strip()
        if not req_id:
            req_id = self._generate_next_key_id(target.api_keys)

        if any(k.id == req_id for k in target.api_keys):
            raise ValueError(f"Key id '{req_id}' already exists in channel '{channel_id}'")

        target.api_keys.append(
            ChannelKeyConfig(
                id=req_id,
                value=req.value,
                enabled=req.enabled,
            )
        )
        target.api_keys = self._dedupe_channel_keys(target.api_keys)
        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def update_key(self, channel_id: str, key_id: str, req: KeyUpdateRequest) -> Dict:
        self._ensure_store_writable()
        cfg = self.get_config()
        ch = next((c for c in cfg.channels if c.id == channel_id), None)
        if not ch:
            raise ValueError(f"Channel '{channel_id}' not found")
        key = next((k for k in ch.api_keys if k.id == key_id), None)
        if not key:
            raise ValueError(f"Key '{key_id}' not found in channel '{channel_id}'")

        upd = req.model_dump(exclude_none=True)
        next_key_id = key_id
        if "id" in upd:
            requested_id = (upd.pop("id") or "").strip()
            if not requested_id:
                raise ValueError("Key id cannot be empty")
            if requested_id != key_id:
                if any(k.id == requested_id for k in ch.api_keys):
                    raise ValueError(
                        f"Key id '{requested_id}' already exists in channel '{channel_id}'"
                    )
                next_key_id = requested_id

        key.id = next_key_id
        if "value" in upd:
            key.value = merge_masked_key_value(key.value, upd["value"])
        if "enabled" in upd:
            key.enabled = upd["enabled"]

        ch.api_keys = self._dedupe_channel_keys(ch.api_keys)

        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def delete_key(self, channel_id: str, key_id: str) -> Dict:
        self._ensure_store_writable()
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
        self._ensure_store_writable()
        cfg = self.get_config()
        cfg.virtual_models[name] = vm

        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))

        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def delete_virtual_model(self, name: str) -> Dict:
        self._ensure_store_writable()
        cfg = self.get_config()
        if name not in cfg.virtual_models:
            raise ValueError(f"Virtual model '{name}' not found")
        del cfg.virtual_models[name]
        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    def update_policies(self, req: AdminPoliciesUpdateRequest) -> Dict:
        self._ensure_store_writable()
        cfg = self.get_config()
        cfg.policies = AdminPolicies(**req.model_dump())
        result = self.validate_config(cfg)
        if not result.ok:
            raise ValueError("; ".join(result.errors))
        self._cfg = save_admin_config(cfg)
        return self.get_config_masked()

    # -----------------------
    # Runtime derivation/reload
    # -----------------------
    def get_channel(self, channel_id: str) -> Optional[ChannelConfig]:
        cfg = self.get_config()
        return next((c for c in cfg.channels if c.id == channel_id), None)

    @staticmethod
    def _build_channel_overlay(ch: ChannelConfig) -> Dict[str, str]:
        import json

        env: Dict[str, str] = {}
        prefix = ch.id.upper()
        env[f"{prefix}_API_BASE"] = AdminService._normalize_api_base(ch.api_base)
        env[f"PROVIDER_TYPE_{prefix}"] = (ch.provider_type or "openai_compatible").strip().lower()

        enabled_keys = [k for k in AdminService._dedupe_channel_keys(ch.api_keys) if k.enabled]
        for idx, key in enumerate(enabled_keys, start=1):
            env[f"{prefix}_API_KEY_{idx}"] = key.value
            env[f"{prefix}_API_KEY_ID_{idx}"] = key.id

        effective_models = AdminService._build_effective_models(ch)
        if effective_models:
            env[f"{prefix}_MODELS"] = json.dumps(effective_models, ensure_ascii=False)

        env[f"ROTATION_MODE_{prefix}"] = ch.settings.rotation_mode
        env[f"MAX_CONCURRENT_REQUESTS_PER_KEY_{prefix}"] = str(
            ch.settings.max_concurrent_requests_per_key
        )
        env[f"AUTO_DISABLE_LONG_UNAVAILABLE_{prefix}"] = (
            "true" if ch.settings.auto_disable_long_unavailable else "false"
        )
        env[f"AUTO_DISABLE_UNAVAILABLE_HOURS_{prefix}"] = str(
            ch.settings.auto_disable_unavailable_hours
        )
        if ch.settings.ignore_models:
            env[f"IGNORE_MODELS_{prefix}"] = ",".join(ch.settings.ignore_models)
        if ch.settings.whitelist_models:
            env[f"WHITELIST_MODELS_{prefix}"] = ",".join(ch.settings.whitelist_models)

        return env

    def build_runtime_env_overlay(self) -> Dict[str, str]:
        """
        Convert admin_config into env-like overlay, reusing existing startup logic.

        Full-sync semantics:
        - only enabled channels are emitted
        - deleted/renamed/disabled channels are cleaned in apply_runtime_overlay()
        """
        cfg = self.get_config()
        env: Dict[str, str] = {}

        for ch in cfg.channels:
            if not ch.enabled:
                continue
            env.update(self._build_channel_overlay(ch))

        # virtual models -> VIRTUAL_MODELS (only enabled virtual models)
        effective_vms = self._get_effective_virtual_models(cfg)
        if effective_vms:
            import json

            enabled_vms = {
                name: vm.model_dump()
                for name, vm in effective_vms.items()
                if vm.enabled
            }
            if enabled_vms:
                env["VIRTUAL_MODELS"] = json.dumps(enabled_vms, ensure_ascii=False)

        if cfg.policies.global_timeout is not None:
            env["GLOBAL_TIMEOUT"] = str(cfg.policies.global_timeout)
        env["MAX_RETRIES"] = str(cfg.policies.same_key_max_retries)
        env["VIRTUAL_SCHEDULER_MODE"] = cfg.policies.virtual_scheduler_mode
        env["KEY_BUSY_WAIT_INTERVAL_SECONDS"] = str(
            cfg.policies.key_busy_wait_interval_seconds
        )
        env["KEY_BUSY_WAIT_MAX_ATTEMPTS"] = str(
            cfg.policies.key_busy_wait_max_attempts
        )
        env["SCARCITY_PROBE_BUDGET_RATIO"] = str(
            cfg.policies.scarcity_probe_budget_ratio
        )
        env["SCARCITY_PROBE_BURST"] = str(cfg.policies.scarcity_probe_burst)

        return env

    def apply_runtime_overlay(self) -> Dict:
        """
        MVP reload behavior:
        - apply derived env overlay to os.environ
        - reload virtual models registry immediately
        - return status (full RotatingClient live rebuild can be added later)
        """
        self._ensure_store_writable()
        overlay = self.build_runtime_env_overlay()
        next_keys = set(overlay.keys())

        stale_keys = sorted(self._managed_runtime_env_keys - next_keys)
        for key in stale_keys:
            os.environ.pop(key, None)

        for k, v in overlay.items():
            os.environ[k] = v
        self._managed_runtime_env_keys = next_keys

        # reload virtual model registry
        from proxy_app.virtual_models import load_virtual_models
        vm = load_virtual_models()

        self._last_reload_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        cfg = self.get_config()

        return {
            "ok": True,
            "message": "runtime overlay applied",
            "overlay_keys": sorted(list(overlay.keys())),
            "removed_stale_keys": stale_keys,
            "virtual_models_loaded": list(vm.keys()),
            "last_reload_at": self._last_reload_at,
            "config_version": cfg.metadata.version,
        }

    def get_runtime_status(self) -> RuntimeStatus:
        cfg = self.get_config()
        health = self._current_store_health()
        channels_enabled = sum(1 for c in cfg.channels if c.enabled)
        effective_vms = self._get_effective_virtual_models(cfg)
        virtual_enabled = sum(1 for _, v in effective_vms.items() if v.enabled)
        return RuntimeStatus(
            loaded=bool(health.get("ok")),
            config_version=cfg.metadata.version,
            updated_at=cfg.metadata.updated_at,
            channels_enabled=channels_enabled,
            virtual_models_enabled=virtual_enabled,
            last_reload_at=self._last_reload_at,
            message="ok" if health.get("ok") else "admin_config_corrupted_readonly",
        )


admin_service = AdminService()
