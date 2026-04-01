import importlib



def _reload_modules(monkeypatch, tmp_path):
    import proxy_app.admin_store as admin_store

    monkeypatch.setattr(admin_store, "get_default_root", lambda: tmp_path)
    importlib.reload(admin_store)
    monkeypatch.setattr(admin_store, "get_default_root", lambda: tmp_path)

    import proxy_app.admin_service as admin_service
    importlib.reload(admin_service)
    return admin_store, admin_service


def test_admin_store_save_load_mask(monkeypatch, tmp_path):
    admin_store, _ = _reload_modules(monkeypatch, tmp_path)
    from proxy_app.admin_schemas import AdminConfig, ChannelConfig, ChannelKeyConfig

    cfg = AdminConfig(
        channels=[
            ChannelConfig(
                id="dashscope_a",
                api_base="https://example.com/v1",
                api_keys=[ChannelKeyConfig(id="k1", value="sk-1234567890")],
                models={"kimi2.5": {"id": "kimi-k2"}},
            )
        ]
    )

    admin_store.save_admin_config(cfg)
    loaded = admin_store.load_admin_config()
    assert loaded.channels[0].id == "dashscope_a"

    masked = admin_store.masked_config_dict(loaded)
    assert masked["channels"][0]["api_keys"][0]["value"] != "sk-1234567890"
    assert "..." in masked["channels"][0]["api_keys"][0]["value"]


def test_admin_service_auto_channel_id_and_runtime_api_base_normalize(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    # id 留空自动生成
    out = service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id=None,
            display_name="Infini Coding",
            api_base="https://cloud.infini-ai.com/maas/coding/v1/chat/completions",
            provider_type="openai_compatible",
            models={"kimi2.5": {"id": "kimi-k2.5"}},
            api_keys=[],
        )
    )
    created_id = out.get("created_channel_id")
    assert created_id == "infini_coding"

    cfg = service.get_config()
    ch = next((c for c in cfg.channels if c.id == created_id), None)
    assert ch is not None
    # 管理配置中保留用户填入的完整 URL，避免编辑时被“裁掉”
    assert ch.api_base == "https://cloud.infini-ai.com/maas/coding/v1/chat/completions"

    overlay = service.build_runtime_env_overlay()
    assert overlay["INFINI_CODING_API_BASE"] == "https://cloud.infini-ai.com/maas/coding/v1"

    # 再创建一个同名 display_name，自动加后缀
    out2 = service.create_channel(
        admin_service_mod.ChannelCreateRequest(api_base="https://x.y/v1", display_name="Infini Coding")
    )
    assert out2.get("created_channel_id") == "infini_coding_2"


def test_admin_service_auto_channel_id_with_non_ascii_name(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    # 非 ASCII 显示名会被清洗为空，应该回退到 provider_type 生成合法 id
    out = service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id=None,
            display_name="无问",
            provider_type="openai_compatible",
            api_base="https://example.com/v1",
        )
    )
    assert out.get("created_channel_id") == "openai_compatible"


def test_admin_service_channel_virtual_crud(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="dashscope_a",
            api_base="https://example.com/v1",
            provider_type="openai_compatible",
            models={"kimi2.5": {"id": "kimi-k2"}},
            api_keys=[],
        )
    )
    channels = service.list_channels()
    assert len(channels) == 1
    assert channels[0]["id"] == "dashscope_a"

    service.add_key("dashscope_a", admin_service_mod.KeyCreateRequest(id="k1", value="abc123"))
    channels = service.list_channels()
    assert len(channels[0]["api_keys"]) == 1

    from proxy_app.admin_schemas import VirtualModelAdminConfig, VirtualTargetConfig

    vm = VirtualModelAdminConfig(
        enabled=True,
        strategy="sequential",
        targets=[VirtualTargetConfig(model="dashscope_a/kimi2.5")],
    )
    service.create_or_update_virtual_model("kimi2.5", vm)

    vms = service.list_virtual_models()
    assert "kimi2.5" in vms


def test_admin_service_runtime_overlay(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    from proxy_app.admin_schemas import ChannelKeyConfig, ChannelSettingsConfig

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="dashscope_a",
            api_base="https://example.com/v1",
            provider_type="openai_compatible",
            settings=ChannelSettingsConfig(
                rotation_mode="balanced",
                max_concurrent_requests_per_key=1,
                auto_disable_long_unavailable=True,
                auto_disable_unavailable_hours=12,
            ),
            models={"kimi2.5": {"id": "kimi-k2"}},
            api_keys=[ChannelKeyConfig(id="k1", value="abc123")],
        )
    )

    overlay = service.build_runtime_env_overlay()
    assert overlay["DASHSCOPE_A_API_BASE"] == "https://example.com/v1"
    assert overlay["DASHSCOPE_A_API_KEY_1"] == "abc123"
    assert "DASHSCOPE_A_MODELS" in overlay
    assert '"kimi2.5": {"id": "kimi-k2"}' in overlay["DASHSCOPE_A_MODELS"]
    assert overlay["AUTO_DISABLE_LONG_UNAVAILABLE_DASHSCOPE_A"] == "true"
    assert overlay["AUTO_DISABLE_UNAVAILABLE_HOURS_DASHSCOPE_A"] == "12"


def test_admin_service_update_channel_id_and_custom_provider(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="dashscope_a",
            api_base="https://example.com/v1",
            provider_type="openai_compatible",
            models={"kimi2.5": {"id": "kimi-k2"}},
            api_keys=[],
        )
    )

    from proxy_app.admin_schemas import VirtualModelAdminConfig, VirtualTargetConfig

    service.create_or_update_virtual_model(
        "kimi2.5",
        VirtualModelAdminConfig(
            enabled=True,
            strategy="sequential",
            targets=[VirtualTargetConfig(model="dashscope_a/kimi2.5")],
        ),
    )

    out = service.update_channel(
        "dashscope_a",
        admin_service_mod.ChannelUpdateRequest(
            id="infini_custom_a",
            provider_type="infini_custom",
            display_name="安安干饭",
        ),
    )

    assert out.get("updated_channel_id") == "infini_custom_a"

    cfg = service.get_config()
    channel = next((c for c in cfg.channels if c.id == "infini_custom_a"), None)
    assert channel is not None
    assert channel.provider_type == "infini_custom"
    assert channel.display_name == "安安干饭"
    assert cfg.virtual_models["kimi2.5"].targets[0].model == "infini_custom_a/kimi2.5"


def test_admin_service_provided_models_are_separate_from_alias_mapping(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    from proxy_app.admin_schemas import ChannelKeyConfig

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="custom_a",
            api_base="https://example.com/v1",
            provider_type="custom",
            provided_models=["glm-5", "kimi-k2.5"],
            models={"[喵喵] glm-5": {"id": "glm-5"}},
            api_keys=[ChannelKeyConfig(id="k1", value="abc123")],
        )
    )

    cfg = service.get_config()
    ch = next(c for c in cfg.channels if c.id == "custom_a")
    assert ch.provided_models == ["glm-5", "kimi-k2.5"]
    assert ch.models == {"[喵喵] glm-5": {"id": "glm-5"}}

    overlay = service.build_runtime_env_overlay()
    assert '"glm-5": {"id": "glm-5"}' in overlay["CUSTOM_A_MODELS"]
    assert '"kimi-k2.5": {"id": "kimi-k2.5"}' in overlay["CUSTOM_A_MODELS"]
    assert '"[喵喵] glm-5": {"id": "glm-5"}' in overlay["CUSTOM_A_MODELS"]


def test_admin_service_auto_dedup_channel_key_pool_by_value(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    from proxy_app.admin_schemas import ChannelKeyConfig

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="custom_a",
            api_base="https://example.com/v1",
            provider_type="custom",
            provided_models=["glm-5"],
            api_keys=[
                ChannelKeyConfig(id="k1", value=" sk-dup ", enabled=False),
                ChannelKeyConfig(id="k2", value="sk-dup", enabled=True),
                ChannelKeyConfig(id="k3", value="sk-unique", enabled=True),
            ],
        )
    )

    cfg = service.get_config()
    ch = next(c for c in cfg.channels if c.id == "custom_a")
    assert len(ch.api_keys) == 2
    assert ch.api_keys[0].id == "k1"
    assert ch.api_keys[0].value == "sk-dup"
    assert ch.api_keys[0].enabled is True
    assert ch.api_keys[1].id == "k3"

    overlay = service.build_runtime_env_overlay()
    assert overlay["CUSTOM_A_API_KEY_1"] == "sk-dup"
    assert overlay["CUSTOM_A_API_KEY_2"] == "sk-unique"


def test_admin_service_add_key_auto_dedup_by_value(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="custom_a",
            api_base="https://example.com/v1",
            provider_type="custom",
            provided_models=["glm-5"],
        )
    )
    service.add_key("custom_a", admin_service_mod.KeyCreateRequest(id="k1", value="sk-dup", enabled=False))
    service.add_key("custom_a", admin_service_mod.KeyCreateRequest(id="k2", value=" sk-dup ", enabled=True))

    cfg = service.get_config()
    ch = next(c for c in cfg.channels if c.id == "custom_a")
    assert len(ch.api_keys) == 1
    assert ch.api_keys[0].id == "k1"
    assert ch.api_keys[0].enabled is True


def test_admin_service_add_key_auto_generates_id_when_missing(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="custom_a",
            api_base="https://example.com/v1",
            provider_type="custom",
            provided_models=["glm-5"],
        )
    )
    service.add_key("custom_a", admin_service_mod.KeyCreateRequest(id=None, value="sk-auto-1", enabled=True))
    service.add_key("custom_a", admin_service_mod.KeyCreateRequest(id=None, value="sk-auto-2", enabled=True))

    cfg = service.get_config()
    ch = next(c for c in cfg.channels if c.id == "custom_a")
    assert [k.id for k in ch.api_keys] == ["key_1", "key_2"]


def test_admin_service_update_key_supports_renaming_id(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(admin_service_mod.ChannelCreateRequest(id="custom_a", api_base="https://example.com/v1"))
    service.add_key("custom_a", admin_service_mod.KeyCreateRequest(id="k1", value="sk-1", enabled=True))

    service.update_key("custom_a", "k1", admin_service_mod.KeyUpdateRequest(id="k_renamed", value="sk-1-updated", enabled=False))

    cfg = service.get_config()
    ch = next(c for c in cfg.channels if c.id == "custom_a")
    assert ch.api_keys[0].id == "k_renamed"
    assert ch.api_keys[0].value == "sk-1-updated"
    assert ch.api_keys[0].enabled is False



def test_admin_service_runtime_overlay_skips_disabled_and_cleans_virtuals(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="enabled_a",
            api_base="https://enabled.example.com/v1",
            provider_type="openai_compatible",
            provided_models=["m1"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-enabled")],
            enabled=True,
        )
    )
    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="disabled_b",
            api_base="https://disabled.example.com/v1",
            provider_type="openai_compatible",
            provided_models=["m2"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-disabled")],
            enabled=False,
        )
    )

    from proxy_app.admin_schemas import VirtualModelAdminConfig, VirtualTargetConfig

    service.create_or_update_virtual_model(
        "vm_enabled",
        VirtualModelAdminConfig(
            enabled=True,
            strategy="sequential",
            targets=[VirtualTargetConfig(model="enabled_a/m1")],
        ),
    )

    overlay = service.build_runtime_env_overlay()
    assert "ENABLED_A_API_BASE" in overlay
    assert "DISABLED_B_API_BASE" not in overlay
    assert "VIRTUAL_MODELS" in overlay

    apply1 = service.apply_runtime_overlay()
    assert "ENABLED_A_API_BASE" in apply1["overlay_keys"]

    service.create_or_update_virtual_model(
        "vm_enabled",
        VirtualModelAdminConfig(enabled=False, strategy="sequential", targets=[VirtualTargetConfig(model="enabled_a/m1")]),
    )
    service.update_channel("enabled_a", admin_service_mod.ChannelUpdateRequest(enabled=False))
    apply2 = service.apply_runtime_overlay()
    assert "ENABLED_A_API_BASE" in apply2["removed_stale_keys"]
    assert "VIRTUAL_MODELS" in apply2["removed_stale_keys"]


def test_admin_service_auto_virtual_model_balanced(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="inf",
            api_base="https://inf.example.com/v1",
            provider_type="openai_compatible",
            provided_models=["kimi-k2.5", "glm-5"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-inf")],
            enabled=True,
        )
    )
    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="ali",
            api_base="https://ali.example.com/v1",
            provider_type="openai_compatible",
            provided_models=["kimi-k2.5"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-ali")],
            enabled=True,
        )
    )

    vms = service.list_virtual_models()
    assert "kimi-k2.5" in vms
    assert vms["kimi-k2.5"]["strategy"] == "balanced"
    target_models = {t["model"] for t in vms["kimi-k2.5"]["targets"]}
    assert target_models == {"inf/kimi-k2.5", "ali/kimi-k2.5"}

    overlay = service.build_runtime_env_overlay()
    assert "VIRTUAL_MODELS" in overlay
    assert '"strategy": "balanced"' in overlay["VIRTUAL_MODELS"]


def test_admin_service_manual_virtual_model_overrides_auto(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(admin_service_mod.ChannelCreateRequest(id="a", api_base="https://a.example.com/v1", provided_models=["m1"]))
    service.create_channel(admin_service_mod.ChannelCreateRequest(id="b", api_base="https://b.example.com/v1", provided_models=["m1"]))

    from proxy_app.admin_schemas import VirtualModelAdminConfig, VirtualTargetConfig
    service.create_or_update_virtual_model(
        "m1",
        VirtualModelAdminConfig(enabled=True, strategy="sequential", targets=[VirtualTargetConfig(model="a/m1")]),
    )

    vms = service.list_virtual_models()
    assert vms["m1"]["strategy"] == "sequential"


def test_admin_service_auto_virtual_model_exposes_single_channel_model(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="single",
            api_base="https://single.example.com/v1",
            provider_type="openai_compatible",
            provided_models=["deepseek-v3.2"],
            enabled=True,
        )
    )

    vms = service.list_virtual_models()
    assert "deepseek-v3.2" in vms
    assert vms["deepseek-v3.2"]["strategy"] == "balanced"
    assert [t["model"] for t in vms["deepseek-v3.2"]["targets"]] == ["single/deepseek-v3.2"]


def test_admin_service_auto_virtual_model_normalizes_lightweight_names(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(id="a", api_base="https://a.example.com/v1", provided_models=["glm5"])
    )
    service.create_channel(
        admin_service_mod.ChannelCreateRequest(id="b", api_base="https://b.example.com/v1", provided_models=["glm-5"])
    )

    vms = service.list_virtual_models()
    assert "glm-5" in vms
    targets = {t["model"] for t in vms["glm-5"]["targets"]}
    assert targets == {"a/glm5", "b/glm-5"}
    assert "glm5" not in vms


def test_admin_service_corrupted_config_readonly_protection(monkeypatch, tmp_path):
    admin_store, admin_service_mod = _reload_modules(monkeypatch, tmp_path)

    config_path = admin_store.get_default_root() / "data" / "admin_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{bad json", encoding="utf-8")

    service = admin_service_mod.AdminService()
    masked = service.get_config_masked()
    store_health = masked.get("_store_health", {})
    assert store_health.get("ok") is False
    assert store_health.get("corrupt_evidence_path")

    try:
        service.create_channel(
            admin_service_mod.ChannelCreateRequest(
                id="blocked_write",
                api_base="https://example.com/v1",
                provider_type="openai_compatible",
            )
        )
        assert False, "expected readonly protection to block writes"
    except ValueError as e:
        assert "只读模式" in str(e)
