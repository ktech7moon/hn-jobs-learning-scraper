"""CLI entrypoint for hn-scraper.

The root command is ``hn-scraper``. Slice 1 wired ``naive``; Slice 2
adds ``learn``, ``graduated``, and ``compare``.
"""

from __future__ import annotations

import json
import uuid

import click

from hn_scraper import __version__, llm
from hn_scraper.config import get_settings
from hn_scraper.logging_setup import setup_logging


def _start_run() -> str:
    """Generate and register a fresh run id for this CLI invocation.

    Every ``llm.call`` made downstream picks this id up via
    ``llm.get_current_run_id()`` and writes it to the JSONL row.
    ``compare`` groups by it so back-to-back runs don't merge.
    """
    rid = uuid.uuid4().hex[:12]
    llm.set_current_run_id(rid)
    return rid


@click.group()
def main() -> None:
    """Autobrowse-pattern learning scraper for HN 'Who's Hiring' threads."""


@main.command()
def version() -> None:
    """Print the package version."""
    click.echo(__version__)


@main.command()
@click.option(
    "--thread-id",
    type=int,
    default=None,
    help="HN item id to scrape. Default: auto-discover the most recent 'Who is hiring' thread.",
)
@click.option(
    "--max-pages",
    type=int,
    default=5,
    show_default=True,
    help="Comment-page cap. 0 means no cap (every page until 'More' disappears).",
)
def naive(thread_id: int | None, max_pages: int) -> None:
    """Slice 1: naive Playwright scraper of the latest HN 'Who's Hiring' thread."""
    setup_logging(get_settings().log_level)
    _start_run()
    from hn_scraper.naive_scraper import run

    out_path = run(thread_id=thread_id, max_pages=max_pages)
    click.echo(str(out_path))


@main.command()
@click.option(
    "--thread-id",
    type=int,
    required=True,
    help="HN item id to learn from. Required.",
)
@click.option(
    "--max-iterations",
    type=int,
    default=8,
    show_default=True,
    help="Iteration budget for the discovery loop.",
)
def learn(thread_id: int, max_iterations: int) -> None:
    """Slice 2: run the Autobrowse iterative learning loop and graduate a SKILL.md."""
    setup_logging(get_settings().log_level)
    _start_run()
    from hn_scraper.learner import run

    summary = run(thread_id=thread_id, max_iterations=max_iterations)
    click.echo(json.dumps(summary, indent=2))


@main.command()
@click.option(
    "--thread-id",
    type=int,
    required=True,
    help="HN item id to scrape with the graduated strategy.",
)
@click.option(
    "--max-workers",
    type=int,
    default=6,
    show_default=True,
    help="Concurrent batched-extraction worker count.",
)
@click.option(
    "--batch-size",
    type=int,
    default=8,
    show_default=True,
    help="Number of comments packed into a single LLM call. 8 keeps "
    "total request count well under the 50 RPM ceiling and amortizes "
    "system-prompt input tokens.",
)
@click.option(
    "--model",
    type=str,
    default=None,
    help="Anthropic model id for batched extraction. Default: cheap "
    "tier (Haiku). Pass claude-sonnet-4-6 for higher quality at the "
    "cost of throughput on rate-limited tiers.",
)
def graduated(
    thread_id: int, max_workers: int, batch_size: int, model: str | None
) -> None:
    """Slice 2: run the graduated path using the discovered Firebase API."""
    setup_logging(get_settings().log_level)
    _start_run()
    from hn_scraper.graduated import run

    out_path = run(
        thread_id=thread_id,
        max_workers=max_workers,
        batch_size=batch_size,
        model=model,
    )
    click.echo(str(out_path))


@main.command()
@click.option(
    "--since",
    type=str,
    default=None,
    help="ISO8601 timestamp; only count log rows at or after this time. "
    "Default: read all rows in the JSONL log.",
)
def compare(since: str | None) -> None:
    """Print a cost/latency comparison between the naive and graduated paths."""
    setup_logging(get_settings().log_level)
    from hn_scraper.compare import print_comparison

    print_comparison(since=since)
