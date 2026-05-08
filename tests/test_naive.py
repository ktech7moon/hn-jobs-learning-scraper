"""Slice 1 unit tests.

No network. No Playwright. ``llm.call`` is mocked via monkeypatch
to return canned model output. Fixtures live in ``samples/``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from hn_scraper import config, llm, naive_scraper
from hn_scraper.models import Digest, Job, ThreadMeta

SAMPLE = json.loads(
    Path(__file__).resolve().parent.parent.joinpath("samples/sample_comment.json").read_text()
)


def _fake_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        usage=SimpleNamespace(input_tokens=200, output_tokens=80),
        content=[SimpleNamespace(type="text", text=text)],
    )


@pytest.fixture(autouse=True)
def _isolate_telemetry(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    config.get_settings.cache_clear()
    log = tmp_path / "llm_calls.jsonl"
    monkeypatch.setattr(llm, "LOG_PATH", log)
    monkeypatch.setattr(naive_scraper, "TELEMETRY_LOG", log)
    yield log
    config.get_settings.cache_clear()


def _patch_client(monkeypatch, model_text: str) -> None:
    monkeypatch.setattr(
        llm,
        "_client",
        lambda: SimpleNamespace(
            messages=SimpleNamespace(create=lambda **_: _fake_response(model_text))
        ),
    )


def test_extract_job_happy_path(monkeypatch):
    _patch_client(monkeypatch, json.dumps(SAMPLE["model_response_json"]))
    jobs = naive_scraper.extract_job(SAMPLE["comment_text"])
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Acme Robotics"
    assert job.work_mode == "hybrid"
    assert "python" in job.tech_stack
    assert job.salary_range and "€90" in job.salary_range
    assert job.raw_text == SAMPLE["comment_text"]


def test_extract_job_not_a_posting(monkeypatch):
    _patch_client(monkeypatch, '{"not_a_posting": true}')
    assert naive_scraper.extract_job("great list, thanks!") == []


def test_extract_job_strips_markdown_fences(monkeypatch):
    fenced = "```json\n" + json.dumps(SAMPLE["model_response_json"]) + "\n```"
    _patch_client(monkeypatch, fenced)
    jobs = naive_scraper.extract_job(SAMPLE["comment_text"])
    assert len(jobs) == 1
    assert jobs[0].company == "Acme Robotics"


def test_extract_job_invalid_work_mode_normalizes(monkeypatch):
    payload = dict(SAMPLE["model_response_json"], work_mode="WhoKnows")
    _patch_client(monkeypatch, json.dumps(payload))
    jobs = naive_scraper.extract_job(SAMPLE["comment_text"])
    assert len(jobs) == 1
    assert jobs[0].work_mode == "unspecified"


def test_extract_job_garbled_output_returns_empty(monkeypatch):
    _patch_client(monkeypatch, "sorry I can't help")
    assert naive_scraper.extract_job("anything") == []


def test_extract_job_top_level_list_yields_one_per_element(monkeypatch):
    base = SAMPLE["model_response_json"]
    listed = json.dumps(
        [
            base,
            dict(base, company="Beta Robotics", role="SRE", work_mode="remote"),
            dict(base, company="Gamma Robotics", role="EM", work_mode="onsite"),
        ]
    )
    _patch_client(monkeypatch, listed)
    jobs = naive_scraper.extract_job("multi-role posting text")
    assert [j.company for j in jobs] == ["Acme Robotics", "Beta Robotics", "Gamma Robotics"]
    assert [j.work_mode for j in jobs] == ["hybrid", "remote", "onsite"]
    # raw_text is the comment, not per-element.
    assert all(j.raw_text == "multi-role posting text" for j in jobs)


def test_extract_job_top_level_list_drops_invalid_elements_only(monkeypatch):
    base = SAMPLE["model_response_json"]
    # Mix: valid object, a string (not an object), a sentinel, another valid object.
    listed = json.dumps(
        [
            base,
            "not an object",
            {"not_a_posting": True},
            dict(base, company="Delta Robotics"),
        ]
    )
    _patch_client(monkeypatch, listed)
    jobs = naive_scraper.extract_job("mixed list")
    assert [j.company for j in jobs] == ["Acme Robotics", "Delta Robotics"]


def test_extract_job_top_level_scalar_returns_empty(monkeypatch):
    _patch_client(monkeypatch, "42")
    assert naive_scraper.extract_job("anything") == []


def test_compute_run_metrics_filters_by_slice_and_time(_isolate_telemetry, monkeypatch):
    log: Path = _isolate_telemetry
    cutoff = "2026-05-08T12:00:00.000+00:00"
    rows = [
        # Before cutoff — must be ignored.
        {
            "timestamp": "2026-05-08T11:59:59.000+00:00",
            "slice_label": "naive",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1000,
            "output_tokens": 1000,
            "status": "ok",
        },
        # Wrong slice — ignored.
        {
            "timestamp": "2026-05-08T12:30:00.000+00:00",
            "slice_label": "scaffolding",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1000,
            "output_tokens": 1000,
            "status": "ok",
        },
        # Counted: 1M in @ $1, 1M out @ $5 -> $6 each.
        {
            "timestamp": "2026-05-08T12:30:01.000+00:00",
            "slice_label": "naive",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "status": "ok",
        },
        {
            "timestamp": "2026-05-08T12:30:02.000+00:00",
            "slice_label": "naive",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "status": "ok",
        },
        # Error status — ignored.
        {
            "timestamp": "2026-05-08T12:30:03.000+00:00",
            "slice_label": "naive",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 100,
            "output_tokens": 100,
            "status": "error",
        },
    ]
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    cost, calls = naive_scraper.compute_run_metrics(
        log_path=log, started_at_iso=cutoff, slice_label="naive"
    )
    assert calls == 2
    assert cost == pytest.approx(12.0, rel=1e-6)


def test_render_digest_groups_by_work_mode_and_sorts_alpha():
    jobs = [
        Job(
            company="Zeta",
            role="SWE",
            location_text="Remote",
            work_mode="remote",
            salary_range=None,
            tech_stack=["go"],
            contact=None,
            raw_text="...",
        ),
        Job(
            company="Alpha",
            role="SRE",
            location_text="Worldwide",
            work_mode="remote",
            salary_range="$200k",
            tech_stack=["python", "k8s"],
            contact="hi@a.example",
            raw_text="...",
        ),
        Job(
            company="Beta",
            role="EM",
            location_text="NYC",
            work_mode="onsite",
            salary_range=None,
            tech_stack=[],
            contact=None,
            raw_text="...",
        ),
    ]
    digest = Digest(
        thread=ThreadMeta(
            item_id=42,
            title="Ask HN: Who is hiring? (May 2026)",
            url="https://news.ycombinator.com/item?id=42",
        ),
        jobs=jobs,
        generated_at=datetime(2026, 5, 8, 12, 0, tzinfo=UTC),
        wall_clock_seconds=125.4,
        total_llm_cost_usd=0.0734,
        total_llm_calls=3,
        candidate_comments=4,
    )
    md = naive_scraper.render_digest(digest)
    assert "# Ask HN: Who is hiring? (May 2026)" in md
    assert "## Remote (2 jobs)" in md
    assert "## Onsite (1 jobs)" in md
    # Alpha must appear before Zeta in the Remote section.
    remote_idx = md.index("## Remote")
    onsite_idx = md.index("## Onsite")
    remote_section = md[remote_idx:onsite_idx]
    assert remote_section.index("Alpha") < remote_section.index("Zeta")
    # Empty fields render as em-dashes.
    assert "| — |" in md


def test_render_digest_omits_empty_groups():
    jobs = [
        Job(
            company="Solo",
            role="SWE",
            location_text="Berlin",
            work_mode="hybrid",
            salary_range=None,
            tech_stack=[],
            contact=None,
            raw_text="...",
        ),
    ]
    digest = Digest(
        thread=ThreadMeta(item_id=1, title="t", url="https://news.ycombinator.com/item?id=1"),
        jobs=jobs,
        generated_at=datetime(2026, 5, 8, tzinfo=UTC),
        wall_clock_seconds=1.0,
        total_llm_cost_usd=0.0,
        total_llm_calls=1,
        candidate_comments=1,
    )
    md = naive_scraper.render_digest(digest)
    assert "## Hybrid" in md
    assert "## Remote" not in md
    assert "## Onsite" not in md
    assert "## Unspecified" not in md
