import importlib
import sys
import types
import importlib.util
import os
import json

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


@pytest.mark.asyncio
async def test_v1_http_exception_is_wrapped_to_openai_error(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    class _Req:
        class _URL:
            path = "/v1/chat/completions"

        url = _URL()

    resp = await main_mod.v1_openai_error_handler(
        _Req(),
        HTTPException(status_code=401, detail="Invalid or missing API Key"),
    )

    assert resp.status_code == 401
    body = json.loads(resp.body.decode("utf-8"))
    assert body["error"]["type"] == "authentication"
    assert "Invalid or missing API Key" in body["error"]["message"]


def test_extract_sse_error_from_chunk(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    chunk = 'data: {"error":{"message":"all targets failed","type":"virtual_model_exhausted"}}\n\n'
    parsed = main_mod._extract_sse_error_from_chunk(chunk)

    assert parsed is not None
    assert parsed["type"] == "virtual_model_exhausted"
    assert parsed["message"] == "all targets failed"


@pytest.mark.asyncio
async def test_prime_stream_first_chunk_replays(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    async def _gen():
        yield "data: first\n\n"
        yield "data: second\n\n"

    first, replay = await main_mod._prime_stream_first_chunk(_gen())
    assert first == "data: first\n\n"

    collected = []
    async for item in replay:
        collected.append(item)

    assert collected == ["data: first\n\n", "data: second\n\n"]


@pytest.mark.asyncio
async def test_streaming_response_wrapper_closes_underlying_stream_on_disconnect(
    monkeypatch,
):
    main_mod = _reload_main(monkeypatch)

    class _DummyRequest:
        async def is_disconnected(self):
            return True

    class _DummyStream:
        def __init__(self):
            self.closed = False
            self._yielded = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._yielded:
                raise StopAsyncIteration
            self._yielded = True
            return 'data: {"id":"x","choices":[]}\n\n'

        async def aclose(self):
            self.closed = True

    stream = _DummyStream()
    wrapped = main_mod.streaming_response_wrapper(_DummyRequest(), {}, stream)

    collected = []
    async for item in wrapped:
        collected.append(item)

    assert collected == []
    assert stream.closed is True


@pytest.mark.asyncio
async def test_chat_completions_streaming_virtual_first_error_returns_json(monkeypatch):
    main_mod = _reload_main(monkeypatch)

    class _DummyReqClient:
        host = "127.0.0.1"
        port = 12345

    class _DummyRequest:
        headers = {}
        url = "http://test/v1/chat/completions"
        client = _DummyReqClient()

        async def json(self):
            return {"model": "vm-test", "stream": True, "messages": [{"role": "user", "content": "hi"}]}

        async def is_disconnected(self):
            return False

    async def _error_stream():
        yield 'data: {"error":{"message":"all failed","type":"virtual_model_exhausted"}}\n\n'
        yield "data: [DONE]\n\n"

    async def _fake_execute_virtual_completion_streaming(client, request, request_data, virtual_model_name):
        return (_error_stream(), "", 0)

    monkeypatch.setattr(main_mod, "log_request_to_console", lambda **kwargs: None)

    import proxy_app.virtual_models as vm_mod
    import proxy_app.aggregate_router as ar_mod

    monkeypatch.setattr(vm_mod, "is_virtual_model", lambda model: model == "vm-test")
    monkeypatch.setattr(vm_mod, "get_virtual_model", lambda model: object() if model == "vm-test" else None)
    monkeypatch.setattr(ar_mod, "execute_virtual_completion_streaming", _fake_execute_virtual_completion_streaming)

    response = await main_mod.chat_completions(
        request=_DummyRequest(),
        client=object(),
        _=None,
    )

    assert isinstance(response, main_mod.JSONResponse)
    assert response.status_code == 503
    body = json.loads(response.body.decode("utf-8"))
    assert body["error"]["type"] == "virtual_model_exhausted"
    assert body["error"]["message"] == "all failed"


@pytest.mark.asyncio
async def test_get_rotating_client_returns_runtime_synced_instance(monkeypatch):
    main_mod = _reload_main(monkeypatch)
    original_client = object()
    refreshed_client = object()

    class _State:
        rotating_client = original_client

    class _App:
        state = _State()

    class _Request:
        app = _App()

    async def _fake_sync(app):
        app.state.rotating_client = refreshed_client
        return {}

    monkeypatch.setattr(main_mod, "_ensure_runtime_synced", _fake_sync)

    client = await main_mod.get_rotating_client(_Request())

    assert client is refreshed_client


def test_prime_runtime_from_admin_config_applies_overlay(monkeypatch):
    main_mod = _reload_main(monkeypatch)
    cfg = types.SimpleNamespace(metadata=types.SimpleNamespace(version=7))

    monkeypatch.setattr(main_mod.admin_service, "get_config", lambda: cfg)
    monkeypatch.setattr(
        main_mod.admin_service,
        "build_runtime_env_overlay",
        lambda: {
            "GLOBAL_TIMEOUT": "20",
            "TEST_PROVIDER_API_KEY_1": "sk-test",
        },
    )

    main_mod._managed_overlay_keys = {"STALE_KEY"}
    main_mod._last_synced_admin_version = None
    monkeypatch.setenv("STALE_KEY", "obsolete")

    version = main_mod._prime_runtime_from_admin_config()

    assert version == 7
    assert main_mod._last_synced_admin_version == 7
    assert os.getenv("GLOBAL_TIMEOUT") == "20"
    assert os.getenv("TEST_PROVIDER_API_KEY_1") == "sk-test"
    assert os.getenv("STALE_KEY") is None
