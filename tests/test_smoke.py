"""Smoke tests.

Two checks for the scaffolding phase:

1. ``hn_scraper`` imports and exposes a string ``__version__``.
2. :func:`hn_scraper.llm.call` writes a JSONL telemetry line and
   never reaches the real Anthropic API. We monkeypatch the
   lazy client factory so no network call happens.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import hn_scraper
from hn_scraper import llm


def test_version_is_string() -> None:
    assert isinstance(hn_scraper.__version__, str)
    assert hn_scraper.__version__


def test_llm_call_writes_telemetry(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "llm_calls.jsonl"
    monkeypatch.setattr(llm, "LOG_PATH", log_path)

    fake_response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=12, output_tokens=34),
        content=[SimpleNamespace(type="text", text="ok")],
    )
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: fake_response))
    monkeypatch.setattr(llm, "_client", lambda: fake_client)

    response = llm.call(
        prompt_name="smoke",
        model="claude-haiku-4-5-20251001",
        messages=[{"role": "user", "content": "hi"}],
        slice_label="scaffolding",
    )

    assert response is fake_response
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "ok"
    assert record["prompt_name"] == "smoke"
    assert record["slice_label"] == "scaffolding"
    assert record["input_tokens"] == 12
    assert record["output_tokens"] == 34
    assert record["model"] == "claude-haiku-4-5-20251001"
