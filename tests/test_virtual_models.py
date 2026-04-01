"""Tests for virtual model aggregation layer."""
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
# 4. Aggregate router – error classification
# ---------------------------------------------------------------------------
from proxy_app.aggregate_router import _classify_exception_type, _should_fallback


class TestAggregateErrorClassification:
    def test_invalid_request_no_fallback(self):
        assert not _should_fallback("invalid_request")

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
