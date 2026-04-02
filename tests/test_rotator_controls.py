import asyncio
import asyncio
import importlib
import importlib.machinery
import json
import sys
import time
import types

import pytest


def _stub_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    return module


def _make_usage_entry(model: str, *, success_count: int = 0, last_used_ts: float = 0.0):
    return {
        "models": {model: {"success_count": success_count}},
        "global": {"models": {}},
        "model_cooldowns": {},
        "failures": {},
        "last_used_ts": last_used_ts,
    }


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


@pytest.mark.asyncio
async def test_scheduler_state_migrates_into_snapshot(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    usage_manager._usage_data = {
        "key_a": {
            "models": {"relay/model": {"success_count": 1}},
            "global": {"models": {}},
            "model_cooldowns": {},
            "failures": {},
        }
    }
    usage_manager._initialized.set()

    snapshot = await usage_manager._build_usage_snapshot_for_save()

    assert "scheduler" in snapshot["key_a"]
    assert snapshot["key_a"]["scheduler"]["credential_global"]["scheduler_state"] == "hot"


@pytest.mark.asyncio
async def test_internal_fair_cycle_state_is_not_mutated_by_maintenance(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    fair_cycle_data = {
        "relay": {
            "1": {
                "relay/model": {
                    "cycle_started_at": time.time(),
                    "exhausted": ["env://relay/1"],
                }
            }
        }
    }
    usage_manager._usage_data = {
        "__fair_cycle__": json.loads(json.dumps(fair_cycle_data)),
        "env://relay/1": _make_usage_entry("relay/model"),
    }
    usage_manager._initialized.set()

    await usage_manager.run_maintenance()

    assert usage_manager._usage_data["__fair_cycle__"] == fair_cycle_data
    assert "scheduler" not in usage_manager._usage_data["__fair_cycle__"]


@pytest.mark.asyncio
async def test_acquire_key_respects_sequential_stickiness(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    model = "relay/model"
    now_ts = time.time()
    key_hot = "env://relay/1"
    key_cold = "env://relay/2"
    usage_manager._usage_data = {
        key_hot: _make_usage_entry(model, success_count=12, last_used_ts=now_ts),
        key_cold: _make_usage_entry(model, success_count=1, last_used_ts=now_ts - 100),
    }
    usage_manager._initialized.set()
    monkeypatch.setattr(usage_manager, "_get_rotation_mode", lambda provider: "sequential")

    selected = await usage_manager.acquire_key(
        available_keys=[key_hot, key_cold],
        model=model,
        deadline=time.time() + 1.0,
        max_concurrent=1,
        credential_priorities={key_hot: 1, key_cold: 1},
    )

    assert selected == key_hot


@pytest.mark.asyncio
async def test_acquire_key_applies_priority_concurrency_multiplier(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    model = "relay/model"
    high_priority_key = "env://relay/1"
    low_priority_key = "env://relay/2"
    usage_manager._usage_data = {
        high_priority_key: _make_usage_entry(model, success_count=5),
        low_priority_key: _make_usage_entry(model, success_count=1),
    }
    usage_manager._initialized.set()
    usage_manager._initialize_key_states([high_priority_key, low_priority_key])
    usage_manager.key_states[high_priority_key]["models_in_use"][model] = 2
    monkeypatch.setattr(usage_manager, "_get_rotation_mode", lambda provider: "balanced")
    monkeypatch.setattr(
        usage_manager,
        "_get_priority_multiplier",
        lambda provider, priority, mode: 3 if priority == 1 else 1,
    )

    selected = await usage_manager.acquire_key(
        available_keys=[high_priority_key, low_priority_key],
        model=model,
        deadline=time.time() + 1.0,
        max_concurrent=1,
        credential_priorities={high_priority_key: 1, low_priority_key: 2},
    )

    assert selected == high_priority_key


@pytest.mark.asyncio
async def test_acquire_key_respects_fair_cycle_exclusions(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    model = "relay/model"
    exhausted_key = "env://relay/1"
    busy_same_tier_key = "env://relay/2"
    fallback_key = "env://relay/3"
    usage_manager._usage_data = {
        exhausted_key: _make_usage_entry(model, success_count=9),
        busy_same_tier_key: _make_usage_entry(model, success_count=6),
        fallback_key: _make_usage_entry(model, success_count=1),
    }
    usage_manager._initialized.set()
    usage_manager._initialize_key_states(
        [exhausted_key, busy_same_tier_key, fallback_key]
    )
    usage_manager.key_states[busy_same_tier_key]["models_in_use"][model] = 1
    monkeypatch.setattr(usage_manager, "_get_rotation_mode", lambda provider: "sequential")

    tier_key = usage_manager._get_tier_key("relay", 1)
    tracking_key = usage_manager._get_tracking_key(exhausted_key, model, "relay")
    usage_manager._mark_credential_exhausted(
        exhausted_key, "relay", tier_key, tracking_key
    )

    selected = await usage_manager.acquire_key(
        available_keys=[exhausted_key, busy_same_tier_key, fallback_key],
        model=model,
        deadline=time.time() + 1.0,
        max_concurrent=1,
        credential_priorities={
            exhausted_key: 1,
            busy_same_tier_key: 1,
            fallback_key: 2,
        },
    )

    assert selected == fallback_key


@pytest.mark.asyncio
async def test_unknown_429_uses_sparse_recovery_ladder(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    usage_manager._usage_data = {}
    usage_manager._initialized.set()

    class DummyError:
        error_type = "rate_limit"
        retry_after = None
        quota_reset_timestamp = None
        status_code = 429
        original_exception = Exception("opaque 429")

    key = "env://relay/1"
    model = "relay/model"

    await usage_manager.record_failure(key, model, DummyError())
    tracking_key = usage_manager._get_scheduler_tracking_key(key, model)
    tracking_state = usage_manager._usage_data[key]["scheduler"]["tracking"][tracking_key]

    assert tracking_state["scheduler_state"] == "warm"
    assert tracking_state["probe_step"] == 1
    first_wait = tracking_state["next_probe_at"] - time.time()
    assert 10 <= first_wait <= 20

    tracking_state["next_probe_at"] = time.time() - 1
    tracking_state["next_eligible_at"] = time.time() - 1
    usage_manager._usage_data[key]["model_cooldowns"][model] = time.time() - 1

    await usage_manager.record_failure(key, model, DummyError())
    tracking_state = usage_manager._usage_data[key]["scheduler"]["tracking"][tracking_key]

    assert tracking_state["probe_step"] == 2
    second_wait = tracking_state["next_probe_at"] - time.time()
    assert 110 <= second_wait <= 130


@pytest.mark.asyncio
async def test_quota_stats_include_scheduler_fields(
    monkeypatch, tmp_path, usage_manager_modules
):
    _, UsageManager = usage_manager_modules
    usage_manager = UsageManager(file_path=tmp_path / "usage.json")
    usage_manager._usage_data = {
        "env://relay/1": {
            "models": {"relay/model": {"success_count": 1}},
            "global": {"models": {}},
            "model_cooldowns": {},
            "failures": {},
        }
    }
    usage_manager._initialized.set()

    stats = await usage_manager.get_stats_for_endpoint()
    credential = stats["providers"]["relay"]["credentials"][0]

    assert "scheduler_state" in credential
    assert "health_score" in credential
    assert "next_probe_at" in credential
    assert credential["recovery_hypothesis"].keys() == {
        "short",
        "weekly",
        "monthly",
        "expired",
    }
