# ADR 003 — Graduated discovery target: HN Firebase API

**Date:** 2026-05-08
**Status:** Accepted
**Slice:** 2

## Context

Slice 2's whole point is the Autobrowse pattern: a Sonnet-driven
loop iterates over the problem until it discovers a stable, cheap
strategy, then graduates a `SKILL.md` that future runs use to skip
the discovery phase.

For HN "Who's Hiring" threads we considered three discoverable
paths the loop could converge on:

- **(a) HN Firebase API** at `https://hacker-news.firebaseio.com/v0/`.
  Public, undocumented-on-the-site but widely known among HN
  developers. `item/<id>.json` returns the story with a `kids`
  array; each kid id maps to its own `item/<kid>.json` with a
  `text` field. No auth, no rate limit advertised.
- **(b) Algolia HN Search API** at `https://hn.algolia.com/api/v1/`.
  Higher-level; `search?tags=comment,story_<id>` returns hits
  with a `comment_text` field and pagination via `page` /
  `hitsPerPage`. Same data, less granular control.
- **(c) HN HTML rendered without JavaScript.** The comment pages
  are mostly server-rendered, so dropping Playwright in favor of
  `requests` + an HTML parser would speed up the naive path
  somewhat but doesn't change the strategy class.

## Decision

(a) is the target. Slice 2's learner is allowed to "discover"
either (a) or (b) on its own — both are correct answers — but the
SKILL.md author prompt instructs Opus to prefer (a) for the same
reason as below.

## Why

(a) gives one HTTP call per item with the smallest possible payload
and no server-side filtering surprises. The thread's `kids` array
is the canonical list of top-level comments — no pagination, no
"more" link to chase, no width=0 detection, no HTML scraping. The
graduated path becomes:

1. `GET item/<thread_id>.json` → read `kids`.
2. For each kid id (parallel): `GET item/<kid>.json` → keep entries
   where `deleted` and `dead` are falsy and `text` is non-empty.
3. Decode HTML entities, strip `<p>` tags, hand the plain text to
   Sonnet 4.6 for structured extraction.

A single sanity-check run confirms the math: thread 47975571 has
353 kids, of which 318 are visible (24 deleted, 11 dead, 24 with
no text — overlapping). Naive scraper saw 317. Within 1, which is
within HN's normal HTML-vs-API pagination drift.

(b) would also work but adds a layer of indirection — Algolia is
HN's hosted search index, not the canonical store. If the index is
behind real-time, postings are missed. (a) reads from the source.

(c) is in scope only as a fallback if the model can't find an API
within the 8-iteration budget; not the target.

## How to apply

- `hn_scraper/firebase_api.py` codifies the base URL and the two
  endpoint patterns that the graduated path actually calls.
- `hn_scraper/learner.py` runs the Sonnet 4.6 tool-use loop with
  bounded HTTP fetches; the agent reasons about the problem,
  proposes a strategy, verifies it, and records findings.
- Opus 4.7 takes the dossier and authors
  `hn_scraper/skills/who-is-hiring/SKILL.md`. Future graduated
  runs read that file for context, not to drive code — the
  discovered constants live in `firebase_api.py`. This mirrors
  Browserbase's autobrowse pattern: SKILL.md is human-readable
  documentation of the discovered strategy, loaded by future
  agents to short-circuit re-discovery.
- The graduated path is `requests` + a thread pool + per-comment
  Sonnet 4.6 extraction. Slice label `"graduated"` on every LLM
  call so `compare` can split costs.
