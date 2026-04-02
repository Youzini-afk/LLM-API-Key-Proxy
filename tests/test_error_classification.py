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
