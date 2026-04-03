from rotator_library.request_sanitizer import sanitize_request_payload


def test_sanitizer_drops_relay_meta_null_and_openai_compat_params():
    payload = {
        "model": "channel_a/glm-5.1",
        "messages": [{"role": "user", "content": "ping"}],
        "route": "glm-5.1",
        "provider": "newapi",
        "vendor_trace_id": "abc-123",
        "user": None,
        "tools": [],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "response_format": {"type": "text"},
        "reasoning_effort": "high",
    }

    sanitized = sanitize_request_payload(
        payload,
        model="channel_a/glm-5.1",
        runtime_provider="openai_compatible",
    )

    assert "route" not in sanitized
    assert "provider" not in sanitized
    assert "vendor_trace_id" not in sanitized
    assert "user" not in sanitized
    assert "tools" not in sanitized
    assert "tool_choice" not in sanitized
    assert "parallel_tool_calls" not in sanitized
    assert "response_format" not in sanitized
    assert "reasoning_effort" not in sanitized


def test_sanitizer_keeps_reasoning_effort_for_non_openai_compatible():
    payload = {
        "model": "antigravity/gemini-2.5-pro",
        "messages": [{"role": "user", "content": "ping"}],
        "reasoning_effort": "high",
    }

    sanitized = sanitize_request_payload(
        payload,
        model="antigravity/gemini-2.5-pro",
        runtime_provider="antigravity",
    )

    assert sanitized.get("reasoning_effort") == "high"


def test_sanitizer_removes_thinking_for_non_supported_model():
    payload = {
        "model": "openai/gpt-4.1",
        "messages": [{"role": "user", "content": "ping"}],
        "thinking": {"type": "enabled", "budget_tokens": -1},
    }

    sanitized = sanitize_request_payload(
        payload,
        model="openai/gpt-4.1",
        runtime_provider="openai",
    )

    assert "thinking" not in sanitized


def test_sanitizer_keeps_internal_keys_for_openai_compatible():
    payload = {
        "model": "channel_a/glm-5.1",
        "messages": [{"role": "user", "content": "ping"}],
        "_forced_credential": "test-key",
        "_request_deadline": 123.4,
        "unknown_external_flag": True,
    }

    sanitized = sanitize_request_payload(
        payload,
        model="channel_a/glm-5.1",
        runtime_provider="openai_compatible",
    )

    assert sanitized.get("_forced_credential") == "test-key"
    assert sanitized.get("_request_deadline") == 123.4
    assert "unknown_external_flag" not in sanitized
