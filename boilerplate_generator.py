#!/usr/bin/env python3
"""Repo-root helper: generate sample / boilerplate content via Haiku.

Takes a description string and asks Haiku
(``claude-haiku-4-5-20251001`` or whatever ``CHEAP_MODEL`` overrides
to) to produce the requested artifact with a strict "no preamble,
no explanations, output only" system prompt.

For this project the most likely use is generating synthetic
HN-style comment HTML for fixtures in ``samples/`` so tests and
the digest layout can be exercised without scraping the real site.
"""

from __future__ import annotations

import argparse
import os
import sys

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "You generate boilerplate / sample content as requested. "
    "Output ONLY the content. No preamble, no closing remarks, "
    "no markdown code fences unless the requested artifact is "
    "itself markdown, no meta-commentary, no apologies, no "
    "'here is...' phrasing. Just the artifact."
)


def generate(description: str, max_tokens: int) -> str:
    from anthropic import Anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.stderr.write("ANTHROPIC_API_KEY is required\n")
        sys.exit(2)

    model = os.environ.get("CHEAP_MODEL", DEFAULT_MODEL)
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": description}],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample / boilerplate via Haiku.")
    parser.add_argument("description", help="What to generate. Be specific.")
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()

    out = generate(args.description, args.max_tokens)
    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
