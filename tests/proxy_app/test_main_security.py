import importlib
import sys
import types
import importlib.util

import pytest
from fastapi import HTTPException


def _stub_runtime_modules(monkeypatch):
    # rich
    rich_console = types.ModuleType("rich.console")

    class _DummyStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _DummyConsole:
        def status(self, *args, **kwargs):
            return _DummyStatus()

        def print(self, *args, **kwargs):
            return None

        def input(self, *args, **kwargs):
            return ""

    rich_console.Console = _DummyConsole

    # litellm
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

    monkeypatch.setitem(sys.modules, "rich.console", rich_console)
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    monkeypatch.setitem(sys.modules, "litellm.exceptions", litellm_ex)
    monkeypatch.setitem(sys.modules, "litellm.litellm_core_utils.token_counter", litellm_tc)


def _reload_main(monkeypatch, **env):
    if importlib.util.find_spec("colorlog") is None:
        pytest.skip("colorlog not installed in test environment")

    _stub_runtime_modules(monkeypatch)

    import proxy_app.main as main_mod

    for key in ["PROXY_API_KEY", "ADMIN_API_KEY", "ALLOW_INSECURE_NO_AUTH"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    importlib.reload(main_mod)
    return main_mod


@pytest.mark.asyncio
async def test_verify_api_key_fail_closed_by_default(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await main_mod.verify_api_key(auth=None)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_api_key_allows_explicit_insecure_mode(monkeypatch):
    main_mod = _reload_main(monkeypatch, ALLOW_INSECURE_NO_AUTH="true")

    # should not raise
    await main_mod.verify_api_key(auth=None)


@pytest.mark.asyncio
async def test_verify_admin_api_key_prefers_admin_key(monkeypatch):
    main_mod = _reload_main(
        monkeypatch,
        PROXY_API_KEY="proxy-secret",
        ADMIN_API_KEY="admin-secret",
    )

    with pytest.raises(HTTPException) as exc:
        await main_mod.verify_admin_api_key(auth="Bearer proxy-secret")
    assert exc.value.status_code == 401

    # should not raise
    await main_mod.verify_admin_api_key(auth="Bearer admin-secret")


@pytest.mark.asyncio
async def test_verify_anthropic_api_key_fail_closed_without_key(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        await main_mod.verify_anthropic_api_key(x_api_key=None, auth=None)

    assert exc.value.status_code == 503


def test_status_code_for_proxy_error_timeout(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    status = main_mod._status_code_for_proxy_error(
        {"type": "proxy_timeout", "message": "timed out"}
    )

    assert status == 504


def test_status_code_for_proxy_error_credentials_exhausted(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    status = main_mod._status_code_for_proxy_error(
        {"type": "proxy_all_credentials_exhausted", "message": "all exhausted"}
    )

    assert status == 503
