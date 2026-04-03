# SPDX-License-Identifier: MIT
# Aggregate Router – cross-provider target fallback for virtual models.
#
# This module sits *above* RotatingClient.  RotatingClient handles key
# rotation inside a single provider; AggregateRouter handles target
# rotation across multiple providers for a given virtual model.

import asyncio
import json
import logging
import re
import time
from collections import Counter
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

from proxy_app.virtual_models import get_virtual_model, is_virtual_model
from proxy_app.route_strategy import resolve_targets
from proxy_app.schemas_virtual import RouteTarget, VirtualModelConfig

logger = logging.getLogger("proxy_app.virtual_models")

# ---------------------------------------------------------------------------
# Error types that should NOT trigger fallback to the next target.
# These indicate a problem with the request itself, not the provider.
# ---------------------------------------------------------------------------
NON_FALLBACK_ERROR_TYPES = frozenset(
    {
        "invalid_request",
        "context_window_exceeded",
        "pre_request_callback_error",
    }
)


# ---------------------------------------------------------------------------
# Target-level failure record
# ---------------------------------------------------------------------------
class TargetFailure:
    """Records why a particular target failed."""

    def __init__(self, target: str, reason: str, error_type: str = "unknown",
                 status_code: Optional[int] = None):
        self.target = target
        self.reason = reason
        self.error_type = error_type
        self.status_code = status_code

    def to_dict(self) -> dict:
        d: Dict[str, Any] = {
            "target": self.target,
            "reason": self.error_type,
        }
        if self.status_code:
            d["status_code"] = self.status_code
        if self.reason:
            d["message"] = self.reason[:200]
        return d


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------
def _is_error_response(result: Any) -> bool:
    """Check whether a non-streaming RotatingClient result is an error."""
    if result is None:
        return True
    if isinstance(result, dict) and "error" in result:
        return True
    return False


def _extract_error_info(result: Any) -> Tuple[str, str, Optional[int]]:
    """
    Extract (error_type, message, status_code) from a RotatingClient error result.
    """
    if result is None:
        return ("unknown", "No response received", None)
    if isinstance(result, dict) and "error" in result:
        err = result["error"]
        return (
            err.get("type", "unknown"),
            err.get("message", str(err)),
            err.get("details", {}).get("status_code") if isinstance(err.get("details"), dict) else None,
        )
    return ("unknown", str(result), None)


def _has_nonempty_content(content: Any) -> bool:
    """Best-effort check for meaningful text/media content fields."""
    if content is None:
        return False
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        for item in content:
            if isinstance(item, str) and item.strip():
                return True
            if isinstance(item, dict):
                for key in ("text", "value", "content"):
                    val = item.get(key)
                    if isinstance(val, str) and val.strip():
                        return True
        return False
    return bool(content)


def _to_plain_dict(payload: Any) -> Optional[Dict[str, Any]]:
    """Convert response-like objects to dict when possible."""
    if isinstance(payload, dict):
        return payload
    for method_name in ("model_dump", "dict"):
        method = getattr(payload, method_name, None)
        if callable(method):
            try:
                data = method()
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return None


def _response_has_meaningful_completion(result: Any) -> bool:
    """Check non-streaming completion result for meaningful assistant output."""
    data = _to_plain_dict(result)
    if not data:
        return True

    # Non-chat payloads used in lightweight tests may not include choices.
    # In that case, keep prior behavior and treat as meaningful.
    if "choices" not in data:
        return True

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return False

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            if _has_nonempty_content(message.get("content")):
                return True
            if message.get("tool_calls") or message.get("function_call"):
                return True

        delta = choice.get("delta")
        if isinstance(delta, dict):
            if _has_nonempty_content(delta.get("content")):
                return True
            if delta.get("tool_calls") or delta.get("function_call"):
                return True
            if _has_nonempty_content(delta.get("reasoning")) or _has_nonempty_content(
                delta.get("reasoning_content")
            ):
                return True

        if choice.get("finish_reason") == "tool_calls":
            return True

    return False


def _stream_chunk_has_meaningful_output(parsed: Dict[str, Any]) -> bool:
    """Check a streaming JSON chunk for meaningful output."""
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return False

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if isinstance(delta, dict):
            if _has_nonempty_content(delta.get("content")):
                return True
            if delta.get("tool_calls") or delta.get("function_call"):
                return True
            if _has_nonempty_content(delta.get("reasoning")) or _has_nonempty_content(
                delta.get("reasoning_content")
            ):
                return True

        message = choice.get("message")
        if isinstance(message, dict):
            if _has_nonempty_content(message.get("content")):
                return True
            if message.get("tool_calls") or message.get("function_call"):
                return True

        if choice.get("finish_reason") == "tool_calls":
            return True

    return False


def _looks_provider_specific_invalid_request(
    message: str, status_code: Optional[int] = None
) -> bool:
    """
    Decide whether an invalid_request is likely provider-specific.

    These errors often recover by trying a different target/provider:
    - model not found / not available on this provider
    - provider-specific unsupported request fields
    """
    msg_raw = (message or "").strip()
    msg = msg_raw.lower()
    if not msg:
        # Some providers return empty body with a status code that still indicates
        # "route/target mismatch" semantics.
        return status_code in {404, 405, 409, 422}

    # Status codes that are very often provider/model/parameter mismatch errors.
    if status_code in {404, 405, 409, 422}:
        return True

    patterns = [
        "model not found",
        "no such model",
        "model does not exist",
        "model is not available",
        "not available for your account",
        "unsupported model",
        "unsupported parameter",
        "parameter is not supported",
        "unrecognized request argument",
        "unknown field",
        "invalid model",
        "not supported by this model",
        "is not supported for this model",
        "unsupported field",
        "extra inputs are not permitted",
        "unknown argument",
        "unknown parameter",
        "does not support",
        "not available on this provider",
    ]
    if any(p in msg for p in patterns):
        return True

    # Chinese provider-side request incompatibility patterns.
    zh_provider_specific_patterns = [
        "模型不存在",
        "模型未找到",
        "模型不可用",
        "无效模型",
        "不支持的模型",
        "参数不支持",
        "不支持参数",
        "未知参数",
        "未识别参数",
        "字段不存在",
        "不支持该参数",
    ]
    if any(p in msg_raw for p in zh_provider_specific_patterns):
        return True

    return False


def _should_fallback(
    error_type: str,
    message: str = "",
    status_code: Optional[int] = None,
) -> bool:
    """Decide whether to try the next target for this error type."""
    if error_type == "invalid_request":
        return _looks_provider_specific_invalid_request(message, status_code)
    return error_type not in NON_FALLBACK_ERROR_TYPES


async def _await_target_timeout(
    awaitable: Any, timeout_seconds: float, target_model: str
) -> Any:
    """Enforce per-target timeout budget for non-streaming virtual model attempts."""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except TimeoutError as exc:
        raise TimeoutError(
            f"Virtual model target '{target_model}' timed out after {timeout_seconds:.2f}s"
        ) from exc


async def _iter_stream_with_initial_timeout(
    stream: AsyncGenerator[str, None],
    timeout_seconds: float,
    target_model: str,
) -> AsyncGenerator[str, None]:
    """Fail over if a target does not produce its first streaming chunk in time."""
    iterator = stream.__aiter__()
    close_stream = getattr(stream, "aclose", None)
    try:
        first_chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_seconds)
    except StopAsyncIteration:
        if callable(close_stream):
            try:
                await close_stream()
            except Exception:
                pass
        return
    except TimeoutError as exc:
        if callable(close_stream):
            try:
                await close_stream()
            except Exception:
                pass
        raise TimeoutError(
            f"Virtual model target '{target_model}' produced no stream data within {timeout_seconds:.2f}s"
        ) from exc

    try:
        yield first_chunk
        async for chunk in iterator:
            yield chunk
    finally:
        if callable(close_stream):
            try:
                await close_stream()
            except Exception:
                pass


def _should_retry_candidate_acquire_error(exc: Exception, *, deadline: float) -> bool:
    """Retry candidate acquisition when hot pool is temporarily busy and budget remains."""
    if time.monotonic() >= deadline:
        return False
    msg = (str(exc) or "").lower()
    return "stayed busy" in msg or "stayed unavailable" in msg


def _build_aggregate_error(
    virtual_model: str, failures: List[TargetFailure]
) -> dict:
    """Build a unified error response when all targets have failed."""
    unsupported_parameters = _extract_unsupported_parameters(failures)
    hint = _build_failure_hint(failures, unsupported_parameters)
    message = f"All route targets failed for virtual model '{virtual_model}'"
    if hint:
        message = f"{message}. Hint: {hint}"

    details: Dict[str, Any] = {
        "virtual_model": virtual_model,
        "targets_tried": len(failures),
        "failures": [f.to_dict() for f in failures],
    }
    if failures:
        details["sample_errors"] = [f.to_dict() for f in failures[:3]]
    if unsupported_parameters:
        details["unsupported_parameters"] = unsupported_parameters
    if hint:
        details["hint"] = hint

    return {
        "error": {
            "message": message,
            "type": "virtual_model_exhausted",
            "details": details,
        }
    }


def _extract_unsupported_parameter(message: str) -> Optional[str]:
    """Best-effort extract unsupported parameter name from provider error text."""
    if not message:
        return None

    patterns = [
        r"(?:unsupported|unknown|unrecognized|invalid)\s+(?:request\s+)?(?:argument|parameter|field)\s*[:：`'\"\s]+\s*([a-zA-Z0-9_.-]+)",
        r"`([a-zA-Z0-9_.-]+)`\s+(?:is\s+)?not supported",
        r"未知参数[:：\s]*([A-Za-z0-9_.-]+)",
        r"未识别参数[:：\s]*([A-Za-z0-9_.-]+)",
        r"不支持(?:的)?参数[:：\s]*([A-Za-z0-9_.-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = (match.group(1) or "").strip("`'\" ").lower()
            if value:
                return value
    return None


def _extract_unsupported_parameters(failures: List[TargetFailure]) -> List[str]:
    params = {
        value
        for value in (
            _extract_unsupported_parameter(f.reason)
            for f in failures
            if f.error_type == "invalid_request"
        )
        if value
    }
    return sorted(params)


def _build_failure_hint(
    failures: List[TargetFailure], unsupported_parameters: List[str]
) -> str:
    if unsupported_parameters:
        params = ", ".join(unsupported_parameters[:3])
        return (
            f"Likely unsupported request parameter(s): {params}. "
            "External relay payload may include fields not accepted by upstream."
        )

    error_counts = Counter(f.error_type for f in failures)
    dominant_type, dominant_count = error_counts.most_common(1)[0] if error_counts else ("unknown", 0)
    if dominant_count and dominant_count == len(failures):
        if dominant_type == "invalid_request":
            return "Likely request payload incompatibility across all route targets."
        if dominant_type in {"rate_limit", "quota_exceeded"}:
            return "All targets are currently rate-limited or quota-limited."
        if dominant_type in {"authentication", "forbidden"}:
            return "Credential authorization failed across all targets."
    return ""


def _add_virtual_model_headers(
    headers: dict, virtual_model: str, actual_target: str, fallback_count: int
) -> dict:
    """Add virtual model metadata headers to the response."""
    headers["X-Proxy-Virtual-Model"] = virtual_model
    headers["X-Proxy-Actual-Target"] = actual_target
    headers["X-Proxy-Fallback-Count"] = str(fallback_count)
    return headers


def _resolve_overall_timeout_seconds(client: Any, config: VirtualModelConfig) -> float:
    """
    Use the proxy-wide request budget when available so aggregate fallback cannot
    multiply latency across targets.
    """
    raw_timeout = getattr(client, "global_timeout", None)
    try:
        parsed_timeout = float(raw_timeout) if raw_timeout is not None else None
    except (TypeError, ValueError):
        parsed_timeout = None

    if parsed_timeout and parsed_timeout > 0:
        return parsed_timeout
    return float(config.timeout_seconds)


def _compute_target_timeout(
    deadline: float,
    per_target_timeout_seconds: int,
    target_model: str,
) -> float:
    """Clamp each target attempt to the remaining aggregate request budget."""
    remaining_budget = deadline - time.monotonic()
    if remaining_budget <= 0:
        raise TimeoutError(
            f"Virtual model request budget exhausted before trying target '{target_model}'"
        )
    return min(float(per_target_timeout_seconds), remaining_budget)


def _should_use_global_pool(client: Any, config: VirtualModelConfig) -> bool:
    scheduler_mode = (
        getattr(client, "virtual_scheduler_mode", "legacy") or "legacy"
    ).strip().lower()
    enabled_target_count = len(config.enabled_targets or [])
    return scheduler_mode == "global_pool" and config.strategy in {
        "balanced",
        "weighted_random",
    } and enabled_target_count > 1


def _monotonic_to_wall_deadline(deadline: float) -> float:
    remaining = max(0.0, deadline - time.monotonic())
    return time.time() + remaining


def _resolve_route_model(client: Any, target_model: str) -> str:
    if hasattr(client, "_resolve_model_id") and "/" in target_model:
        provider = target_model.split("/", 1)[0]
        try:
            resolved = client._resolve_model_id(target_model, provider)
            if resolved:
                return resolved
        except Exception:
            logger.debug(
                f"[VirtualModel] Falling back to route model without resolution: {target_model}"
            )
    return target_model


def _note_real_virtual_request(client: Any) -> None:
    usage_manager = getattr(client, "usage_manager", None)
    if usage_manager and hasattr(usage_manager, "note_real_request"):
        usage_manager.note_real_request()


async def _release_virtual_candidate(client: Any, selected: Dict[str, Any]) -> None:
    usage_manager = getattr(client, "usage_manager", None)
    if not usage_manager or not hasattr(usage_manager, "release_key"):
        return
    try:
        await usage_manager.release_key(
            selected["key"],
            selected.get("request_model") or selected.get("model") or selected["target_model"],
        )
    except Exception as exc:
        logger.warning(
            f"[VirtualModel] Failed to release pre-acquired candidate {selected.get('target_model')}: {exc}"
        )


def _build_global_candidate_specs(
    client: Any,
    targets: List[RouteTarget],
) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    for target in targets:
        provider = target.provider
        if provider not in getattr(client, "all_credentials", {}):
            continue

        request_model = _resolve_route_model(client, target.model)
        provider_context = client._build_provider_credential_context(
            provider,
            request_model,
        )
        hard_cap = max(
            1, int(getattr(client, "max_concurrent_requests_per_key", {}).get(provider, 1))
        )
        route_weight_factor = float(target.weight) / 100.0
        for credential in provider_context.get("credentials", []):
            specs.append(
                {
                    "provider": provider,
                    "model": request_model,
                    "route_model": target.model,
                    "key": credential,
                    "hard_cap": hard_cap,
                    "route_weight_factor": route_weight_factor,
                }
            )
    return specs


# ---------------------------------------------------------------------------
# Non-streaming execution
# ---------------------------------------------------------------------------
async def execute_virtual_completion(
    client: Any,
    request: Any,
    request_data: dict,
    virtual_model_name: str,
) -> Tuple[Any, str, int]:
    """
    Execute a non-streaming completion for a virtual model, trying each target
    in order until one succeeds.

    Returns:
        (response, actual_target_model, fallback_count)

    Raises:
        Exception: propagates non-fallbackable errors immediately.
    """
    config = get_virtual_model(virtual_model_name)
    if config is None:
        raise ValueError(f"Virtual model '{virtual_model_name}' not found in registry")

    targets = resolve_targets(config)
    if not targets:
        raise ValueError(
            f"Virtual model '{virtual_model_name}' has no enabled targets"
        )

    failures: List[TargetFailure] = []
    overall_timeout_seconds = _resolve_overall_timeout_seconds(client, config)
    deadline = time.monotonic() + overall_timeout_seconds
    _note_real_virtual_request(client)

    if _should_use_global_pool(client, config):
        attempted_candidates: set[Tuple[str, str]] = set()
        candidate_specs = _build_global_candidate_specs(client, config.enabled_targets)
        global_pool_made_upstream_attempt = False
        global_pool_fallback_reserve = min(
            2.0, max(0.2, float(overall_timeout_seconds) * 0.2)
        )
        global_pool_deadline = max(
            time.monotonic(), deadline - global_pool_fallback_reserve
        )
        if not candidate_specs:
            raise ValueError(
                f"Virtual model '{virtual_model_name}' has no enabled targets with usable credentials"
            )

        while time.monotonic() < global_pool_deadline:
            remaining_specs = [
                spec
                for spec in candidate_specs
                if (spec["key"], spec["model"]) not in attempted_candidates
            ]
            if not remaining_specs:
                break

            try:
                selected = await client.usage_manager.acquire_virtual_candidate(
                    remaining_specs,
                    deadline=_monotonic_to_wall_deadline(deadline),
                    strategy=config.strategy,
                    top_n=5,
                )
            except Exception as e:
                if _should_retry_candidate_acquire_error(e, deadline=deadline):
                    await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
                    continue
                failures.append(
                    TargetFailure(
                        target=virtual_model_name,
                        reason=str(e),
                        error_type="proxy_busy",
                    )
                )
                break
            target_model = selected["target_model"]
            request_model = selected.get("request_model", selected["target_model"])
            attempted_candidates.add((selected["key"], request_model))

            try:
                attempt_timeout = _compute_target_timeout(
                    deadline,
                    config.timeout_seconds,
                    target_model,
                )
            except TimeoutError as e:
                logger.warning(
                    f"[VirtualModel] Aggregate request budget exhausted before "
                    f"candidate {target_model}/{selected['key']} could start: {e}"
                )
                await _release_virtual_candidate(client, selected)
                break

            modified_data = {
                **request_data,
                "model": request_model,
                "_forced_credential": selected["key"],
                "_allow_rotation": False,
                "_allow_same_key_retry": False,
                "_request_deadline": time.time() + attempt_timeout,
                "_key_already_acquired": True,
                "_acquired_model": request_model,
                "_count_as_real_request": False,
            }

            try:
                global_pool_made_upstream_attempt = True
                result = await client.acompletion(request=request, **modified_data)

                if _is_error_response(result):
                    error_type, message, status_code = _extract_error_info(result)
                    failures.append(
                        TargetFailure(
                            target=target_model,
                            reason=message,
                            error_type=error_type,
                            status_code=status_code,
                        )
                    )
                    if not _should_fallback(error_type, message, status_code):
                        return (result, target_model, len(failures) - 1)
                    continue

                if not _response_has_meaningful_completion(result):
                    failures.append(
                        TargetFailure(
                            target=target_model,
                            reason="Empty completion response",
                            error_type="server_error",
                        )
                    )
                    continue

                logger.info(
                    f"[VirtualModel] Global pool candidate {target_model} succeeded "
                    f"(fallback_count={len(failures)})"
                )
                return (result, target_model, len(failures))

            except Exception as e:
                error_type = _classify_exception_type(e)
                message = str(e).split("\n")[0]
                failures.append(
                    TargetFailure(
                        target=target_model,
                        reason=message,
                        error_type=error_type,
                        status_code=getattr(e, "status_code", None),
                    )
                )
                if not _should_fallback(
                    error_type, message, getattr(e, "status_code", None)
                ):
                    raise
                continue

        if time.monotonic() >= deadline:
            if not failures:
                failures.append(
                    TargetFailure(
                        target=virtual_model_name,
                        reason=(
                            f"Virtual model request exhausted its shared "
                            f"{overall_timeout_seconds:.2f}s budget before any target started"
                        ),
                        error_type="timeout",
                    )
                )
            error_response = _build_aggregate_error(virtual_model_name, failures)
            return (error_response, "", len(failures) - 1)
        if not global_pool_made_upstream_attempt:
            logger.warning(
                f"[VirtualModel] Global pool did not reach upstream for '{virtual_model_name}'. "
                "Falling back to legacy target routing."
            )
        else:
            logger.warning(
                f"[VirtualModel] Global pool failed for '{virtual_model_name}' after "
                f"{len(failures)} attempt(s); falling back to legacy target routing."
            )

    legacy_fallback_base_failures = len(failures)

    for idx, target in enumerate(targets):
        target_model = target.model
        logger.info(
            f"[VirtualModel] Trying target {idx + 1}/{len(targets)}: "
            f"{target_model} for virtual model '{virtual_model_name}'"
        )

        # Build modified request data with the actual target model
        modified_data = {
            **request_data,
            "model": target_model,
            "_count_as_real_request": False,
        }

        try:
            attempt_timeout = _compute_target_timeout(
                deadline,
                config.timeout_seconds,
                target_model,
            )
        except TimeoutError as e:
            logger.warning(
                f"[VirtualModel] Aggregate request budget exhausted before "
                f"target {target_model} could start: {e}"
            )
            break

        try:
            result = await _await_target_timeout(
                client.acompletion(request=request, **modified_data),
                attempt_timeout,
                target_model,
            )

            # Check for error result (RotatingClient returns dict on all-keys-exhausted)
            if _is_error_response(result):
                error_type, message, status_code = _extract_error_info(result)

                logger.warning(
                    f"[VirtualModel] Target {target_model} failed: "
                    f"{error_type} – {message[:120]}"
                )

                failure = TargetFailure(
                    target=target_model,
                    reason=message,
                    error_type=error_type,
                    status_code=status_code,
                )
                failures.append(failure)

                if not _should_fallback(error_type, message, status_code):
                    logger.error(
                        f"[VirtualModel] Non-fallbackable error '{error_type}' "
                        f"from {target_model}. Stopping."
                    )
                    # Return the error result directly, don't try more targets
                    fallback_count = (
                        len(failures) - 1
                        if legacy_fallback_base_failures > 0
                        else idx
                    )
                    return (result, target_model, fallback_count)

                continue  # Try next target

            if not _response_has_meaningful_completion(result):
                failures.append(
                    TargetFailure(
                        target=target_model,
                        reason="Empty completion response",
                        error_type="server_error",
                    )
                )
                continue

            # Success!
            logger.info(
                f"[VirtualModel] Target {target_model} succeeded "
                f"(fallback_count={idx})"
            )
            fallback_count = (
                len(failures)
                if legacy_fallback_base_failures > 0
                else idx
            )
            return (result, target_model, fallback_count)

        except Exception as e:
            # Exceptions from RotatingClient that propagated
            # (e.g. InvalidRequestError, ContextWindowExceededError)
            error_type = _classify_exception_type(e)
            message = str(e).split("\n")[0]

            logger.warning(
                f"[VirtualModel] Target {target_model} raised {type(e).__name__}: "
                f"{message[:120]}"
            )

            failure = TargetFailure(
                target=target_model,
                reason=message,
                error_type=error_type,
                status_code=getattr(e, "status_code", None),
            )
            failures.append(failure)

            if not _should_fallback(
                error_type, message, getattr(e, "status_code", None)
            ):
                logger.error(
                    f"[VirtualModel] Non-fallbackable exception from "
                    f"{target_model}. Propagating."
                )
                raise

            continue  # Try next target

    # All targets exhausted
    if not failures:
        failures.append(
            TargetFailure(
                target=virtual_model_name,
                reason=(
                    f"Virtual model request exhausted its shared "
                    f"{overall_timeout_seconds:.2f}s budget before any target started"
                ),
                error_type="timeout",
            )
        )
    logger.error(
        f"[VirtualModel] All {len(failures)} target(s) failed for "
        f"virtual model '{virtual_model_name}'"
    )
    error_response = _build_aggregate_error(virtual_model_name, failures)
    return (error_response, "", len(failures) - 1)


# ---------------------------------------------------------------------------
# Streaming execution
# ---------------------------------------------------------------------------
async def execute_virtual_completion_streaming(
    client: Any,
    request: Any,
    request_data: dict,
    virtual_model_name: str,
) -> Tuple[AsyncGenerator[str, None], str, int]:
    """
    Execute a streaming completion for a virtual model.

    Returns:
        (stream_generator, actual_target_model, fallback_count)

    The returned generator yields SSE data chunks.  If all targets fail,
    the generator yields an aggregate error chunk.
    """
    config = get_virtual_model(virtual_model_name)
    if config is None:
        raise ValueError(f"Virtual model '{virtual_model_name}' not found in registry")

    targets = resolve_targets(config)
    if not targets:
        raise ValueError(
            f"Virtual model '{virtual_model_name}' has no enabled targets"
        )

    # We need to wrap the whole fallback logic inside an async generator
    # so that FastAPI can stream the response.
    actual_target = ""
    fallback_count = 0
    overall_timeout_seconds = _resolve_overall_timeout_seconds(client, config)
    deadline = time.monotonic() + overall_timeout_seconds
    _note_real_virtual_request(client)
    use_global_pool = _should_use_global_pool(client, config)
    candidate_specs = (
        _build_global_candidate_specs(client, config.enabled_targets)
        if use_global_pool
        else []
    )

    async def _streaming_with_fallback() -> AsyncGenerator[str, None]:
        nonlocal actual_target, fallback_count
        failures: List[TargetFailure] = []

        if use_global_pool:
            attempted_candidates: set[Tuple[str, str]] = set()
            global_pool_made_upstream_attempt = False
            global_pool_fallback_reserve = min(
                2.0, max(0.2, float(overall_timeout_seconds) * 0.2)
            )
            global_pool_deadline = max(
                time.monotonic(), deadline - global_pool_fallback_reserve
            )
            if not candidate_specs:
                failures.append(
                    TargetFailure(
                        target=virtual_model_name,
                        reason="No enabled targets with usable credentials",
                        error_type="virtual_model_exhausted",
                    )
                )
            while time.monotonic() < global_pool_deadline and candidate_specs:
                remaining_specs = [
                    spec
                    for spec in candidate_specs
                    if (spec["key"], spec["model"]) not in attempted_candidates
                ]
                if not remaining_specs:
                    break

                try:
                    selected = await client.usage_manager.acquire_virtual_candidate(
                        remaining_specs,
                        deadline=_monotonic_to_wall_deadline(deadline),
                        strategy=config.strategy,
                        top_n=5,
                    )
                except Exception as e:
                    if _should_retry_candidate_acquire_error(e, deadline=deadline):
                        await asyncio.sleep(
                            min(0.05, max(0.0, deadline - time.monotonic()))
                        )
                        continue
                    failures.append(
                        TargetFailure(
                            target=virtual_model_name,
                            reason=str(e),
                            error_type="proxy_busy",
                        )
                    )
                    break
                target_model = selected["target_model"]
                request_model = selected.get("request_model", selected["target_model"])
                attempted_candidates.add((selected["key"], request_model))

                try:
                    attempt_timeout = _compute_target_timeout(
                        deadline,
                        config.timeout_seconds,
                        target_model,
                    )
                except TimeoutError as e:
                    logger.warning(
                        f"[VirtualModel] Streaming aggregate budget exhausted before "
                        f"candidate {target_model} could start: {e}"
                    )
                    await _release_virtual_candidate(client, selected)
                    break

                modified_data = {
                    **request_data,
                    "model": request_model,
                    "_forced_credential": selected["key"],
                    "_allow_rotation": False,
                    "_allow_same_key_retry": False,
                    "_request_deadline": time.time() + attempt_timeout,
                    "_key_already_acquired": True,
                    "_acquired_model": request_model,
                    "_count_as_real_request": False,
                }

                try:
                    global_pool_made_upstream_attempt = True
                    stream = _iter_stream_with_initial_timeout(
                        client.acompletion(request=request, **modified_data),
                        attempt_timeout,
                        target_model,
                    )

                    pending_chunks: List[str] = []
                    found_error = False
                    error_type = "unknown"
                    error_message = ""
                    has_meaningful_output = False

                    async for chunk in stream:
                        if chunk.strip().startswith("data:"):
                            data_content = chunk[len("data:"):].strip()
                            if data_content == "[DONE]":
                                if found_error:
                                    break
                                if not has_meaningful_output:
                                    failures.append(
                                        TargetFailure(
                                            target=target_model,
                                            reason="Empty streaming response",
                                            error_type="server_error",
                                        )
                                    )
                                    break
                                for buffered in pending_chunks:
                                    yield buffered
                                pending_chunks.clear()
                                yield chunk
                                actual_target = target_model
                                fallback_count = len(failures)
                                return
                            try:
                                parsed = json.loads(data_content)
                                if "error" in parsed and not has_meaningful_output:
                                    found_error = True
                                    err = parsed.get("error", {})
                                    error_type = err.get("type", "unknown")
                                    error_message = err.get("message", str(err))
                                    status_code = (
                                        err.get("code")
                                        if isinstance(err.get("code"), int)
                                        else None
                                    )
                                    if not _should_fallback(
                                        error_type, error_message, status_code
                                    ):
                                        yield chunk
                                        actual_target = target_model
                                        fallback_count = len(failures)
                                        return
                                    continue
                                pending_chunks.append(chunk)
                                if _stream_chunk_has_meaningful_output(parsed):
                                    has_meaningful_output = True
                                    for buffered in pending_chunks:
                                        yield buffered
                                    pending_chunks.clear()
                                    async for remaining in stream:
                                        yield remaining
                                    actual_target = target_model
                                    fallback_count = len(failures)
                                    return
                            except json.JSONDecodeError:
                                has_meaningful_output = True
                                pending_chunks.append(chunk)
                                for buffered in pending_chunks:
                                    yield buffered
                                pending_chunks.clear()
                                async for remaining in stream:
                                    yield remaining
                                actual_target = target_model
                                fallback_count = len(failures)
                                return
                        else:
                            pending_chunks.append(chunk)

                    if found_error:
                        failures.append(
                            TargetFailure(
                                target=target_model,
                                reason=error_message,
                                error_type=error_type,
                            )
                        )
                        continue

                    failures.append(
                        TargetFailure(
                            target=target_model,
                            reason="Empty streaming response",
                            error_type="server_error",
                        )
                    )
                    continue

                except Exception as e:
                    exc_error_type = _classify_exception_type(e)
                    failures.append(
                        TargetFailure(
                            target=target_model,
                            reason=str(e).split("\n")[0],
                            error_type=exc_error_type,
                            status_code=getattr(e, "status_code", None),
                        )
                    )
                    if not _should_fallback(
                        exc_error_type, str(e), getattr(e, "status_code", None)
                    ):
                        raise
                    continue

            if time.monotonic() >= deadline:
                if not failures:
                    failures.append(
                        TargetFailure(
                            target=virtual_model_name,
                            reason=(
                                f"Virtual model request exhausted its shared "
                                f"{overall_timeout_seconds:.2f}s budget before any target started"
                            ),
                            error_type="timeout",
                        )
                    )
                error_response = _build_aggregate_error(virtual_model_name, failures)
                yield f"data: {json.dumps(error_response)}\n\n"
                yield "data: [DONE]\n\n"
                return
            if not global_pool_made_upstream_attempt:
                logger.warning(
                    f"[VirtualModel] Streaming global pool did not reach upstream for "
                    f"'{virtual_model_name}'. Falling back to legacy target routing."
                )
            else:
                logger.warning(
                    f"[VirtualModel] Streaming global pool failed for '{virtual_model_name}' "
                    f"after {len(failures)} attempt(s); falling back to legacy target routing."
                )

        legacy_fallback_base_failures = len(failures)

        for idx, target in enumerate(targets):
            target_model = target.model
            logger.info(
                f"[VirtualModel] Streaming: trying target {idx + 1}/{len(targets)}: "
                f"{target_model} for '{virtual_model_name}'"
            )

            modified_data = {
                **request_data,
                "model": target_model,
                "_count_as_real_request": False,
            }

            try:
                attempt_timeout = _compute_target_timeout(
                    deadline,
                    config.timeout_seconds,
                    target_model,
                )
            except TimeoutError as e:
                logger.warning(
                    f"[VirtualModel] Streaming aggregate budget exhausted before "
                    f"target {target_model} could start: {e}"
                )
                break

            try:
                stream = _iter_stream_with_initial_timeout(
                    client.acompletion(request=request, **modified_data),
                    attempt_timeout,
                    target_model,
                )

                # Buffer initial chunks to detect immediate errors
                pending_chunks: List[str] = []
                found_error = False
                error_type = "unknown"
                error_message = ""
                has_meaningful_output = False

                async for chunk in stream:
                    # Check if this chunk is an error response
                    if chunk.strip().startswith("data:"):
                        data_content = chunk[len("data:"):].strip()
                        if data_content == "[DONE]":
                            if found_error:
                                # Error stream complete – try next target
                                break
                            else:
                                if not has_meaningful_output:
                                    failures.append(
                                        TargetFailure(
                                            target=target_model,
                                            reason="Empty streaming response",
                                            error_type="server_error",
                                        )
                                    )
                                    break
                                for buffered in pending_chunks:
                                    yield buffered
                                pending_chunks.clear()
                                yield chunk
                                actual_target = target_model
                                fallback_count = (
                                    len(failures)
                                    if legacy_fallback_base_failures > 0
                                    else idx
                                )
                                return
                        else:
                            try:
                                parsed = json.loads(data_content)
                                if "error" in parsed and not has_meaningful_output:
                                    # First meaningful chunk is an error
                                    found_error = True
                                    err = parsed.get("error", {})
                                    error_type = err.get("type", "unknown")
                                    error_message = err.get("message", str(err))
                                    status_code = (
                                        err.get("code")
                                        if isinstance(err.get("code"), int)
                                        else None
                                    )

                                    if not _should_fallback(
                                        error_type, error_message, status_code
                                    ):
                                        # Non-fallbackable – forward to client
                                        logger.error(
                                            f"[VirtualModel] Streaming: non-fallbackable "
                                            f"error from {target_model}"
                                        )
                                        yield chunk
                                        actual_target = target_model
                                        fallback_count = (
                                            len(failures)
                                            if legacy_fallback_base_failures > 0
                                            else idx
                                        )
                                        return

                                    # Record failure, will try next target
                                    continue
                                else:
                                    pending_chunks.append(chunk)
                                    if _stream_chunk_has_meaningful_output(parsed):
                                        has_meaningful_output = True
                                        for buffered in pending_chunks:
                                            yield buffered
                                        pending_chunks.clear()
                                        async for remaining in stream:
                                            yield remaining
                                        actual_target = target_model
                                        fallback_count = (
                                            len(failures)
                                            if legacy_fallback_base_failures > 0
                                            else idx
                                        )
                                        return
                            except json.JSONDecodeError:
                                # Not valid JSON, treat as content
                                has_meaningful_output = True
                                pending_chunks.append(chunk)
                                for buffered in pending_chunks:
                                    yield buffered
                                pending_chunks.clear()
                                async for remaining in stream:
                                    yield remaining
                                actual_target = target_model
                                fallback_count = (
                                    len(failures)
                                    if legacy_fallback_base_failures > 0
                                    else idx
                                )
                                return
                    else:
                        # Non-data line (empty, comments) – buffer it
                        pending_chunks.append(chunk)

                # Stream ended – if we found an error, record and continue
                if found_error:
                    logger.warning(
                        f"[VirtualModel] Streaming: target {target_model} "
                        f"error: {error_type}"
                    )
                    failures.append(
                        TargetFailure(
                            target=target_model,
                            reason=error_message,
                            error_type=error_type,
                        )
                    )
                    continue

                failures.append(
                    TargetFailure(
                        target=target_model,
                        reason="Empty streaming response",
                        error_type="server_error",
                    )
                )
                continue

            except Exception as e:
                exc_error_type = _classify_exception_type(e)
                message = str(e).split("\n")[0]

                logger.warning(
                    f"[VirtualModel] Streaming: target {target_model} raised "
                    f"{type(e).__name__}: {message[:120]}"
                )

                failures.append(
                    TargetFailure(
                        target=target_model,
                        reason=message,
                        error_type=exc_error_type,
                        status_code=getattr(e, "status_code", None),
                    )
                )

                if not _should_fallback(
                    exc_error_type, message, getattr(e, "status_code", None)
                ):
                    raise

                continue

        # All targets exhausted
        if not failures:
            failures.append(
                TargetFailure(
                    target=virtual_model_name,
                    reason=(
                        f"Virtual model request exhausted its shared "
                        f"{overall_timeout_seconds:.2f}s budget before any target started"
                    ),
                    error_type="timeout",
                )
            )
        logger.error(
            f"[VirtualModel] Streaming: all {len(failures)} target(s) failed "
            f"for '{virtual_model_name}'"
        )
        error_response = _build_aggregate_error(virtual_model_name, failures)
        yield f"data: {json.dumps(error_response)}\n\n"
        yield "data: [DONE]\n\n"

    gen = _streaming_with_fallback()
    return (gen, actual_target, fallback_count)


# ---------------------------------------------------------------------------
# Exception classifier (lightweight, for aggregate-level use)
# ---------------------------------------------------------------------------
def _classify_exception_type(e: Exception) -> str:
    """
    Lightweight exception classification for aggregate-level fallback decisions.
    Maps common exception types to error_type strings.
    """
    type_name = type(e).__name__.lower()

    # litellm exception types
    if "invalidrequest" in type_name or "badrequest" in type_name:
        return "invalid_request"
    if "contextwindow" in type_name:
        return "context_window_exceeded"
    if "authentication" in type_name:
        return "authentication"
    if "ratelimit" in type_name:
        return "rate_limit"
    if "timeout" in type_name:
        return "timeout"
    if "connection" in type_name:
        return "api_connection"
    if "serviceunavailable" in type_name or "internalserver" in type_name:
        return "server_error"

    # Check status_code attribute
    status = getattr(e, "status_code", None)
    if status:
        if status == 400:
            return "invalid_request"
        if status == 401:
            return "authentication"
        if status == 429:
            return "rate_limit"
        if status >= 500:
            return "server_error"

    return "unknown"
