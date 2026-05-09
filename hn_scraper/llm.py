"""All LLM calls in this project go through this module.

Never call the Anthropic SDK directly from product code. Doing so
bypasses the cost/latency telemetry that drives the demo's headline
comparison ("graduated path is N× cheaper than naive path"). Every
call writes one JSONL line to ``data/logs/llm_calls.jsonl`` with
metadata only — message content is never logged (privacy).

Public surface: :func:`call`. The Anthropic client is lazily
constructed once per process via :func:`_client`.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from hn_scraper.config import get_settings

LOG_PATH = Path("data/logs/llm_calls.jsonl")

_client_instance: Anthropic | None = None
_logger = logging.getLogger(__name__)

# Per-process current run id. Each CLI subcommand calls
# ``set_current_run_id(uuid.uuid4().hex)`` at startup so every
# downstream ``llm.call`` is tagged with the same id. ``compare``
# groups by ``run_id`` to pick the latest run per slice cleanly,
# avoiding the time-gap heuristic's false grouping of back-to-back
# CLI invocations that share a slice_label.
_current_run_id: str | None = None


def set_current_run_id(run_id: str | None) -> None:
    global _current_run_id
    _current_run_id = run_id


def get_current_run_id() -> str | None:
    return _current_run_id


def _client() -> Anthropic:
    global _client_instance
    if _client_instance is None:
        # max_retries=15 — the graduated path bursts hundreds of
        # parallel calls and routinely trips Sonnet 4.6's per-org
        # 50 RPM / 30K input-tokens-per-minute rate limits. The SDK
        # honors Retry-After headers, so high retries means in-thread
        # backoff rather than dropped extractions.
        _client_instance = Anthropic(
            api_key=get_settings().anthropic_api_key,
            max_retries=15,
        )
    return _client_instance


def _write_telemetry(record: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def call(
    *,
    prompt_name: str,
    model: str,
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int = 1024,
    slice_label: str = "scaffolding",
    **extra: Any,
) -> Any:
    """Invoke ``messages.create`` and emit one JSONL telemetry line.

    ``slice_label`` lets us split cost/latency between ``"naive"``,
    ``"graduated"``, and ad-hoc ``"scaffolding"`` calls when we
    later compute the demo's headline numbers.
    """
    started = time.perf_counter()
    timestamp = datetime.now(UTC).isoformat(timespec="milliseconds")

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system is not None:
        kwargs["system"] = system
    kwargs.update(extra)

    run_id = _current_run_id
    try:
        response = _client().messages.create(**kwargs)
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        record = {
            "timestamp": timestamp,
            "prompt_name": prompt_name,
            "model": model,
            "slice_label": slice_label,
            "run_id": run_id,
            "input_tokens": None,
            "output_tokens": None,
            "latency_ms": latency_ms,
            "status": "error",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        _write_telemetry(record)
        _logger.info(
            "llm.call prompt=%s model=%s status=error latency_ms=%d error=%s",
            prompt_name,
            model,
            latency_ms,
            type(exc).__name__,
        )
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None) if usage else None
    output_tokens = getattr(usage, "output_tokens", None) if usage else None

    record = {
        "timestamp": timestamp,
        "prompt_name": prompt_name,
        "model": model,
        "slice_label": slice_label,
        "run_id": run_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "status": "ok",
    }
    _write_telemetry(record)
    _logger.info(
        "llm.call prompt=%s model=%s status=ok in=%s out=%s latency_ms=%d",
        prompt_name,
        model,
        input_tokens,
        output_tokens,
        latency_ms,
    )
    return response
