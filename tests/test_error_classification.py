import importlib
import importlib.machinery
import sys
import types


def _stub_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    return module


def _load_error_handler():
    sys.modules.pop("rotator_library.error_handler", None)
    return importlib.import_module("rotator_library.error_handler")


def _install_litellm_stubs(monkeypatch):
    litellm_stub = _stub_module("litellm")
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
        exc = type(name, (Exception,), {})
        setattr(litellm_stub, name, exc)
        setattr(exceptions_stub, name, exc)

    monkeypatch.setitem(sys.modules, "litellm", litellm_stub)
    monkeypatch.setitem(sys.modules, "litellm.exceptions", exceptions_stub)

    return litellm_stub, exceptions_stub


def test_bad_request_auth_message_is_classified_as_authentication(monkeypatch):
    _, litellm_ex = _install_litellm_stubs(monkeypatch)
    error_handler = _load_error_handler()

    err = litellm_ex.BadRequestError(
        "litellm.BadRequestError: OpenAIException - invalid access token or token expired"
    )
    classified = error_handler.classify_error(err)

    assert classified.error_type == "authentication"
    assert error_handler.should_rotate_on_error(classified) is True


def test_bad_request_forbidden_message_is_classified_as_forbidden(monkeypatch):
    _, litellm_ex = _install_litellm_stubs(monkeypatch)
    error_handler = _load_error_handler()

    err = litellm_ex.BadRequestError("permission denied for this model")
    classified = error_handler.classify_error(err)

    assert classified.error_type == "forbidden"
    assert error_handler.should_rotate_on_error(classified) is True


def test_error_response_includes_counts_samples_and_hint(monkeypatch):
    _install_litellm_stubs(monkeypatch)
    error_handler = _load_error_handler()

    accumulator = error_handler.RequestErrorAccumulator()
    accumulator.model = "demo/model"
    accumulator.provider = "demo"
    accumulator.record_error(
        "sk-live-1",
        error_handler.ClassifiedError(
            error_type="rate_limit",
            original_exception=Exception("too many requests"),
            status_code=429,
        ),
        "HTTP 429: too many requests",
    )
    accumulator.record_error(
        "sk-live-2",
        error_handler.ClassifiedError(
            error_type="api_connection",
            original_exception=Exception("connection reset by peer"),
            status_code=503,
        ),
        "connection reset by peer",
    )

    payload = accumulator.build_client_error_response()
    details = payload["error"]["details"]

    assert details["error_type_counts"]["rate_limit"] == 1
    assert details["error_type_counts"]["api_connection"] == 1
    assert isinstance(details["sample_errors"], list)
    assert len(details["sample_errors"]) >= 2
    assert "hint" in details
    assert "Recent concrete failures" in payload["error"]["message"]
