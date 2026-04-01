import pytest
import importlib.util


def _stub_litellm_modules(monkeypatch):
    import sys
    import types

    fake_litellm = types.ModuleType("litellm")

    class _BaseErr(Exception):
        pass

    class _UsageObj:
        prompt_tokens = 0
        completion_tokens = 0
        prompt_tokens_details = None

    class _ModelResp:
        usage = _UsageObj()

    class _EmbeddingResp:
        usage = _UsageObj()

    fake_litellm.ModelResponse = _ModelResp
    fake_litellm.EmbeddingResponse = _EmbeddingResp
    fake_litellm.InvalidRequestError = _BaseErr
    fake_litellm.ContextWindowExceededError = _BaseErr
    fake_litellm.AuthenticationError = _BaseErr
    fake_litellm.RateLimitError = _BaseErr
    fake_litellm.ServiceUnavailableError = _BaseErr
    fake_litellm.APIConnectionError = _BaseErr
    fake_litellm.Timeout = _BaseErr
    fake_litellm.InternalServerError = _BaseErr
    fake_litellm.OpenAIError = _BaseErr
    fake_litellm.set_verbose = False
    fake_litellm.drop_params = True
    fake_litellm.completion_cost = lambda *args, **kwargs: 0
    fake_litellm.get_model_info = lambda *args, **kwargs: {}

    litellm_ex = types.ModuleType("litellm.exceptions")
    litellm_ex.APIConnectionError = _BaseErr

    litellm_tc = types.ModuleType("litellm.litellm_core_utils.token_counter")
    litellm_tc.token_counter = lambda *args, **kwargs: 0

    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    monkeypatch.setitem(sys.modules, "litellm.exceptions", litellm_ex)
    monkeypatch.setitem(sys.modules, "litellm.litellm_core_utils.token_counter", litellm_tc)


def test_provider_config_runtime_provider_type_mapping(monkeypatch):
    if importlib.util.find_spec("litellm") is None:
        pytest.skip("litellm not installed in test environment")

    from rotator_library.provider_config import ProviderConfig

    monkeypatch.setenv("CHANNEL_A_API_BASE", "https://example.com/v1")
    cfg = ProviderConfig(provider_type_overrides={"channel_a": "openai_compatible"})

    out = cfg.convert_for_litellm(model="channel_a/kimi-k2.5")
    assert out["model"] == "openai/kimi-k2.5"
    assert out["api_base"] == "https://example.com/v1"
    assert out["custom_llm_provider"] == "openai"


def test_provider_config_openai_compatible_not_custom_provider(monkeypatch):
    from rotator_library.provider_config import ProviderConfig

    monkeypatch.delenv("ALI_API_BASE", raising=False)
    cfg = ProviderConfig(provider_type_overrides={"ali": "openai_compatible"})

    # Regression: openai_compatible must NOT be treated as dynamic custom provider
    # requiring ALI_API_BASE.
    assert cfg.is_custom_provider("ali") is False


def test_provider_config_explicit_custom_still_custom_provider(monkeypatch):
    from rotator_library.provider_config import ProviderConfig

    monkeypatch.delenv("ALI_API_BASE", raising=False)
    cfg = ProviderConfig(provider_type_overrides={"ali": "custom"})

    assert cfg.is_custom_provider("ali") is True


def test_provider_config_openai_compatible_convert_without_forced_custom_detection(monkeypatch):
    from rotator_library.provider_config import ProviderConfig

    monkeypatch.setenv("ALI_API_BASE", "https://dashscope.example/v1")
    cfg = ProviderConfig(provider_type_overrides={"ali": "openai_compatible"})
    assert cfg.convert_for_litellm(model="ali/kimi-k2.5")["model"] == "openai/kimi-k2.5"


@pytest.mark.asyncio
async def test_usage_manager_public_identifier_redacts_raw_key(monkeypatch, tmp_path):
    if importlib.util.find_spec("litellm") is None or importlib.util.find_spec("aiofiles") is None:
        pytest.skip("litellm/aiofiles not installed in test environment")

    _stub_litellm_modules(monkeypatch)
    from rotator_library.usage_manager import UsageManager

    monkeypatch.setenv("CHANNEL_A_API_KEY_1", "sk-real-secret")
    monkeypatch.setenv("CHANNEL_A_API_KEY_ID_1", "main")

    um = UsageManager(file_path=tmp_path / "usage.json")

    identifier = um._build_public_credential_identifier("channel_a", "sk-real-secret")
    assert identifier == "key:channel_a/main"
    assert "sk-real-secret" not in identifier

    public_full_path = um._build_public_full_path("sk-real-secret")
    assert public_full_path is None
