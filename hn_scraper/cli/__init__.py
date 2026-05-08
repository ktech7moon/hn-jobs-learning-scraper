"""CLI entrypoint for hn-scraper.

The root command is ``hn-scraper``. ``naive`` is wired to
:func:`hn_scraper.naive_scraper.run` (Slice 1). ``learn``,
``graduated``, and ``compare`` remain placeholders for Slice 2.
"""

from __future__ import annotations

import click

from hn_scraper import __version__
from hn_scraper.config import get_settings
from hn_scraper.logging_setup import setup_logging


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
    from hn_scraper.naive_scraper import run

    out_path = run(thread_id=thread_id, max_pages=max_pages)
    click.echo(str(out_path))


@main.command()
def learn() -> None:
    """Slice 2: run the Autobrowse iterative learning loop and graduate a SKILL.md."""
    click.echo("learn: not yet implemented (Slice 2)")


@main.command()
def graduated() -> None:
    """Slice 2: run the graduated path using the discovered SKILL.md."""
    click.echo("graduated: not yet implemented (Slice 2)")


@main.command()
def compare() -> None:
    """Print a cost/latency comparison between the naive and graduated paths."""
    click.echo("compare: not yet implemented (Slice 2)")
