"""HN Firebase API client used by the graduated path.

The base URL and endpoint patterns codified here are the artifact
of Slice 2's learning loop: the agent discovered them by reasoning
about the problem and verifying live, then graduated them into the
SKILL.md plus this module. Future graduated runs skip discovery
and call these helpers directly.

The API is undocumented on news.ycombinator.com but is published at
https://github.com/HackerNews/API. No auth, no key, no advertised
rate limit. We keep client-side concurrency bounded anyway out of
politeness (`MAX_CONCURRENT_FETCHES`).
"""

from __future__ import annotations

import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

BASE_URL = "https://hacker-news.firebaseio.com/v0"
ITEM_URL = f"{BASE_URL}/item/{{item_id}}.json"
USER_URL = f"{BASE_URL}/user/{{username}}.json"

DEFAULT_TIMEOUT_S = 10.0
MAX_CONCURRENT_FETCHES = 16

_logger = logging.getLogger(__name__)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "hn-jobs-learning-scraper/0.1 (+https://github.com/ktech7moon) "
                "graduated path; portfolio demo"
            ),
            "Accept": "application/json",
        }
    )
    return s


def get_item(item_id: int, *, session: requests.Session | None = None) -> dict[str, Any]:
    """GET ``/item/<id>.json``. Raises on HTTP error or JSON parse failure."""
    s = session or _session()
    resp = s.get(ITEM_URL.format(item_id=item_id), timeout=DEFAULT_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def fetch_kids(
    parent_id: int,
    *,
    session: requests.Session | None = None,
    max_workers: int = MAX_CONCURRENT_FETCHES,
) -> list[dict[str, Any]]:
    """Fetch every direct child of ``parent_id`` in parallel.

    Returns a list of raw item dicts in the order ``kids`` lists them
    (HN orders kids best-first). Items with ``deleted`` / ``dead`` set,
    or missing ``text``, are filtered out — those don't appear on the
    rendered HN page either.
    """
    s = session or _session()
    parent = get_item(parent_id, session=s)
    kid_ids: list[int] = parent.get("kids") or []
    _logger.info("firebase: parent=%d has %d kids", parent_id, len(kid_ids))

    def _fetch(kid_id: int) -> tuple[int, dict[str, Any] | None]:
        try:
            return kid_id, get_item(kid_id, session=s)
        except (requests.RequestException, json.JSONDecodeError) as exc:
            _logger.warning("firebase: kid %d fetch failed: %s", kid_id, exc)
            return kid_id, None

    by_id: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_fetch, k) for k in kid_ids]
        for fut in as_completed(futures):
            kid_id, item = fut.result()
            if item is not None:
                by_id[kid_id] = item

    visible: list[dict[str, Any]] = []
    for kid_id in kid_ids:
        item = by_id.get(kid_id)
        if item is None:
            continue
        if item.get("deleted") or item.get("dead"):
            continue
        if not item.get("text"):
            continue
        visible.append(item)
    _logger.info(
        "firebase: parent=%d kids=%d visible=%d (filtered deleted/dead/empty)",
        parent_id,
        len(kid_ids),
        len(visible),
    )
    return visible


# HN comment text comes back as escaped HTML: entities like &#x27; for
# apostrophes and <p> tags between paragraphs. The extraction prompt
# was written for plain text on the naive path, so we normalize here.
_TAG_RE = re.compile(r"<[^>]+>")


def comment_text_to_plain(html_text: str) -> str:
    """Convert HN's escaped-HTML comment text to plain text.

    Replaces ``<p>`` with double newlines (paragraph break), strips
    remaining tags, and unescapes HTML entities. Conservative — we
    don't try to preserve markdown-like structure.
    """
    if not html_text:
        return ""
    text = re.sub(r"<p[^>]*>", "\n\n", html_text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    return text.strip()
