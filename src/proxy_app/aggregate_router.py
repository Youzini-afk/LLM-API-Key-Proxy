# SPDX-License-Identifier: MIT
# Aggregate Router – cross-provider target fallback for virtual models.
#
# This module sits *above* RotatingClient.  RotatingClient handles key
# rotation inside a single provider; AggregateRouter handles target
# rotation across multiple providers for a given virtual model.

import asyncio
import json
import logging
import time
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


def _should_fallback(error_type: str) -> bool:
    """Decide whether to try the next target for this error type."""
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
    try:
        first_chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_seconds)
    except StopAsyncIteration:
        return
    except TimeoutError as exc:
        raise TimeoutError(
            f"Virtual model target '{target_model}' produced no stream data within {timeout_seconds:.2f}s"
        ) from exc

    yield first_chunk
    async for chunk in iterator:
        yield chunk


def _build_aggregate_error(
    virtual_model: str, failures: List[TargetFailure]
) -> dict:
    """Build a unified error response when all targets have failed."""
    return {
        "error": {
            "message": f"All route targets failed for virtual model '{virtual_model}'",
            "type": "virtual_model_exhausted",
            "details": {
                "virtual_model": virtual_model,
                "targets_tried": len(failures),
                "failures": [f.to_dict() for f in failures],
            },
        }
    }


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

    for idx, target in enumerate(targets):
        target_model = target.model
        logger.info(
            f"[VirtualModel] Trying target {idx + 1}/{len(targets)}: "
            f"{target_model} for virtual model '{virtual_model_name}'"
        )

        # Build modified request data with the actual target model
        modified_data = {**request_data, "model": target_model}

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

                if not _should_fallback(error_type):
                    logger.error(
                        f"[VirtualModel] Non-fallbackable error '{error_type}' "
                        f"from {target_model}. Stopping."
                    )
                    # Return the error result directly, don't try more targets
                    return (result, target_model, idx)

                continue  # Try next target

            # Success!
            logger.info(
                f"[VirtualModel] Target {target_model} succeeded "
                f"(fallback_count={idx})"
            )
            return (result, target_model, idx)

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

            if not _should_fallback(error_type):
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

    async def _streaming_with_fallback() -> AsyncGenerator[str, None]:
        nonlocal actual_target, fallback_count
        failures: List[TargetFailure] = []

        for idx, target in enumerate(targets):
            target_model = target.model
            logger.info(
                f"[VirtualModel] Streaming: trying target {idx + 1}/{len(targets)}: "
                f"{target_model} for '{virtual_model_name}'"
            )

            modified_data = {**request_data, "model": target_model}

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
                buffer: List[str] = []
                found_error = False
                error_type = "unknown"
                error_message = ""

                async for chunk in stream:
                    # Check if this chunk is an error response
                    if chunk.strip().startswith("data:"):
                        data_content = chunk[len("data:"):].strip()
                        if data_content == "[DONE]":
                            if found_error:
                                # Error stream complete – try next target
                                break
                            else:
                                # Normal end of stream
                                # First yield any buffered chunks
                                for buffered in buffer:
                                    yield buffered
                                buffer.clear()
                                yield chunk
                                actual_target = target_model
                                fallback_count = idx
                                return
                        else:
                            try:
                                parsed = json.loads(data_content)
                                if "error" in parsed and not buffer:
                                    # First meaningful chunk is an error
                                    found_error = True
                                    err = parsed.get("error", {})
                                    error_type = err.get("type", "unknown")
                                    error_message = err.get("message", str(err))

                                    if not _should_fallback(error_type):
                                        # Non-fallbackable – forward to client
                                        logger.error(
                                            f"[VirtualModel] Streaming: non-fallbackable "
                                            f"error from {target_model}"
                                        )
                                        yield chunk
                                        actual_target = target_model
                                        fallback_count = idx
                                        return

                                    # Record failure, will try next target
                                    continue
                                else:
                                    # Real content – flush buffer and continue
                                    for buffered in buffer:
                                        yield buffered
                                    buffer.clear()
                                    yield chunk
                                    # From here on, stream directly
                                    async for remaining in stream:
                                        yield remaining
                                    actual_target = target_model
                                    fallback_count = idx
                                    return
                            except json.JSONDecodeError:
                                # Not valid JSON, treat as content
                                for buffered in buffer:
                                    yield buffered
                                buffer.clear()
                                yield chunk
                                async for remaining in stream:
                                    yield remaining
                                actual_target = target_model
                                fallback_count = idx
                                return
                    else:
                        # Non-data line (empty, comments) – buffer it
                        buffer.append(chunk)

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

                # Stream ended without data (edge case) – treat as success
                for buffered in buffer:
                    yield buffered
                actual_target = target_model
                fallback_count = idx
                return

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

                if not _should_fallback(exc_error_type):
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
