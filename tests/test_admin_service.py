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

    from proxy_app.admin_schemas import ChannelKeyConfig

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="dashscope_a",
            api_base="https://example.com/v1",
            provider_type="openai_compatible",
            models={"kimi2.5": {"id": "kimi-k2"}},
            api_keys=[ChannelKeyConfig(id="k1", value="abc123")],
        )
    )

    overlay = service.build_runtime_env_overlay()
    assert overlay["DASHSCOPE_A_API_BASE"] == "https://example.com/v1"
    assert overlay["DASHSCOPE_A_API_KEY_1"] == "abc123"
    assert "DASHSCOPE_A_MODELS" in overlay
