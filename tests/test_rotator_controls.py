import asyncio
import asyncio
import importlib
import importlib.machinery
import sys
import time
import types

import pytest


def _stub_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    return module


@pytest.fixture
def usage_manager_modules(monkeypatch):
    litellm_stub = _stub_module("litellm")
    litellm_stub.ModelResponse = object

    exceptions_stub = _stub_module("litellm.exceptions")
    for name in [
        "APIConnectionError",
        "RateLimitError",
        "ServiceUnavailableError",
        "AuthenticationError",
        "InvalidRequestError",
        "BadRequestError",
        "OpenAIError",
        "InternalServerError",
        "Timeout",
        "ContextWindowExceededError",
    ]:
        setattr(exceptions_stub, name, type(name, (Exception,), {}))

    providers_stub = _stub_module("rotator_library.providers")
    providers_stub.PROVIDER_PLUGINS = {}
    aiofiles_stub = _stub_module("aiofiles")

    monkeypatch.setitem(sys.modules, "litellm", litellm_stub)
    monkeypatch.setitem(sys.modules, "litellm.exceptions", exceptions_stub)
    monkeypatch.setitem(sys.modules, "rotator_library.providers", providers_stub)
    monkeypatch.setitem(sys.modules, "aiofiles", aiofiles_stub)

    sys.modules.pop("rotator_library.error_handler", None)
    sys.modules.pop("rotator_library.usage_manager", None)

    error_handler = importlib.import_module("rotator_library.error_handler")
    usage_manager_module = importlib.import_module("rotator_library.usage_manager")

    yield error_handler.NoAvailableKeysError, usage_manager_module.UsageManager

    sys.modules.pop("rotator_library.usage_manager", None)
    sys.modules.pop("rotator_library.error_handler", None)


@pytest.mark.asyncio
async def test_acquire_key_stops_after_configured_busy_wait_attempts(
    monkeypatch, tmp_path, usage_manager_modules
):
    NoAvailableKeysError, UsageManager = usage_manager_modules
    monkeypatch.setenv("KEY_BUSY_WAIT_INTERVAL_SECONDS", "0.1")
    monkeypatch.setenv("KEY_BUSY_WAIT_MAX_ATTEMPTS", "2")

    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    usage_manager._usage_data = {}
    usage_manager._initialized.set()

    keys = ["key_a", "key_b"]
    model = "relay/model"
    usage_manager._initialize_key_states(keys)
    for key in keys:
        usage_manager.key_states[key]["models_in_use"][model] = 1

    with pytest.raises(
        NoAvailableKeysError, match="All eligible credentials stayed busy"
    ):
        await usage_manager.acquire_key(
            available_keys=keys,
            model=model,
            deadline=time.time() + 1.0,
            max_concurrent=1,
        )


@pytest.mark.asyncio
async def test_acquire_key_wakes_when_any_key_is_released(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    monkeypatch.setenv("KEY_BUSY_WAIT_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("KEY_BUSY_WAIT_MAX_ATTEMPTS", "2")

    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    usage_manager._usage_data = {}
    usage_manager._initialized.set()

    keys = ["key_a", "key_b"]
    model = "relay/model"
    usage_manager._initialize_key_states(keys)
    for key in keys:
        usage_manager.key_states[key]["models_in_use"][model] = 1

    async def release_later():
        await asyncio.sleep(0.05)
        await usage_manager.release_key("key_b", model)

    release_task = asyncio.create_task(release_later())
    try:
        acquired = await usage_manager.acquire_key(
            available_keys=keys,
            model=model,
            deadline=time.time() + 1.0,
            max_concurrent=1,
        )
    finally:
        await release_task

    assert acquired == "key_b"


@pytest.mark.asyncio
async def test_save_usage_is_deferred_off_request_path(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    monkeypatch.setenv("USAGE_SAVE_DEBOUNCE_SECONDS", "0")

    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    usage_manager._usage_data = {"key_a": {"models": {}}}
    usage_manager._initialized.set()

    writes = []

    def fake_write(data):
        time.sleep(0.05)
        writes.append(data)

    usage_manager._state_writer.write = fake_write

    start = time.perf_counter()
    await usage_manager._save_usage()
    elapsed = time.perf_counter() - start

    assert elapsed < 0.03

    await asyncio.sleep(0.1)
    assert writes

    await usage_manager.shutdown()
