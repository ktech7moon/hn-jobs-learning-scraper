"""Slice 2 unit tests.

No network. No live LLM calls. Anthropic ``llm.call`` and ``requests``
HTTP are mocked via monkeypatch. Tests cover the deterministic
helpers: HTML-to-plain-text, firebase fetch_kids filtering, the
learner's strategy verification helper, the dossier renderer, and
the compare aggregator.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hn_scraper import compare, config, firebase_api, learner, llm


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    config.get_settings.cache_clear()
    log = tmp_path / "llm_calls.jsonl"
    monkeypatch.setattr(llm, "LOG_PATH", log)
    yield log
    config.get_settings.cache_clear()


# ---------- firebase_api.comment_text_to_plain ----------


def test_comment_text_to_plain_decodes_entities_and_paragraphs():
    raw = "Acme | SRE | Berlin<p>We&#x27;re hiring &amp; growing.<p>Stack: <i>Python</i>, k8s."
    out = firebase_api.comment_text_to_plain(raw)
    assert "We're hiring & growing." in out
    assert "Python" in out
    assert "<i>" not in out
    assert "<p>" not in out
    # Paragraph break renders as a blank line between sections.
    assert "\n\n" in out


def test_comment_text_to_plain_handles_empty_and_none():
    assert firebase_api.comment_text_to_plain("") == ""
    assert firebase_api.comment_text_to_plain(None) == ""  # type: ignore[arg-type]


def test_comment_text_to_plain_strips_tags_but_keeps_link_text():
    raw = 'Acme<p>Apply: <a href="mailto:hi@acme.example">hi@acme.example</a>'
    out = firebase_api.comment_text_to_plain(raw)
    assert "hi@acme.example" in out
    assert "<a" not in out


# ---------- firebase_api.fetch_kids ----------


def _fake_response(payload: Any) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=200,
        json=lambda: payload,
        raise_for_status=lambda: None,
    )


def test_fetch_kids_filters_deleted_dead_and_empty(monkeypatch):
    """fetch_kids should skip items with deleted/dead/empty text."""
    parent = {"id": 100, "kids": [1, 2, 3, 4, 5]}
    items = {
        100: parent,
        1: {"id": 1, "text": "real posting"},
        2: {"id": 2, "text": "another posting"},
        3: {"id": 3, "deleted": True},
        4: {"id": 4, "dead": True, "text": "killed"},
        5: {"id": 5, "text": ""},
    }

    class FakeSession:
        headers: dict[str, str] = {}

        def get(self, url, timeout):
            # last path segment, strip ".json"
            kid = int(url.rsplit("/", 1)[-1].split(".")[0])
            return _fake_response(items[kid])

    monkeypatch.setattr(firebase_api, "_session", lambda: FakeSession())
    visible = firebase_api.fetch_kids(100)
    visible_ids = [v["id"] for v in visible]
    assert visible_ids == [1, 2]


def test_fetch_kids_preserves_kid_order(monkeypatch):
    """Returned list mirrors the parent's kids array order, not future arrival order."""
    parent = {"id": 99, "kids": [10, 20, 30]}
    items = {
        99: parent,
        10: {"id": 10, "text": "first"},
        20: {"id": 20, "text": "second"},
        30: {"id": 30, "text": "third"},
    }

    class FakeSession:
        headers: dict[str, str] = {}

        def get(self, url, timeout):
            kid = int(url.rsplit("/", 1)[-1].split(".")[0])
            return _fake_response(items[kid])

    monkeypatch.setattr(firebase_api, "_session", lambda: FakeSession())
    out = firebase_api.fetch_kids(99)
    assert [o["id"] for o in out] == [10, 20, 30]


# ---------- learner._verify_strategy ----------


def test_verify_strategy_rejects_pattern_without_placeholder():
    result = learner._verify_strategy(
        primary_endpoint_pattern="https://example.com/static.json",
        thread_id=1,
    )
    assert result["verification_status"] == "FAIL"
    assert "placeholder" in result["reason"]


def test_verify_strategy_accepts_thread_id_placeholder(monkeypatch):
    """Round-trip: parent has 100 kids, sample kid has text → PASS."""
    parent_payload = {"id": 1, "kids": list(range(2, 102))}
    kid_payload = {"id": 2, "text": "sample"}

    class FakeSession:
        headers: dict[str, str] = {}

        def get(self, url, timeout):
            if "1.json" in url:
                return _fake_response(parent_payload)
            return _fake_response(kid_payload)

    monkeypatch.setattr(learner, "_HTTP_SESSION", FakeSession())
    result = learner._verify_strategy(
        primary_endpoint_pattern="https://example.com/item/{thread_id}.json",
        thread_id=1,
    )
    assert result["verification_status"] == "PASS"
    assert result["kids_count"] == 100


def test_verify_strategy_fails_on_missing_kids(monkeypatch):
    class FakeSession:
        headers: dict[str, str] = {}

        def get(self, url, timeout):
            return _fake_response({"id": 1, "kids": []})

    monkeypatch.setattr(learner, "_HTTP_SESSION", FakeSession())
    result = learner._verify_strategy(
        primary_endpoint_pattern="https://example.com/item/{thread_id}.json",
        thread_id=1,
    )
    assert result["verification_status"] == "FAIL"
    assert "kids list" in result["reason"]


# ---------- learner.Dossier rendering ----------


def test_dossier_to_markdown_handles_empty_dossier():
    d = learner.Dossier(thread_id=42, started_at="2026-05-08T00:00:00")
    md = d.to_markdown()
    assert "thread 42" in md
    assert "NOT REACHED" in md
    assert "_No structured findings recorded._" in md


def test_dossier_to_markdown_renders_findings_and_calls():
    d = learner.Dossier(thread_id=42, started_at="2026-05-08T00:00:00")
    d.findings.append(
        learner.Finding(iteration=1, category="endpoint", text="found a thing")
    )
    d.tool_calls.append(
        learner.ToolCallRecord(
            iteration=1,
            tool="http_get",
            input={"url": "https://example.com/x"},
            result_summary="status=200 body_len=100",
        )
    )
    d.iterations_used = 1
    md = d.to_markdown()
    assert "iter 1 / endpoint" in md
    assert "found a thing" in md
    assert "https://example.com/x" in md
    assert "status=200" in md


# ---------- learner._tool_record_finding ----------


def test_tool_record_finding_rejects_invalid_category():
    d = learner.Dossier(thread_id=1, started_at="now")
    res = learner._tool_record_finding(
        dossier=d, iteration=1, category="bogus", text="anything"
    )
    assert "error" in res
    assert d.findings == []


def test_tool_record_finding_appends_with_valid_input():
    d = learner.Dossier(thread_id=1, started_at="now")
    res = learner._tool_record_finding(
        dossier=d, iteration=2, category="endpoint", text="real finding"
    )
    assert res["ok"] is True
    assert len(d.findings) == 1
    assert d.findings[0].category == "endpoint"


# ---------- compare.aggregation ----------


def test_compare_aggregates_by_slice(tmp_path: Path):
    log = tmp_path / "calls.jsonl"
    rows = [
        {
            "timestamp": "2026-05-08T01:00:00.000+00:00",
            "slice_label": "naive",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1_000_000,
            "output_tokens": 200_000,
            "latency_ms": 1200,
            "status": "ok",
        },
        {
            "timestamp": "2026-05-08T01:01:00.000+00:00",
            "slice_label": "graduated",
            "model": "claude-sonnet-4-6",
            "input_tokens": 500_000,
            "output_tokens": 100_000,
            "latency_ms": 1500,
            "status": "ok",
        },
        {
            "timestamp": "2026-05-08T01:02:00.000+00:00",
            "slice_label": "graduated",
            "model": "claude-sonnet-4-6",
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 50,
            "status": "error",
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    rows_loaded = compare._read_log(log_path=log, since=None)
    by_slice = compare._aggregate_by_slice(rows_loaded)
    assert by_slice["naive"]["calls_ok"] == 1
    assert by_slice["naive"]["cost_usd"] == pytest.approx(1.0 * 1 + 0.2 * 5, rel=1e-6)
    assert by_slice["graduated"]["calls_ok"] == 1
    assert by_slice["graduated"]["calls_err"] == 1
    # Sonnet pricing 3/15 per Mtok: 0.5*3 + 0.1*15 = 1.5 + 1.5 = 3.0
    assert by_slice["graduated"]["cost_usd"] == pytest.approx(3.0, rel=1e-6)


def test_compare_since_filter_drops_old_rows(tmp_path: Path):
    log = tmp_path / "calls.jsonl"
    rows = [
        {
            "timestamp": "2026-05-07T00:00:00.000+00:00",
            "slice_label": "naive",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1000,
            "output_tokens": 100,
            "latency_ms": 1000,
            "status": "ok",
        },
        {
            "timestamp": "2026-05-08T00:00:00.000+00:00",
            "slice_label": "naive",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1000,
            "output_tokens": 100,
            "latency_ms": 1000,
            "status": "ok",
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    rows_after = compare._read_log(
        log_path=log, since="2026-05-07T12:00:00.000+00:00"
    )
    assert len(rows_after) == 1
    assert rows_after[0]["timestamp"].startswith("2026-05-08")


def test_compare_count_jobs_in_digest(tmp_path: Path):
    p = tmp_path / "fake-digest.md"
    p.write_text(
        "# Title\n"
        "**Source:** https://example.com\n"
        "**Wall-clock:** 1.0 s\n"
        "**Jobs extracted:** 42 (out of 100 top-level comments)\n\n"
        "## Remote (1 jobs)\n"
    )
    assert compare._count_jobs_in(p) == 42


def test_compare_count_jobs_returns_none_when_missing(tmp_path: Path):
    p = tmp_path / "no-jobs-line.md"
    p.write_text("# Title\nno jobs line here\n")
    assert compare._count_jobs_in(p) is None


# ---------- compare auto-scope to latest run ----------


def _row(
    ts: str,
    sl: str,
    model: str = "claude-haiku-4-5-20251001",
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "timestamp": ts,
        "slice_label": sl,
        "model": model,
        "input_tokens": 100,
        "output_tokens": 20,
        "latency_ms": 500,
        "status": "ok",
    }
    if run_id is not None:
        rec["run_id"] = run_id
    return rec


def test_latest_run_window_picks_most_recent_contiguous_block():
    rows = [
        # Older "naive" run
        _row("2026-05-08T10:00:00.000+00:00", "naive"),
        _row("2026-05-08T10:00:01.000+00:00", "naive"),
        _row("2026-05-08T10:00:02.000+00:00", "naive"),
        # Big gap (>5 min)
        _row("2026-05-08T11:00:00.000+00:00", "naive"),
        _row("2026-05-08T11:00:01.000+00:00", "naive"),
    ]
    win = compare._latest_run_window(rows, slice_label="naive")
    assert win == ("2026-05-08T11:00:00.000+00:00", "2026-05-08T11:00:01.000+00:00")


def test_latest_run_window_tolerates_in_run_stalls_below_threshold():
    """A 4-min stall (e.g. rate-limit retry) is within the 5-min default — keep grouped."""
    rows = [
        _row("2026-05-08T10:00:00.000+00:00", "graduated"),
        _row("2026-05-08T10:04:00.000+00:00", "graduated"),  # 4-min gap, still same run
        _row("2026-05-08T10:04:30.000+00:00", "graduated"),
    ]
    win = compare._latest_run_window(rows, slice_label="graduated")
    assert win == (
        "2026-05-08T10:00:00.000+00:00",
        "2026-05-08T10:04:30.000+00:00",
    )


def test_latest_run_window_handles_duplicate_timestamps():
    """Two parallel workers can finish in the same millisecond; sort must not
    fall through to comparing the dict payloads."""
    rows = [
        _row("2026-05-08T10:00:00.000+00:00", "graduated"),
        _row("2026-05-08T10:00:00.000+00:00", "graduated"),
        _row("2026-05-08T10:00:01.000+00:00", "graduated"),
    ]
    win = compare._latest_run_window(rows, slice_label="graduated")
    assert win == (
        "2026-05-08T10:00:00.000+00:00",
        "2026-05-08T10:00:01.000+00:00",
    )


def test_latest_run_window_returns_none_when_slice_missing():
    rows = [_row("2026-05-08T10:00:00.000+00:00", "naive")]
    assert compare._latest_run_window(rows, slice_label="learn") is None


def test_scope_to_latest_runs_keeps_only_latest_per_slice():
    rows = [
        # naive: old run
        _row("2026-05-08T09:00:00.000+00:00", "naive"),
        # naive: latest run
        _row("2026-05-08T11:00:00.000+00:00", "naive"),
        _row("2026-05-08T11:00:01.000+00:00", "naive"),
        # graduated: only run
        _row("2026-05-08T11:30:00.000+00:00", "graduated"),
    ]
    kept, windows = compare._scope_to_latest_runs(rows)
    kept_naive = [r for r in kept if r["slice_label"] == "naive"]
    kept_grad = [r for r in kept if r["slice_label"] == "graduated"]
    assert len(kept_naive) == 2
    assert len(kept_grad) == 1
    # Older naive row dropped
    assert all(r["timestamp"].startswith("2026-05-08T11:") for r in kept_naive)
    assert "naive" in windows
    assert "graduated" in windows
    assert windows["naive"][0] == "2026-05-08T11:00:00.000+00:00"


def test_scope_to_latest_runs_empty_when_no_rows():
    kept, windows = compare._scope_to_latest_runs([])
    assert kept == []
    assert windows == {}


def test_scope_to_latest_runs_prefers_run_id_over_time_gap():
    """Two back-to-back runs <300s apart with distinct run_ids must NOT merge."""
    rows = [
        # Older graduated run
        _row("2026-05-08T10:00:00.000+00:00", "graduated", run_id="aaa111"),
        _row("2026-05-08T10:00:30.000+00:00", "graduated", run_id="aaa111"),
        # Newer graduated run, only 60s after the older one ended (within RUN_GAP_SECONDS)
        _row("2026-05-08T10:01:30.000+00:00", "graduated", run_id="bbb222"),
        _row("2026-05-08T10:02:00.000+00:00", "graduated", run_id="bbb222"),
    ]
    kept, windows = compare._scope_to_latest_runs(rows)
    # Time-gap heuristic alone would have merged these (60s gap < 300s).
    # run_id grouping must keep ONLY the newer one.
    assert all(r["run_id"] == "bbb222" for r in kept)
    assert len(kept) == 2
    assert windows["graduated"] == (
        "2026-05-08T10:01:30.000+00:00",
        "2026-05-08T10:02:00.000+00:00",
    )


def test_scope_to_latest_runs_falls_back_to_time_gap_for_legacy_rows():
    """Rows without run_id (legacy) still get the time-gap heuristic."""
    rows = [
        _row("2026-05-08T09:00:00.000+00:00", "naive"),  # no run_id
        # 1-hour gap → split run
        _row("2026-05-08T10:00:00.000+00:00", "naive"),  # no run_id
        _row("2026-05-08T10:00:30.000+00:00", "naive"),  # no run_id
    ]
    kept, windows = compare._scope_to_latest_runs(rows)
    assert len(kept) == 2
    assert all(r["timestamp"].startswith("2026-05-08T10:") for r in kept)
    assert windows["naive"][0] == "2026-05-08T10:00:00.000+00:00"
