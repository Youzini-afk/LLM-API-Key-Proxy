import importlib


def _reload_modules(monkeypatch, tmp_path):
    import proxy_app.admin_store as admin_store

    monkeypatch.setattr(admin_store, "get_default_root", lambda: tmp_path)
    importlib.reload(admin_store)
    monkeypatch.setattr(admin_store, "get_default_root", lambda: tmp_path)

    import proxy_app.admin_service as admin_service
    importlib.reload(admin_service)

    return admin_store, admin_service


def test_overlay_full_sync_removes_stale_keys(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="ch_a",
            api_base="https://example.com/v1",
            provider_type="openai_compatible",
            provided_models=["m1"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-a")],
            enabled=True,
        )
    )

    first = service.apply_runtime_overlay()
    assert "CH_A_API_BASE" in first["overlay_keys"]

    service.delete_channel("ch_a")
    second = service.apply_runtime_overlay()
    assert "CH_A_API_BASE" in second["removed_stale_keys"]


def test_disabled_channel_not_emitted_in_runtime_overlay(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="ch_enabled",
            api_base="https://example.com/v1",
            provider_type="openai_compatible",
            provided_models=["m1"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-1")],
            enabled=True,
        )
    )
    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="ch_disabled",
            api_base="https://example.com/v1",
            provider_type="openai_compatible",
            provided_models=["m2"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-2")],
            enabled=False,
        )
    )

    overlay = service.build_runtime_env_overlay()
    assert "CH_ENABLED_API_BASE" in overlay
    assert "CH_DISABLED_API_BASE" not in overlay


def test_provider_type_overlay_present(monkeypatch, tmp_path):
    _, admin_service_mod = _reload_modules(monkeypatch, tmp_path)
    service = admin_service_mod.AdminService()

    service.create_channel(
        admin_service_mod.ChannelCreateRequest(
            id="anthropic_a",
            api_base="https://example.com/v1",
            provider_type="anthropic",
            provided_models=["claude-sonnet"],
            api_keys=[admin_service_mod.ChannelKeyConfig(id="k1", value="sk-a")],
            enabled=True,
        )
    )

    overlay = service.build_runtime_env_overlay()
    assert overlay["PROVIDER_TYPE_ANTHROPIC_A"] == "anthropic"
