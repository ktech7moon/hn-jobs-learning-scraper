"""Side-by-side comparison of naive vs. graduated paths.

Reads the JSONL telemetry log and, by default, auto-scopes each
``slice_label`` to its most recent contiguous run — calls that
share a ``slice_label`` and arrive within ``RUN_GAP_SECONDS`` of
each other count as one run. ``--since`` overrides the auto-scope
when you need a specific time window.

Auto-scoping prevents the table from mixing experimental reruns
with the run you actually want to talk about: an earlier failed
Sonnet attempt and the final Haiku batched run both write
``slice_label="graduated"`` rows, but only the latest run is
relevant for the demo headline.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from hn_scraper.pricing import cost_usd

TELEMETRY_LOG = Path("data/logs/llm_calls.jsonl")
DIGEST_DIR = Path("data/digests")
LEARNING_DIR = Path("data/learning")

# Gap between two same-slice telemetry rows that splits them into
# separate runs. Within a single ``hn-scraper graduated`` invocation
# inter-call gaps are seconds; between separate invocations they are
# at minimum minutes (manual workflow). 300 s comfortably separates
# real runs while tolerating in-run rate-limit retry stalls.
RUN_GAP_SECONDS = 300


def _read_log(*, log_path: Path, since: str | None) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if since and rec.get("timestamp", "") < since:
                continue
            rows.append(rec)
    return rows


def _aggregate_by_slice(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_slice: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "calls_ok": 0,
            "calls_err": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms_total": 0,
            "models": defaultdict(int),
        }
    )
    for rec in rows:
        sl = rec.get("slice_label") or "unknown"
        bucket = by_slice[sl]
        if rec.get("status") == "ok":
            bucket["calls_ok"] += 1
            it = rec.get("input_tokens") or 0
            ot = rec.get("output_tokens") or 0
            bucket["input_tokens"] += it
            bucket["output_tokens"] += ot
            bucket["cost_usd"] += cost_usd(rec.get("model", ""), it, ot)
            bucket["latency_ms_total"] += rec.get("latency_ms") or 0
            bucket["models"][rec.get("model", "?")] += 1
        else:
            bucket["calls_err"] += 1
    return by_slice


def _latest_run_window(
    rows: list[dict[str, Any]],
    *,
    slice_label: str,
    gap_seconds: int = RUN_GAP_SECONDS,
) -> tuple[str, str] | None:
    """Return ``(start_iso, end_iso)`` for the latest contiguous run of ``slice_label``.

    A "run" is a maximal sequence of rows with the same
    ``slice_label`` such that adjacent rows are no more than
    ``gap_seconds`` apart. Returns ``None`` if no rows match.
    """
    matched = sorted(
        (
            (r["timestamp"], r)
            for r in rows
            if r.get("slice_label") == slice_label and r.get("timestamp")
        ),
        key=lambda pair: pair[0],
    )
    if not matched:
        return None
    end_ts = matched[-1][0]
    start_ts = end_ts
    prev_dt = datetime.fromisoformat(end_ts)
    for ts, _ in reversed(matched[:-1]):
        ts_dt = datetime.fromisoformat(ts)
        if (prev_dt - ts_dt).total_seconds() > gap_seconds:
            break
        start_ts = ts
        prev_dt = ts_dt
    return start_ts, end_ts


def _scope_to_latest_runs(
    rows: list[dict[str, Any]],
    *,
    gap_seconds: int = RUN_GAP_SECONDS,
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
    """Filter ``rows`` to the latest run per ``slice_label``.

    Prefers grouping by ``run_id`` (one id per CLI invocation —
    written to telemetry by ``llm.set_current_run_id`` since 2026-05).
    Falls back to a time-gap heuristic for legacy rows that pre-date
    that field.

    Returns ``(filtered_rows, windows)`` where ``windows`` maps each
    slice label to the ``(start_iso, end_iso)`` of its latest run —
    handy for showing the user which window is actually being shown.
    """
    slices = {r.get("slice_label") for r in rows if r.get("slice_label")}
    windows: dict[str, tuple[str, str]] = {}
    keep: list[dict[str, Any]] = []
    for sl in slices:
        if not isinstance(sl, str):
            continue
        slice_rows = [r for r in rows if r.get("slice_label") == sl]
        with_id = [r for r in slice_rows if r.get("run_id")]
        if with_id:
            latest_id = max(with_id, key=lambda r: r["timestamp"])["run_id"]
            run_rows = [r for r in slice_rows if r.get("run_id") == latest_id]
            timestamps = sorted(r["timestamp"] for r in run_rows if r.get("timestamp"))
            if timestamps:
                windows[sl] = (timestamps[0], timestamps[-1])
                keep.extend(run_rows)
            continue
        # Fallback for legacy rows with no run_id.
        win = _latest_run_window(rows, slice_label=sl, gap_seconds=gap_seconds)
        if win is None:
            continue
        windows[sl] = win
        start, end = win
        keep.extend(
            r
            for r in slice_rows
            if start <= r.get("timestamp", "") <= end
        )
    return keep, windows


_JOBS_LINE_RE = re.compile(r"\*\*Jobs extracted:\*\*\s+(\d+)")


def _count_jobs_in(digest_path: Path) -> int | None:
    if not digest_path.exists():
        return None
    text = digest_path.read_text(encoding="utf-8")
    m = _JOBS_LINE_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def print_comparison(*, since: str | None = None, log_path: Path = TELEMETRY_LOG) -> None:
    rows = _read_log(log_path=log_path, since=since)
    console = Console()

    windows: dict[str, tuple[str, str]] = {}
    if since is None:
        rows, windows = _scope_to_latest_runs(rows)
        scope_note = (
            "Auto-scoped to the latest run per slice "
            f"(gap > {RUN_GAP_SECONDS}s = new run). Pass --since to override."
        )
    else:
        scope_note = f"Filtering rows since {since} (--since override)."

    by_slice = _aggregate_by_slice(rows)

    if not by_slice:
        console.print(
            "[yellow]No telemetry rows found. Run `hn-scraper naive` and "
            "`hn-scraper graduated` first.[/yellow]"
        )
        return

    console.print(f"[dim]{scope_note}[/dim]")
    if windows:
        for sl in sorted(windows):
            start, end = windows[sl]
            console.print(f"[dim]  • {sl}: {start} → {end}[/dim]")
    table = Table(title="Naive vs. Graduated path — Slice 2 comparison")
    table.add_column("Slice", style="bold")
    table.add_column("OK calls", justify="right")
    table.add_column("Err calls", justify="right")
    table.add_column("Input tok", justify="right")
    table.add_column("Output tok", justify="right")
    table.add_column("$ cost", justify="right")
    table.add_column("Avg latency", justify="right")
    table.add_column("Models")

    # Stable ordering: naive, learn, graduated, then the rest.
    order = ["naive", "learn", "graduated"]
    keys = order + sorted(k for k in by_slice if k not in order)
    for sl in keys:
        if sl not in by_slice:
            continue
        b = by_slice[sl]
        avg_latency_ms = (b["latency_ms_total"] / b["calls_ok"]) if b["calls_ok"] else 0
        models_str = ", ".join(
            f"{m} ×{n}" for m, n in sorted(b["models"].items(), key=lambda kv: -kv[1])
        )
        table.add_row(
            sl,
            str(b["calls_ok"]),
            str(b["calls_err"]),
            f"{b['input_tokens']:,}",
            f"{b['output_tokens']:,}",
            f"${b['cost_usd']:.4f}",
            f"{avg_latency_ms / 1000:.2f} s",
            models_str,
        )

    console.print(table)

    # Per-thread digest job counts: scan ./data/digests/.
    if DIGEST_DIR.exists():
        digest_table = Table(title="Digests on disk")
        digest_table.add_column("File")
        digest_table.add_column("Thread id")
        digest_table.add_column("Slice")
        digest_table.add_column("Jobs", justify="right")
        for path in sorted(DIGEST_DIR.glob("*.md")):
            name = path.name
            jobs = _count_jobs_in(path)
            slice_part = "naive" if "naive" in name else (
                "graduated" if "graduated" in name else "?"
            )
            thread_part = name.split("-")[0]
            digest_table.add_row(
                name, thread_part, slice_part, str(jobs) if jobs is not None else "?"
            )
        console.print(digest_table)

    # Headline ratios (only when both naive + graduated rows exist).
    n = by_slice.get("naive")
    g = by_slice.get("graduated")
    if n and g and n["cost_usd"] > 0:
        cost_ratio = g["cost_usd"] / n["cost_usd"]
        console.print(
            f"\n[bold]Cost ratio (graduated / naive):[/bold] {cost_ratio:.2%} "
            f"(${g['cost_usd']:.4f} vs ${n['cost_usd']:.4f}); "
            f"{'cheaper' if cost_ratio < 1 else 'more expensive'} by "
            f"{abs(1 - cost_ratio):.0%}."
        )
