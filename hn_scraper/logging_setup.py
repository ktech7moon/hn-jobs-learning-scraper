"""Logging configuration for hn-scraper.

Idempotent: calling :func:`setup_logging` twice is safe. Logs go to
stderr so CLI output (the digest, version string, etc.) on stdout
stays parseable. Noisy third-party loggers are pinned at WARNING.
"""

from __future__ import annotations

import logging
import sys

_NOISY = ("httpx", "anthropic", "urllib3")
_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        logging.getLogger().setLevel(level.upper())
        return

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)

    _CONFIGURED = True
