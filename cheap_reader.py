#!/usr/bin/env python3
"""Repo-root helper: dump file contents (no LLM by default).

Default mode prints each path's content to stdout under a
`===== <path> =====` header — no LLM call, no preamble. Use this
in place of `cat` when you want a single deterministic dump that
also feeds nicely into a follow-on summarize call.

With ``--summarize``, concatenated contents are sent to Haiku
(``claude-haiku-4-5-20251001`` or whatever ``CHEAP_MODEL`` overrides
to) for a terse summary. The summarize path requires
``ANTHROPIC_API_KEY`` in the environment.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def dump(paths: list[Path]) -> str:
    chunks: list[str] = []
    for p in paths:
        chunks.append(f"===== {p} =====")
        chunks.append(p.read_text())
    return "\n".join(chunks)


def summarize(text: str) -> str:
    from anthropic import Anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.stderr.write("ANTHROPIC_API_KEY is required for --summarize\n")
        sys.exit(2)

    model = os.environ.get("CHEAP_MODEL", DEFAULT_MODEL)
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=(
            "You summarize file contents tersely. Output only the summary. "
            "No preamble, no closing remarks, no meta-commentary."
        ),
        messages=[{"role": "user", "content": text}],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump file contents; optional Haiku summary.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()

    for p in args.paths:
        if not p.is_file():
            sys.stderr.write(f"not a file: {p}\n")
            sys.exit(1)

    text = dump(args.paths)
    if args.summarize:
        sys.stdout.write(summarize(text))
    else:
        sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
