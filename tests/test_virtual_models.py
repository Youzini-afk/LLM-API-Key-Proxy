"""Tests for virtual model aggregation layer."""
import asyncio
import json
import os
import pytest

# ---------------------------------------------------------------------------
# 1. Schema & parsing tests
# ---------------------------------------------------------------------------
from proxy_app.schemas_virtual import (
    RouteTarget,
    VirtualModelConfig,
    parse_virtual_models_config,
)


class TestRouteTarget:
    def test_valid_target_string(self):
        t = RouteTarget(model="provider_a/model_x")
        assert t.provider == "provider_a"
        assert t.model_name == "model_x"
        assert t.enabled is True
        assert t.weight == 100

    def test_invalid_target_no_slash(self):
        with pytest.raises(Exception):
            RouteTarget(model="no_slash_model")

    def test_invalid_target_empty_parts(self):
        with pytest.raises(Exception):
            RouteTarget(model="/model")
        with pytest.raises(Exception):
            RouteTarget(model="provider/")


class TestVirtualModelConfig:
    def test_valid_config(self):
        cfg = VirtualModelConfig(
            strategy="sequential",
            targets=[RouteTarget(model="a/b"), RouteTarget(model="c/d")],
        )
        assert len(cfg.targets) == 2
        assert cfg.enabled is True

    def test_no_targets_fails(self):
        with pytest.raises(Exception):
            VirtualModelConfig(strategy="sequential", targets=[])

    def test_invalid_strategy(self):
        with pytest.raises(Exception):
            VirtualModelConfig(
                strategy="round_robin",
                targets=[RouteTarget(model="a/b")],
            )

    def test_enabled_targets_filters(self):
        cfg = VirtualModelConfig(
            targets=[
                RouteTarget(model="a/b", enabled=True),
                RouteTarget(model="c/d", enabled=False),
                RouteTarget(model="e/f", enabled=True),
            ]
        )
        assert len(cfg.enabled_targets) == 2


class TestParseVirtualModels:
    def test_simple_string_targets(self):
        raw = json.dumps(
            {
                "kimi2.5": {
                    "strategy": "sequential",
                    "targets": ["prov_a/kimi2.5", "prov_b/kimi2.5"],
                }
            }
        )
        result = parse_virtual_models_config(raw)
        assert "kimi2.5" in result
        cfg = result["kimi2.5"]
        assert len(cfg.targets) == 2
        assert cfg.targets[0].model == "prov_a/kimi2.5"

    def test_full_dict_targets(self):
        raw = json.dumps(
            {
                "glm5": {
                    "strategy": "primary_backup",
                    "targets": [
                        {"model": "prov_a/glm5", "weight": 100, "enabled": True},
                        {"model": "prov_b/glm5", "weight": 50, "enabled": False},
                    ],
                }
            }
        )
        result = parse_virtual_models_config(raw)
        assert "glm5" in result
        cfg = result["glm5"]
        assert cfg.strategy == "primary_backup"
        assert cfg.targets[1].enabled is False
        assert cfg.targets[1].weight == 50

    def test_mixed_targets(self):
        raw = json.dumps(
            {
                "test": {
                    "targets": [
                        "prov_a/m1",
                        {"model": "prov_b/m1", "weight": 80},
                    ]
                }
            }
        )
        result = parse_virtual_models_config(raw)
        assert len(result["test"].targets) == 2

    def test_invalid_json(self):
        result = parse_virtual_models_config("not json")
        assert result == {}

    def test_empty_targets_skipped(self):
        raw = json.dumps({"bad": {"targets": []}})
        result = parse_virtual_models_config(raw)
        assert "bad" not in result

    def test_invalid_target_skipped(self):
        raw = json.dumps(
            {
                "ok": {
                    "targets": ["valid/target", "invalid_no_slash"],
                }
            }
        )
        result = parse_virtual_models_config(raw)
        # The valid target should still be loaded
        assert "ok" in result
        assert len(result["ok"].targets) == 1

    def test_multiple_models(self):
        raw = json.dumps(
            {
                "model_a": {"targets": ["p/a"]},
                "model_b": {"targets": ["p/b", "q/b"]},
            }
        )
        result = parse_virtual_models_config(raw)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# 2. Registry tests
# ---------------------------------------------------------------------------
from proxy_app import virtual_models


class TestVirtualModelRegistry:
    def setup_method(self):
        # Reset module state
        virtual_models._registry = {}
        virtual_models._normalized_lookup = {}
        virtual_models._loaded = False

    def test_no_env_var(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_MODELS", raising=False)
        virtual_models.load_virtual_models()
        assert virtual_models.is_virtual_model("anything") is False
        assert virtual_models.get_virtual_model("anything") is None
        assert virtual_models.get_all_virtual_model_names() == []

    def test_with_env_var(self, monkeypatch):
        config = json.dumps(
            {
                "kimi2.5": {
                    "targets": ["prov_a/kimi2.5", "prov_b/kimi2.5"]
                }
            }
        )
        monkeypatch.setenv("VIRTUAL_MODELS", config)
        virtual_models.load_virtual_models()

        assert virtual_models.is_virtual_model("kimi2.5") is True
        assert virtual_models.is_virtual_model("nonexistent") is False

        cfg = virtual_models.get_virtual_model("kimi2.5")
        assert cfg is not None
        assert len(cfg.targets) == 2

    def test_virtual_prefix_stripped(self, monkeypatch):
        config = json.dumps({"test_model": {"targets": ["p/m"]}})
        monkeypatch.setenv("VIRTUAL_MODELS", config)
        virtual_models.load_virtual_models()

        assert virtual_models.is_virtual_model("virtual/test_model") is True
        assert virtual_models.get_virtual_model("virtual/test_model") is not None

    def test_lookup_allows_alias_tag_prefix(self, monkeypatch):
        config = json.dumps({"[喵喵] kimi-k2.5": {"targets": ["ali/kimi-k2.5"]}})
        monkeypatch.setenv("VIRTUAL_MODELS", config)
        virtual_models.load_virtual_models()

        assert virtual_models.is_virtual_model("kimi-k2.5") is True
        assert virtual_models.get_virtual_model("kimi-k2.5") is not None

    def test_ambiguous_normalized_name_requires_exact_match(self, monkeypatch):
        config = json.dumps(
            {
                "ab": {"targets": ["p/a"]},
                "a-b": {"targets": ["q/b"]},
            }
        )
        monkeypatch.setenv("VIRTUAL_MODELS", config)
        virtual_models.load_virtual_models()

        # exact names still work
        assert virtual_models.is_virtual_model("ab") is True
        assert virtual_models.is_virtual_model("a-b") is True
        # ambiguous normalized key should not resolve fuzzy lookup
        assert virtual_models.is_virtual_model("a b") is False


# ---------------------------------------------------------------------------
# 3. Strategy tests
# ---------------------------------------------------------------------------
from proxy_app.route_strategy import resolve_targets


class TestRouteStrategy:
    def _make_config(self, strategy="sequential", n_targets=3, disabled=None):
        targets = []
        for i in range(n_targets):
            enabled = True if disabled is None else (i not in disabled)
            targets.append(
                RouteTarget(model=f"prov_{i}/model", weight=(i + 1) * 10, enabled=enabled)
            )
        return VirtualModelConfig(strategy=strategy, targets=targets)

    def test_sequential_preserves_order(self):
        cfg = self._make_config("sequential")
        result = resolve_targets(cfg)
        assert [t.model for t in result] == [
            "prov_0/model",
            "prov_1/model",
            "prov_2/model",
        ]

    def test_sequential_filters_disabled(self):
        cfg = self._make_config("sequential", disabled={1})
        result = resolve_targets(cfg)
        assert len(result) == 2
        assert all(t.enabled for t in result)

    def test_primary_backup_keeps_primary_first(self):
        cfg = self._make_config("primary_backup", n_targets=5)
        for _ in range(20):
            result = resolve_targets(cfg)
            assert result[0].model == "prov_0/model"
            assert len(result) == 5

    def test_balanced_returns_all(self):
        cfg = self._make_config("balanced")
        result = resolve_targets(cfg)
        assert len(result) == 3
        models = {t.model for t in result}
        assert models == {"prov_0/model", "prov_1/model", "prov_2/model"}

    def test_weighted_random_returns_all(self):
        cfg = self._make_config("weighted_random")
        result = resolve_targets(cfg)
        assert len(result) == 3
        models = {t.model for t in result}
        assert models == {"prov_0/model", "prov_1/model", "prov_2/model"}

    def test_max_target_attempts(self):
        cfg = VirtualModelConfig(
            strategy="sequential",
            max_target_attempts=2,
            targets=[
                RouteTarget(model="a/1"),
                RouteTarget(model="b/2"),
                RouteTarget(model="c/3"),
            ],
        )
        result = resolve_targets(cfg)
        assert len(result) == 2

    def test_empty_after_disable(self):
        cfg = self._make_config("sequential", n_targets=2, disabled={0, 1})
        result = resolve_targets(cfg)
        assert result == []


# ---------------------------------------------------------------------------
# 4. Aggregate router – error classification / timeout behavior
# ---------------------------------------------------------------------------
from proxy_app.aggregate_router import (
    _classify_exception_type,
    _should_fallback,
    execute_virtual_completion,
    execute_virtual_completion_streaming,
)


class TestAggregateErrorClassification:
    def test_invalid_request_no_fallback(self):
        assert not _should_fallback("invalid_request")

    def test_invalid_request_model_not_found_fallback(self):
        assert _should_fallback("invalid_request", "model not found for provider")

    def test_invalid_request_unsupported_parameter_fallback(self):
        assert _should_fallback(
            "invalid_request",
            "unsupported parameter: reasoning_effort",
        )

    def test_invalid_request_chinese_model_not_found_fallback(self):
        assert _should_fallback(
            "invalid_request",
            "模型不存在: kimi-k2.5",
        )

    def test_invalid_request_chinese_unknown_parameter_fallback(self):
        assert _should_fallback(
            "invalid_request",
            "未知参数: foo_bar",
        )

    def test_invalid_request_status_404_fallback_even_without_message(self):
        assert _should_fallback(
            "invalid_request",
            "",
            404,
        )

    def test_invalid_request_status_400_without_provider_hint_no_fallback(self):
        assert not _should_fallback(
            "invalid_request",
            "messages must be a non-empty array",
            400,
        )

    def test_context_window_no_fallback(self):
        assert not _should_fallback("context_window_exceeded")

    def test_rate_limit_fallback(self):
        assert _should_fallback("rate_limit")

    def test_server_error_fallback(self):
        assert _should_fallback("server_error")

    def test_unknown_fallback(self):
        assert _should_fallback("unknown")

    def test_classify_value_error(self):
        e = ValueError("bad value")
        assert _classify_exception_type(e) == "unknown"

    def test_classify_timeout(self):
        class FakeTimeout(Exception):
            pass
        FakeTimeout.__name__ = "TimeoutError"
        e = FakeTimeout()
        assert _classify_exception_type(e) == "timeout"


class TestAggregateRouterTimeouts:
    @pytest.mark.asyncio
    async def test_invalid_request_model_not_found_falls_back(self, monkeypatch):
        class FakeClient:
            global_timeout = 5

            async def acompletion(self, request=None, **kwargs):
                if kwargs["model"] == "first/model":
                    return {
                        "error": {
                            "type": "invalid_request",
                            "message": "model not found for provider",
                        }
                    }
                return {"id": "ok"}

        config = VirtualModelConfig(
            strategy="sequential",
            timeout_seconds=1,
            targets=[
                RouteTarget(model="first/model"),
                RouteTarget(model="second/model"),
            ],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )

        result, actual_target, fallback_count = await execute_virtual_completion(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test"},
            virtual_model_name="virtual/test",
        )

        assert result == {"id": "ok"}
        assert actual_target == "second/model"
        assert fallback_count == 1

    @pytest.mark.asyncio
    async def test_non_streaming_target_timeout_falls_back(self, monkeypatch):
        class FakeClient:
            global_timeout = 5

            async def acompletion(self, request=None, **kwargs):
                if kwargs["model"] == "slow/model":
                    await asyncio.sleep(1.05)
                    return {"id": "slow"}
                return {"id": "fast"}

        config = VirtualModelConfig(
            strategy="sequential",
            timeout_seconds=1,
            targets=[
                RouteTarget(model="slow/model"),
                RouteTarget(model="fast/model"),
            ],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )

        result, actual_target, fallback_count = await execute_virtual_completion(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test"},
            virtual_model_name="virtual/test",
        )

        assert result == {"id": "fast"}
        assert actual_target == "fast/model"
        assert fallback_count == 1

    @pytest.mark.asyncio
    async def test_non_streaming_empty_response_falls_back(self, monkeypatch):
        class FakeClient:
            global_timeout = 5

            async def acompletion(self, request=None, **kwargs):
                if kwargs["model"] == "empty/model":
                    return {
                        "id": "empty",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": ""},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                return {"id": "ok"}

        config = VirtualModelConfig(
            strategy="sequential",
            timeout_seconds=1,
            targets=[
                RouteTarget(model="empty/model"),
                RouteTarget(model="second/model"),
            ],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )

        result, actual_target, fallback_count = await execute_virtual_completion(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test"},
            virtual_model_name="virtual/test",
        )

        assert result == {"id": "ok"}
        assert actual_target == "second/model"
        assert fallback_count == 1

    @pytest.mark.asyncio
    async def test_non_streaming_shared_budget_prevents_latency_multiplication(
        self, monkeypatch
    ):
        attempted_models = []

        class FakeClient:
            global_timeout = 0.2

            async def acompletion(self, request=None, **kwargs):
                model = kwargs["model"]
                attempted_models.append(model)
                if model == "slow-err/model":
                    await asyncio.sleep(0.15)
                    return {
                        "error": {
                            "type": "rate_limit",
                            "message": "provider busy",
                        }
                    }
                if model == "slow-success/model":
                    await asyncio.sleep(0.15)
                    return {"id": "late-success"}
                return {"id": "fast-success"}

        config = VirtualModelConfig(
            strategy="sequential",
            timeout_seconds=1,
            targets=[
                RouteTarget(model="slow-err/model"),
                RouteTarget(model="slow-success/model"),
                RouteTarget(model="fast/model"),
            ],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )

        result, actual_target, fallback_count = await execute_virtual_completion(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test"},
            virtual_model_name="virtual/test",
        )

        assert result["error"]["type"] == "virtual_model_exhausted"
        assert result["error"]["details"]["targets_tried"] == 2
        assert actual_target == ""
        assert fallback_count == 1
        assert attempted_models == ["slow-err/model", "slow-success/model"]

    @pytest.mark.asyncio
    async def test_global_pool_can_pick_hot_candidate_from_later_provider(
        self, monkeypatch
    ):
        selected_specs = []

        class FakeUsageManager:
            def __init__(self):
                self.real_requests = 0

            def note_real_request(self):
                self.real_requests += 1

            async def acquire_virtual_candidate(self, specs, *, deadline, strategy, top_n):
                selected = next(spec for spec in specs if spec["provider"] == "prov_b")
                selected_specs.append((strategy, top_n, selected["provider"], selected["model"]))
                return {
                    **selected,
                    "target_model": selected["model"],
                }

        class FakeClient:
            global_timeout = 5
            virtual_scheduler_mode = "global_pool"
            all_credentials = {
                "prov_a": ["cred-a"],
                "prov_b": ["cred-b"],
            }
            max_concurrent_requests_per_key = {"prov_a": 1, "prov_b": 1}
            usage_manager = FakeUsageManager()

            def _build_provider_credential_context(self, provider, model, credentials_override=None):
                creds = credentials_override or self.all_credentials[provider]
                return {
                    "provider_plugin": None,
                    "credentials": list(creds),
                    "credential_priorities": None,
                    "credential_tier_names": None,
                }

            async def acompletion(self, request=None, **kwargs):
                if kwargs["model"] == "prov_b/model":
                    return {"id": "from-b"}
                return {"error": {"type": "rate_limit", "message": "bad candidate"}}

        config = VirtualModelConfig(
            strategy="balanced",
            timeout_seconds=1,
            targets=[
                RouteTarget(model="prov_a/model", weight=100),
                RouteTarget(model="prov_b/model", weight=100),
            ],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )

        result, actual_target, fallback_count = await execute_virtual_completion(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test"},
            virtual_model_name="virtual/test",
        )

        assert result == {"id": "from-b"}
        assert actual_target == "prov_b/model"
        assert fallback_count == 0
        assert selected_specs == [("balanced", 5, "prov_b", "prov_b/model")]
        assert FakeClient.usage_manager.real_requests == 1

    @pytest.mark.asyncio
    async def test_global_pool_resolves_route_model_before_selection_and_request(
        self, monkeypatch
    ):
        selected_request_models = []
        attempted_request_models = []

        class FakeUsageManager:
            async def acquire_virtual_candidate(self, specs, *, deadline, strategy, top_n):
                selected_request_models.extend(spec["model"] for spec in specs)
                selected = specs[0]
                return {
                    **selected,
                    "request_model": selected["model"],
                    "target_model": selected["route_model"],
                }

            def note_real_request(self):
                pass

        class FakeClient:
            global_timeout = 5
            virtual_scheduler_mode = "global_pool"
            all_credentials = {"prov_a": ["cred-a"]}
            max_concurrent_requests_per_key = {"prov_a": 1}
            usage_manager = FakeUsageManager()

            def _resolve_model_id(self, model, provider):
                assert model == "prov_a/alias"
                assert provider == "prov_a"
                return "prov_a/resolved"

            def _build_provider_credential_context(self, provider, model, credentials_override=None):
                assert model == "prov_a/resolved"
                creds = credentials_override or self.all_credentials[provider]
                return {
                    "provider_plugin": None,
                    "credentials": list(creds),
                    "credential_priorities": None,
                    "credential_tier_names": None,
                }

            async def acompletion(self, request=None, **kwargs):
                attempted_request_models.append(kwargs["model"])
                assert kwargs["_acquired_model"] == "prov_a/resolved"
                assert kwargs["_count_as_real_request"] is False
                return {"id": "resolved"}

        config = VirtualModelConfig(
            strategy="balanced",
            timeout_seconds=1,
            targets=[RouteTarget(model="prov_a/alias", weight=100)],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )

        result, actual_target, fallback_count = await execute_virtual_completion(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test"},
            virtual_model_name="virtual/test",
        )

        assert result == {"id": "resolved"}
        assert actual_target == "prov_a/alias"
        assert fallback_count == 0
        assert selected_request_models == ["prov_a/resolved"]
        assert attempted_request_models == ["prov_a/resolved"]

    @pytest.mark.asyncio
    async def test_global_pool_releases_candidate_if_budget_is_gone_before_request(
        self, monkeypatch
    ):
        releases = []

        class FakeUsageManager:
            async def acquire_virtual_candidate(self, specs, *, deadline, strategy, top_n):
                selected = specs[0]
                return {
                    **selected,
                    "request_model": selected["model"],
                    "target_model": selected["route_model"],
                }

            async def release_key(self, key, model):
                releases.append((key, model))

            def note_real_request(self):
                pass

        class FakeClient:
            global_timeout = 5
            virtual_scheduler_mode = "global_pool"
            all_credentials = {"prov_a": ["cred-a"]}
            max_concurrent_requests_per_key = {"prov_a": 1}
            usage_manager = FakeUsageManager()

            def _build_provider_credential_context(self, provider, model, credentials_override=None):
                return {
                    "provider_plugin": None,
                    "credentials": ["cred-a"],
                    "credential_priorities": None,
                    "credential_tier_names": None,
                }

            async def acompletion(self, request=None, **kwargs):
                raise AssertionError("request should not start when no budget remains")

        config = VirtualModelConfig(
            strategy="balanced",
            timeout_seconds=1,
            targets=[RouteTarget(model="prov_a/model", weight=100)],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )
        monkeypatch.setattr(
            "proxy_app.aggregate_router._compute_target_timeout",
            lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("no budget")),
        )

        result, actual_target, fallback_count = await execute_virtual_completion(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test"},
            virtual_model_name="virtual/test",
        )

        assert result["error"]["type"] == "virtual_model_exhausted"
        assert actual_target == ""
        assert fallback_count == 0
        assert releases == [("cred-a", "prov_a/model")]

    @pytest.mark.asyncio
    async def test_streaming_role_only_then_done_falls_back(self, monkeypatch):
        class FakeClient:
            global_timeout = 5

            def acompletion(self, request=None, **kwargs):
                if kwargs["model"] == "empty/model":
                    async def _empty_stream():
                        yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
                        yield "data: [DONE]\n\n"

                    return _empty_stream()

                async def _ok_stream():
                    yield 'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                    yield "data: [DONE]\n\n"

                return _ok_stream()

        config = VirtualModelConfig(
            strategy="sequential",
            timeout_seconds=1,
            targets=[
                RouteTarget(model="empty/model"),
                RouteTarget(model="ok/model"),
            ],
        )

        monkeypatch.setattr(
            "proxy_app.aggregate_router.get_virtual_model",
            lambda _: config,
        )

        stream, actual_target, fallback_count = await execute_virtual_completion_streaming(
            FakeClient(),
            request=None,
            request_data={"model": "virtual/test", "stream": True},
            virtual_model_name="virtual/test",
        )

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert any("hello" in chunk for chunk in chunks)
        assert not any("virtual_model_exhausted" in chunk for chunk in chunks)
