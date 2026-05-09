"""Slice 2: Autobrowse-style learning loop.

The loop runs Sonnet 4.6 with three tools: ``http_get``,
``record_finding``, and ``declare_convergence``. The agent probes
candidate strategies for fetching HN "Who's Hiring" comments
without a browser, accumulates findings into a dossier, and
declares convergence when it has a verified end-to-end strategy.

When the loop terminates (convergence or budget exhaustion) the
dossier is handed to Opus 4.7, which authors a self-contained
``SKILL.md`` at ``hn_scraper/skills/who-is-hiring/SKILL.md``. Future
graduated runs read that file as documentation; the discovered
constants live in ``hn_scraper/firebase_api.py``.

Iteration accounting: one assistant turn (potentially containing
multiple tool calls) counts as one iteration. The default budget
is 8. If the agent declares convergence and verification passes,
the loop ends early.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from hn_scraper import llm
from hn_scraper.config import get_settings
from hn_scraper.prompts import load_prompt

SLICE_LABEL = "learn"
LEARNING_DIR = Path("data/learning")
SKILL_PATH = Path("hn_scraper/skills/who-is-hiring/SKILL.md")

DEFAULT_MAX_ITERATIONS = 8
HTTP_BODY_CAP_BYTES = 8000
HTTP_TIMEOUT_S = 12.0

# Naive baseline numbers from the live Slice 1 run on thread 47975571.
# Used in prompts so the agent knows what it's beating.
NAIVE_BASELINE = {
    "thread_id": 47975571,
    "comments": 317,
    "jobs": 326,
    "wall_clock": "6 min 39 s",
    "cost_usd": 0.4364,
}

_logger = logging.getLogger(__name__)


# ---------- dossier ----------


@dataclass
class Finding:
    iteration: int
    category: str
    text: str


@dataclass
class ToolCallRecord:
    iteration: int
    tool: str
    input: dict[str, Any]
    result_summary: str


@dataclass
class Dossier:
    thread_id: int
    started_at: str
    findings: list[Finding] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    convergence: dict[str, Any] | None = None
    iterations_used: int = 0

    def to_markdown(self) -> str:
        """Render the dossier as a single Markdown document for Opus."""
        lines: list[str] = []
        lines.append(f"# Discovery Dossier — thread {self.thread_id}")
        lines.append(f"Started: {self.started_at}")
        lines.append(f"Iterations used: {self.iterations_used}")
        if self.convergence:
            lines.append(
                f"Convergence: {self.convergence.get('strategy_name')!r} — "
                f"verification: {self.convergence.get('verification_status')}"
            )
        else:
            lines.append("Convergence: NOT REACHED (budget exhausted)")
        lines.append("")
        lines.append("## Findings (in order recorded)")
        if not self.findings:
            lines.append("_No structured findings recorded._")
        else:
            for f in self.findings:
                lines.append(f"- **iter {f.iteration} / {f.category}**: {f.text}")
        lines.append("")
        lines.append("## Tool-call transcript")
        for tc in self.tool_calls:
            arg_preview = json.dumps(tc.input, ensure_ascii=False)
            if len(arg_preview) > 240:
                arg_preview = arg_preview[:240] + "…"
            lines.append(
                f"- iter {tc.iteration} / `{tc.tool}` "
                f"args={arg_preview} → {tc.result_summary}"
            )
        if self.convergence:
            lines.append("")
            lines.append("## Convergence claim")
            lines.append("```json")
            lines.append(json.dumps(self.convergence, indent=2, ensure_ascii=False))
            lines.append("```")
        return "\n".join(lines) + "\n"


# ---------- tool implementations ----------


_HTTP_SESSION = requests.Session()
_HTTP_SESSION.headers.update(
    {
        "User-Agent": (
            "hn-jobs-learning-scraper/0.1 (+https://github.com/ktech7moon) "
            "discovery loop; portfolio demo"
        )
    }
)


def _tool_http_get(*, url: str, max_bytes: int = HTTP_BODY_CAP_BYTES) -> dict[str, Any]:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return {
            "error": "url must be an http(s) URL",
            "status": None,
        }
    cap = max(512, min(int(max_bytes), HTTP_BODY_CAP_BYTES))
    try:
        resp = _HTTP_SESSION.get(url, timeout=HTTP_TIMEOUT_S, stream=True)
    except requests.RequestException as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "status": None}
    body_bytes = b""
    for chunk in resp.iter_content(chunk_size=1024):
        body_bytes += chunk
        if len(body_bytes) >= cap:
            break
    truncated = len(body_bytes) >= cap
    body = body_bytes.decode("utf-8", errors="replace")
    if truncated:
        body = body[:cap]
    return {
        "status": resp.status_code,
        "content_type": resp.headers.get("content-type", ""),
        "body_truncated": truncated,
        "body": body,
    }


def _tool_record_finding(
    *,
    dossier: Dossier,
    iteration: int,
    category: str,
    text: str,
) -> dict[str, Any]:
    valid_categories = {"endpoint", "schema", "parsing_rule", "edge_case", "reasoning"}
    if category not in valid_categories:
        return {
            "error": (
                f"category must be one of {sorted(valid_categories)}; got {category!r}"
            )
        }
    if not isinstance(text, str) or not text.strip():
        return {"error": "text must be a non-empty string"}
    finding = Finding(iteration=iteration, category=category, text=text.strip())
    dossier.findings.append(finding)
    return {
        "ok": True,
        "stored": {"iteration": iteration, "category": category},
        "total_findings": len(dossier.findings),
    }


def _verify_strategy(
    *,
    primary_endpoint_pattern: str,
    thread_id: int,
) -> dict[str, Any]:
    """Sanity-check a declared strategy by calling its primary endpoint.

    Tolerant: we only require that ``primary_endpoint_pattern`` contains
    a ``{thread_id}`` placeholder, fetches OK, returns JSON with a
    ``kids`` list of length > 50, and that one kid item carries a
    non-empty ``text``. The graduated path may still need adjustment
    around the edges; this is a smoke test, not a full audit.
    """
    if (
        "{thread_id}" not in primary_endpoint_pattern
        and "{item_id}" not in primary_endpoint_pattern
    ):
        return {
            "verification_status": "FAIL",
            "reason": (
                "primary_endpoint_pattern must contain a {thread_id} or "
                "{item_id} placeholder so the strategy is parameterizable"
            ),
        }
    url = primary_endpoint_pattern.format(thread_id=thread_id, item_id=thread_id)
    try:
        resp = _HTTP_SESSION.get(url, timeout=HTTP_TIMEOUT_S)
    except requests.RequestException as exc:
        return {"verification_status": "FAIL", "reason": f"fetch failed: {exc}"}
    if resp.status_code != 200:
        return {
            "verification_status": "FAIL",
            "reason": f"non-200 status: {resp.status_code}",
        }
    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError) as exc:
        return {"verification_status": "FAIL", "reason": f"non-JSON body: {exc}"}
    kids = data.get("kids") if isinstance(data, dict) else None
    if not isinstance(kids, list) or len(kids) < 50:
        return {
            "verification_status": "FAIL",
            "reason": (
                f"primary endpoint did not return a kids list of length > 50 "
                f"(got {type(kids).__name__}, len={len(kids) if isinstance(kids, list) else 'n/a'})"
            ),
        }
    sample_kid_id = kids[0]
    if not isinstance(sample_kid_id, int):
        return {
            "verification_status": "FAIL",
            "reason": f"first kid id is not an int (got {type(sample_kid_id).__name__})",
        }
    sample_url = primary_endpoint_pattern.format(
        thread_id=sample_kid_id, item_id=sample_kid_id
    )
    try:
        sample_resp = _HTTP_SESSION.get(sample_url, timeout=HTTP_TIMEOUT_S)
        sample = sample_resp.json()
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        return {"verification_status": "FAIL", "reason": f"sample kid fetch failed: {exc}"}
    if not isinstance(sample, dict) or not sample.get("text"):
        return {
            "verification_status": "FAIL",
            "reason": (
                "sample kid item has no 'text' field — wrong endpoint shape"
            ),
        }
    return {
        "verification_status": "PASS",
        "thread_id": thread_id,
        "kids_count": len(kids),
        "sample_kid_id": sample_kid_id,
        "sample_kid_text_len": len(sample["text"]),
    }


# ---------- tool schemas (for the Anthropic API) ----------


_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "http_get",
        "description": (
            "Issue a GET request and return the response status, content-type, "
            "and a truncated body. Use this to probe candidate endpoints. "
            "Body is capped at 8000 bytes to keep the iteration cheap; if you "
            "need more, pass max_bytes explicitly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full http(s) URL to fetch.",
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "Cap for the returned body (512–8000).",
                    "default": HTTP_BODY_CAP_BYTES,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "record_finding",
        "description": (
            "Append a structured note to the dossier the SKILL.md author will "
            "read. Use one of: endpoint, schema, parsing_rule, edge_case, "
            "reasoning. Be specific and concrete — cite URLs and example values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "endpoint",
                        "schema",
                        "parsing_rule",
                        "edge_case",
                        "reasoning",
                    ],
                },
                "text": {"type": "string"},
            },
            "required": ["category", "text"],
        },
    },
    {
        "name": "declare_convergence",
        "description": (
            "Call this once you have a verified strategy. The harness will "
            "fetch your primary endpoint and confirm it returns the expected "
            "shape. If verification fails you may keep iterating."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy_name": {"type": "string"},
                "primary_endpoint_pattern": {
                    "type": "string",
                    "description": (
                        "URL template containing a {thread_id} or {item_id} "
                        "placeholder."
                    ),
                },
                "evidence_summary": {
                    "type": "string",
                    "description": (
                        "Two or three sentences summarizing what you observed "
                        "and why you trust this strategy."
                    ),
                },
            },
            "required": [
                "strategy_name",
                "primary_endpoint_pattern",
                "evidence_summary",
            ],
        },
    },
]


# ---------- the loop ----------


def _summarize_tool_result(tool: str, result: dict[str, Any]) -> str:
    """One-line summary of a tool's structured result, for the dossier transcript."""
    if "error" in result:
        return f"ERROR: {result['error']}"
    if tool == "http_get":
        return (
            f"status={result.get('status')} "
            f"ct={result.get('content_type')!r} "
            f"truncated={result.get('body_truncated')} "
            f"body_len={len(result.get('body', ''))}"
        )
    if tool == "record_finding":
        return f"recorded (total_findings={result.get('total_findings')})"
    if tool == "declare_convergence":
        return f"verification={result.get('verification_status')}"
    return json.dumps(result)[:200]


def _system_prompt(thread_id: int, current_iteration: int, max_iterations: int) -> str:
    return load_prompt(
        "learn_loop_system",
        thread_id=thread_id,
        naive_jobs=NAIVE_BASELINE["jobs"],
        naive_comments=NAIVE_BASELINE["comments"],
        naive_wall_clock=NAIVE_BASELINE["wall_clock"],
        naive_cost=NAIVE_BASELINE["cost_usd"],
        max_iterations=max_iterations,
        current_iteration=current_iteration,
    )


def _author_skill_md(dossier: Dossier) -> str:
    """Hand the dossier to Opus 4.7 to author the final SKILL.md."""
    settings = get_settings()
    system_prompt = load_prompt("skill_author_system")
    user_payload = (
        f"Naive baseline: {json.dumps(NAIVE_BASELINE)}\n\n"
        f"Dossier (Markdown):\n\n{dossier.to_markdown()}"
    )
    response = llm.call(
        prompt_name="skill_author",
        model=settings.premium_model,
        slice_label=SLICE_LABEL,
        system=system_prompt,
        max_tokens=4000,
        messages=[{"role": "user", "content": user_payload}],
    )
    text_chunks = [
        block.text for block in response.content if getattr(block, "type", "") == "text"
    ]
    text = "".join(text_chunks).strip()
    if text.startswith("```"):
        # Defensive: strip a stray code fence if Opus wrapped the file.
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text.endswith("\n"):
        text += "\n"
    return text


def run(thread_id: int, *, max_iterations: int = DEFAULT_MAX_ITERATIONS) -> dict[str, Any]:
    """Run the learning loop, then author and write the SKILL.md.

    Returns a summary dict with paths and key metrics.
    """
    settings = get_settings()
    started_at_iso = datetime.now(UTC).isoformat(timespec="milliseconds")
    started_perf = time.perf_counter()
    dossier = Dossier(thread_id=thread_id, started_at=started_at_iso)

    LEARNING_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = LEARNING_DIR / f"{thread_id}-{started_at_iso.replace(':', '-')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = run_dir / "transcript.jsonl"

    def _append_transcript(record: dict[str, Any]) -> None:
        with transcript_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    user_kickoff = (
        f"Begin discovery for thread_id={thread_id}. You are on iteration 1 "
        f"of {max_iterations}. Start by considering what HN itself exposes "
        f"and probe one endpoint."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_kickoff}]

    converged = False
    convergence_payload: dict[str, Any] | None = None
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        dossier.iterations_used = iteration

        system_prompt = _system_prompt(thread_id, iteration, max_iterations)
        try:
            response = llm.call(
                prompt_name="learn_loop_turn",
                model=settings.workhorse_model,
                slice_label=SLICE_LABEL,
                system=system_prompt,
                max_tokens=2000,
                messages=messages,
                tools=_TOOL_SCHEMAS,
            )
        except Exception as exc:
            _logger.error("learn loop iteration %d: model call failed: %s", iteration, exc)
            _append_transcript(
                {"iteration": iteration, "kind": "model_error", "error": str(exc)}
            )
            break

        # The Anthropic SDK accepts its own response.content blocks
        # back as the next assistant message's content, so no manual
        # block-to-dict conversion is needed.
        messages.append({"role": "assistant", "content": response.content})

        text_summary = _join_text_blocks(response.content)
        _append_transcript(
            {
                "iteration": iteration,
                "kind": "assistant_turn",
                "stop_reason": response.stop_reason,
                "text_preview": text_summary[:1000],
                "tool_calls": [
                    {"name": b.name, "input": b.input}
                    for b in response.content
                    if getattr(b, "type", "") == "tool_use"
                ],
            }
        )

        tool_uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
        if not tool_uses:
            _logger.info(
                "learn loop iter %d: no tool calls (stop_reason=%s) — ending",
                iteration,
                response.stop_reason,
            )
            break

        tool_results_content: list[dict[str, Any]] = []
        for tu in tool_uses:
            tool_name = tu.name
            tool_input = tu.input or {}
            if tool_name == "http_get":
                result = _tool_http_get(**tool_input)
            elif tool_name == "record_finding":
                result = _tool_record_finding(
                    dossier=dossier,
                    iteration=iteration,
                    category=tool_input.get("category", ""),
                    text=tool_input.get("text", ""),
                )
            elif tool_name == "declare_convergence":
                verification = _verify_strategy(
                    primary_endpoint_pattern=tool_input.get(
                        "primary_endpoint_pattern", ""
                    ),
                    thread_id=thread_id,
                )
                result = {
                    "strategy_name": tool_input.get("strategy_name"),
                    "primary_endpoint_pattern": tool_input.get(
                        "primary_endpoint_pattern"
                    ),
                    "evidence_summary": tool_input.get("evidence_summary"),
                    **verification,
                }
                if verification.get("verification_status") == "PASS":
                    converged = True
                    convergence_payload = result
            else:
                result = {"error": f"unknown tool: {tool_name}"}

            dossier.tool_calls.append(
                ToolCallRecord(
                    iteration=iteration,
                    tool=tool_name,
                    input=tool_input,
                    result_summary=_summarize_tool_result(tool_name, result),
                )
            )
            _append_transcript(
                {
                    "iteration": iteration,
                    "kind": "tool_result",
                    "tool": tool_name,
                    "input": tool_input,
                    "result_keys": sorted(result.keys()),
                }
            )

            tool_results_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

        messages.append({"role": "user", "content": tool_results_content})

        if converged:
            _logger.info(
                "learn loop converged at iteration %d / %d", iteration, max_iterations
            )
            dossier.convergence = convergence_payload
            break

    if not converged:
        _logger.warning(
            "learn loop ended without convergence (iterations_used=%d / %d)",
            dossier.iterations_used,
            max_iterations,
        )

    # Persist dossier as Markdown for human review and as JSON for tooling.
    (run_dir / "dossier.md").write_text(dossier.to_markdown(), encoding="utf-8")
    (run_dir / "dossier.json").write_text(
        json.dumps(asdict(dossier), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Author the SKILL.md regardless of convergence — the brief calls
    # for a "partial SKILL.md explaining what was attempted" if budget
    # exhausts.
    _logger.info("authoring SKILL.md with %s", settings.premium_model)
    skill_md = _author_skill_md(dossier)
    SKILL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SKILL_PATH.write_text(skill_md, encoding="utf-8")

    elapsed_s = time.perf_counter() - started_perf
    summary = {
        "thread_id": thread_id,
        "iterations_used": dossier.iterations_used,
        "max_iterations": max_iterations,
        "converged": converged,
        "convergence": convergence_payload,
        "skill_path": str(SKILL_PATH),
        "dossier_dir": str(run_dir),
        "wall_clock_seconds": elapsed_s,
    }
    _logger.info(
        "learn loop done: converged=%s iters=%d skill=%s wall=%.1fs",
        converged,
        dossier.iterations_used,
        SKILL_PATH,
        elapsed_s,
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def _join_text_blocks(blocks: list[Any]) -> str:
    parts = [getattr(b, "text", "") for b in blocks if getattr(b, "type", "") == "text"]
    return "\n".join(p for p in parts if p)
