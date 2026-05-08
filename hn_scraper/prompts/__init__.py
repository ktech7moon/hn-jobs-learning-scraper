"""Prompt loader.

Each prompt is a ``.md`` file in this directory. Load with
``load_prompt("name")``; pass keyword arguments to substitute
``{var_name}`` placeholders via ``str.format``.

Prompts are versioned in git like code.
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: object) -> str:
    """Read ``<name>.md`` from this directory; format with kwargs if any."""
    path = _PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    if kwargs:
        return text.format(**kwargs)
    return text
