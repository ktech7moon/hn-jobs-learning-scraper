"""Slice 1: naive Playwright scraper for HN 'Who's Hiring' threads.

Public surface:

- :func:`run` — orchestrator invoked by ``hn-scraper naive``.
- :func:`find_latest_thread` — Playwright nav to ``/submitted?id=whoishiring``.
- :func:`fetch_top_level_comments` — Playwright nav, paginated, returns plain-text comments.
- :func:`extract_job` — single-comment extraction via Haiku.
- :func:`render_digest` — Markdown rendering.

Why a browser at all: the whole point of the naive path is to be
expensive — it's the baseline the graduated path beats. The
learning loop in Slice 2 is what discovers the cheap API.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from pydantic import ValidationError

from hn_scraper import llm
from hn_scraper.config import get_settings
from hn_scraper.models import Digest, Job, ThreadMeta, WorkMode
from hn_scraper.pricing import cost_usd
from hn_scraper.prompts import load_prompt

_logger = logging.getLogger(__name__)

HN_BASE = "https://news.ycombinator.com"
SUBMITTED_URL = f"{HN_BASE}/submitted?id=whoishiring"
SLICE_LABEL = "naive"
DIGEST_DIR = Path("data/digests")
TELEMETRY_LOG = Path("data/logs/llm_calls.jsonl")
TITLE_RE = re.compile(r"who is hiring", re.IGNORECASE)


# ---------- thread discovery ----------


def find_latest_thread(page: Page) -> ThreadMeta:
    """Open whoishiring's submitted page; pick the first 'Who is hiring?' thread."""
    page.goto(SUBMITTED_URL, wait_until="domcontentloaded")
    rows = page.locator("tr.athing").all()
    for row in rows:
        title_link = row.locator("span.titleline > a").first
        if title_link.count() == 0:
            continue
        title = (title_link.text_content() or "").strip()
        if TITLE_RE.search(title):
            item_id = int(row.get_attribute("id") or "0")
            return ThreadMeta(
                item_id=item_id,
                title=title,
                url=f"{HN_BASE}/item?id={item_id}",
            )
    raise RuntimeError("no 'Who is hiring' thread found on /submitted?id=whoishiring")


# ---------- comment fetch ----------


def fetch_top_level_comments(
    page: Page,
    item_id: int,
    *,
    max_pages: int,
) -> list[dict[str, str]]:
    """Walk the thread's pages, collect top-level comments as plain text.

    HN paginates comments via ``?p=N`` with a "More" link at the
    bottom. We follow until the More link disappears or
    ``max_pages`` is reached. ``max_pages=0`` means no cap.
    """
    collected: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    page_no = 1
    while True:
        url = f"{HN_BASE}/item?id={item_id}" + (f"&p={page_no}" if page_no > 1 else "")
        page.goto(url, wait_until="domcontentloaded")
        rows = page.locator("tr.athing.comtr").all()
        if not rows:
            break

        added_this_page = 0
        for row in rows:
            indent_img = row.locator("td.ind img").first
            if indent_img.count() == 0:
                continue
            width = indent_img.get_attribute("width")
            if width != "0":
                continue
            cid = row.get_attribute("id") or ""
            if not cid or cid in seen_ids:
                continue
            text_el = row.locator("div.commtext").first
            if text_el.count() == 0:
                continue
            text = (text_el.text_content() or "").strip()
            if not text:
                continue
            collected.append({"comment_id": cid, "text": text})
            seen_ids.add(cid)
            added_this_page += 1

        more_link = page.locator("a.morelink").first
        has_more = more_link.count() > 0
        _logger.info(
            "fetched HN page p=%d top_level_added=%d total=%d has_more=%s",
            page_no,
            added_this_page,
            len(collected),
            has_more,
        )
        if not has_more:
            break
        page_no += 1
        if max_pages and page_no > max_pages:
            break
        time.sleep(1.0)

    return collected


# ---------- LLM extraction ----------

_VALID_MODES: tuple[WorkMode, ...] = ("remote", "hybrid", "onsite", "unspecified")


def _normalize_payload(data: dict, raw_text: str) -> dict:
    """Coerce loosely-typed model output into a strict :class:`Job` payload."""
    work_mode = data.get("work_mode") or "unspecified"
    if work_mode not in _VALID_MODES:
        work_mode = "unspecified"

    tech_stack = data.get("tech_stack") or []
    if not isinstance(tech_stack, list):
        tech_stack = []
    tech_stack = [str(t).strip().lower() for t in tech_stack if str(t).strip()]

    return {
        "company": str(data.get("company") or "Unknown").strip() or "Unknown",
        "role": str(data.get("role") or "").strip(),
        "location_text": str(data.get("location_text") or "").strip(),
        "work_mode": work_mode,
        "salary_range": data.get("salary_range") or None,
        "tech_stack": tech_stack,
        "contact": data.get("contact") or None,
        "raw_text": raw_text,
    }


def _strip_fences(text: str) -> str:
    """Strip markdown code fences if the model defied the no-fence rule."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _build_job(payload_in: dict, comment_text: str, *, where: str) -> Job | None:
    """Normalize and validate one posting-shaped dict into a ``Job``.

    Returns ``None`` (with a warning) when the dict represents the
    ``not_a_posting`` sentinel or fails Pydantic validation. ``where``
    is used in log messages to disambiguate single-object vs.
    list-element failures.
    """
    if payload_in.get("not_a_posting") is True:
        return None
    payload = _normalize_payload(payload_in, raw_text=comment_text)
    try:
        return Job(**payload)
    except ValidationError as exc:
        _logger.warning("extract_job: validation failed (%s): %s", where, exc)
        return None


def extract_job(
    comment_text: str,
    *,
    model: str | None = None,
    slice_label: str = SLICE_LABEL,
) -> list[Job]:
    """Send one comment through the LLM; return zero, one, or many ``Job`` records.

    Some Who's Hiring comments bundle multiple roles. The model
    occasionally responds with a top-level JSON **list** of posting
    objects rather than the prescribed single object. We accept that
    shape and yield one ``Job`` per element so multi-role postings
    survive instead of being dropped wholesale.

    Default ``model`` is the cheap tier (Haiku) and ``slice_label`` is
    ``"naive"`` — Slice 1's baseline. Slice 2's graduated path passes
    ``model=settings.workhorse_model`` and ``slice_label="graduated"``
    so quality goes up and cost rolls up under the right slice.

    Returns:
      - ``[]`` for non-postings, sentinel, or unparseable output.
      - ``[Job]`` for a single posting object.
      - ``[Job, ...]`` for a top-level list. Invalid elements are
        dropped per-element and logged.
    """
    settings = get_settings()
    chosen_model = model or settings.cheap_model
    system_prompt = load_prompt("extract_job")
    response = llm.call(
        prompt_name="extract_job",
        model=chosen_model,
        slice_label=slice_label,
        system=system_prompt,
        messages=[{"role": "user", "content": comment_text}],
        max_tokens=600,
    )

    text_chunks = [block.text for block in response.content if getattr(block, "type", "") == "text"]
    raw = _strip_fences("".join(text_chunks))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        _logger.warning("extract_job: non-JSON output, dropping. preview=%r", raw[:120])
        return []

    if isinstance(data, list):
        out: list[Job] = []
        for i, element in enumerate(data):
            if not isinstance(element, dict):
                _logger.warning(
                    "extract_job: list element %d is not an object (type=%s), dropping",
                    i,
                    type(element).__name__,
                )
                continue
            job = _build_job(element, comment_text, where=f"list[{i}]")
            if job is not None:
                out.append(job)
        return out

    if not isinstance(data, dict):
        _logger.warning(
            "extract_job: top-level JSON is not object/list (type=%s), dropping",
            type(data).__name__,
        )
        return []

    job = _build_job(data, comment_text, where="single")
    return [job] if job is not None else []


def extract_jobs_batch(
    comment_texts: list[str],
    *,
    model: str,
    slice_label: str,
    max_tokens: int = 4000,
) -> list[list[Job]]:
    """Send N comments in one LLM call; return a list of ``Job`` lists, one per input.

    Used by the graduated path to amortize the system-prompt token
    overhead and stay under the per-organization rate limits. The
    returned outer list always has length ``len(comment_texts)``;
    individual entries are ``[]`` for non-postings, missing batch
    elements, or per-element validation failures.
    """
    if not comment_texts:
        return []
    out: list[list[Job]] = [[] for _ in comment_texts]

    parts: list[str] = []
    for i, text in enumerate(comment_texts):
        parts.append(f'<<<COMMENT id="{i}">>>\n{text}\n<<<END>>>\n')
    user_payload = "".join(parts)

    system_prompt = load_prompt("extract_jobs_batch")
    try:
        response = llm.call(
            prompt_name="extract_jobs_batch",
            model=model,
            slice_label=slice_label,
            system=system_prompt,
            messages=[{"role": "user", "content": user_payload}],
            max_tokens=max_tokens,
        )
    except Exception as exc:
        _logger.warning(
            "extract_jobs_batch: LLM call failed (batch_size=%d): %s",
            len(comment_texts),
            exc,
        )
        return out

    text_chunks = [
        block.text for block in response.content if getattr(block, "type", "") == "text"
    ]
    raw = _strip_fences("".join(text_chunks))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        _logger.warning(
            "extract_jobs_batch: non-JSON output (batch_size=%d). preview=%r",
            len(comment_texts),
            raw[:160],
        )
        return out

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        _logger.warning(
            "extract_jobs_batch: missing 'results' list (batch_size=%d, type=%s)",
            len(comment_texts),
            type(results).__name__,
        )
        return out

    for entry in results:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("comment_id")
        if not isinstance(cid, int) or cid < 0 or cid >= len(comment_texts):
            _logger.warning(
                "extract_jobs_batch: out-of-range comment_id=%r in batch of %d",
                cid,
                len(comment_texts),
            )
            continue
        jobs_raw = entry.get("jobs")
        if not isinstance(jobs_raw, list):
            continue
        comment_text = comment_texts[cid]
        for j_idx, job_dict in enumerate(jobs_raw):
            if not isinstance(job_dict, dict):
                continue
            job = _build_job(job_dict, comment_text, where=f"batch[cid={cid}][{j_idx}]")
            if job is not None:
                out[cid].append(job)
    return out


def extract_jobs(comments: Iterable[dict[str, str]]) -> list[Job]:
    jobs: list[Job] = []
    for i, c in enumerate(comments, start=1):
        try:
            new_jobs = extract_job(c["text"])
        except Exception as exc:
            _logger.warning("extract_job exception on cid=%s: %s", c.get("comment_id"), exc)
            continue
        jobs.extend(new_jobs)
        if i % 20 == 0:
            _logger.info("extract progress: %d candidates processed, %d jobs so far", i, len(jobs))
    return jobs


# ---------- cost / latency over JSONL ----------


def compute_run_metrics(
    *,
    log_path: Path = TELEMETRY_LOG,
    started_at_iso: str,
    slice_label: str = SLICE_LABEL,
) -> tuple[float, int]:
    """Read the JSONL log and return (total_cost_usd, total_calls) for this run.

    Filter is timestamp >= ``started_at_iso`` AND
    ``slice_label`` matches AND ``status == "ok"``. Concurrent runs
    of the same slice would double-count; for Slice 1 the demo runs
    serially so this is fine.
    """
    if not log_path.exists():
        return 0.0, 0
    total_cost = 0.0
    total_calls = 0
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("slice_label") != slice_label:
                continue
            if rec.get("status") != "ok":
                continue
            if rec.get("timestamp", "") < started_at_iso:
                continue
            total_cost += cost_usd(
                rec.get("model", ""),
                rec.get("input_tokens") or 0,
                rec.get("output_tokens") or 0,
            )
            total_calls += 1
    return total_cost, total_calls


# ---------- digest rendering ----------


_GROUP_ORDER: tuple[WorkMode, ...] = ("remote", "hybrid", "onsite", "unspecified")
_GROUP_LABELS: dict[WorkMode, str] = {
    "remote": "Remote",
    "hybrid": "Hybrid",
    "onsite": "Onsite",
    "unspecified": "Unspecified",
}


def _md_escape(s: str) -> str:
    """Escape pipe chars and collapse newlines so a value sits in a Markdown table cell."""
    return s.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def _format_seconds(secs: float) -> str:
    if secs < 60:
        return f"{secs:.1f} s"
    m, s = divmod(int(secs), 60)
    if m < 60:
        return f"{m} min {s} s"
    h, m = divmod(m, 60)
    return f"{h} h {m} min"


def render_digest(digest: Digest) -> str:
    grouped: dict[WorkMode, list[Job]] = defaultdict(list)
    for job in digest.jobs:
        grouped[job.work_mode].append(job)
    for mode in grouped:
        grouped[mode].sort(key=lambda j: (j.company.lower(), j.role.lower()))

    lines: list[str] = []
    lines.append(f"# {digest.thread.title}")
    lines.append("")
    lines.append(f"**Source:** {digest.thread.url}")
    lines.append(f"**Generated:** {digest.generated_at.isoformat(timespec='seconds')} (naive path)")
    lines.append(f"**Wall-clock:** {_format_seconds(digest.wall_clock_seconds)}")
    lines.append(
        f"**LLM cost:** ${digest.total_llm_cost_usd:.4f} USD across {digest.total_llm_calls} calls"
    )
    lines.append(
        f"**Jobs extracted:** {len(digest.jobs)} (out of "
        f"{digest.candidate_comments} top-level comments)"
    )
    lines.append("")
    lines.append(
        "_Cost is approximate, derived from token counts × Anthropic public list "
        "pricing as of 2026-05. See `hn_scraper/pricing.py`._"
    )
    lines.append("")

    for mode in _GROUP_ORDER:
        jobs = grouped.get(mode, [])
        if not jobs:
            continue
        lines.append(f"## {_GROUP_LABELS[mode]} ({len(jobs)} jobs)")
        lines.append("")
        lines.append("| Company | Role | Location | Salary | Tech Stack |")
        lines.append("| --- | --- | --- | --- | --- |")
        for j in jobs:
            stack = ", ".join(j.tech_stack) if j.tech_stack else "—"
            salary = j.salary_range if j.salary_range else "—"
            location = j.location_text if j.location_text else "—"
            lines.append(
                "| "
                + _md_escape(j.company)
                + " | "
                + _md_escape(j.role)
                + " | "
                + _md_escape(location)
                + " | "
                + _md_escape(salary)
                + " | "
                + _md_escape(stack)
                + " |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------- orchestrator ----------


def run(thread_id: int | None = None, *, max_pages: int = 5) -> Path:
    """Top-level orchestrator. Returns the digest path."""
    started = time.perf_counter()
    started_at_iso = datetime.now(UTC).isoformat(timespec="milliseconds")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36 hn-jobs-learning-scraper/0.1 (portfolio demo)"
            )
        )
        page = context.new_page()

        if thread_id is None:
            meta = find_latest_thread(page)
            _logger.info("discovered thread id=%d title=%r", meta.item_id, meta.title)
        else:
            page.goto(f"{HN_BASE}/item?id={thread_id}", wait_until="domcontentloaded")
            title_el = page.locator("tr.athing span.titleline > a").first
            title = (
                (title_el.text_content() or "").strip() if title_el.count() else f"id {thread_id}"
            )
            meta = ThreadMeta(item_id=thread_id, title=title, url=f"{HN_BASE}/item?id={thread_id}")

        comments = fetch_top_level_comments(page, meta.item_id, max_pages=max_pages)
        _logger.info("collected %d top-level comments", len(comments))
        browser.close()

    jobs = extract_jobs(comments)
    wall_clock = time.perf_counter() - started
    total_cost, total_calls = compute_run_metrics(started_at_iso=started_at_iso)

    digest = Digest(
        thread=meta,
        jobs=jobs,
        generated_at=datetime.now(UTC),
        wall_clock_seconds=wall_clock,
        total_llm_cost_usd=total_cost,
        total_llm_calls=total_calls,
        candidate_comments=len(comments),
    )

    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DIGEST_DIR / f"{meta.item_id}-naive.md"
    out_path.write_text(render_digest(digest), encoding="utf-8")
    _logger.info(
        "wrote digest path=%s jobs=%d wall_clock=%.1fs cost=$%.4f",
        out_path,
        len(jobs),
        wall_clock,
        total_cost,
    )
    return out_path
