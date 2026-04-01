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


def test_admin_service_auto_channel_id_and_api_base_normalize(monkeypatch, tmp_path):
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
    # 自动去掉 /chat/completions，保留 API base
    assert ch.api_base == "https://cloud.infini-ai.com/maas/coding/v1"

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
