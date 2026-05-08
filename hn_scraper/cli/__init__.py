"""CLI entrypoint for hn-scraper.

The root command is `hn-scraper`. Subcommands are defined inline; in
scaffolding only `version` is implemented. The others print a
"not yet implemented" message and exit 0 so the CLI shape is real
before the slices fill them in.
"""

from __future__ import annotations

import click

from hn_scraper import __version__


@click.group()
def main() -> None:
    """Autobrowse-pattern learning scraper for HN 'Who's Hiring' threads."""


@main.command()
def version() -> None:
    """Print the package version."""
    click.echo(__version__)


@main.command()
def naive() -> None:
    """Slice 1: naive Playwright scraper of the latest HN 'Who's Hiring' thread."""
    click.echo("naive: not yet implemented (Slice 1)")


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
