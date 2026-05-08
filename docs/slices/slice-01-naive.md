# Slice 01 — Naive Playwright scraper

**Status:** Complete (2026-05-08)
**Time spent:** ~4 hours including the post-acceptance fix.

## Goal

Stand up the naive end of the Autobrowse comparison: a Playwright-driven
scraper of the latest HN "Who's Hiring" thread that extracts structured
`Job` records via Haiku, writes a Markdown digest, and captures
real cost / latency telemetry. This is the baseline the graduated
path will beat in Slice 2.

## What was built

- `find_latest_thread(page)` — Playwright nav to
  `/submitted?id=whoishiring`, picks the first listed story whose
  title matches `Ask HN: Who is hiring`. Returns `ThreadMeta`.
- `fetch_top_level_comments(page, item_id, *, max_pages)` — paginated
  walker that follows `?p=N` until the "More" link disappears or the
  cap is hit; collects only `width=0` (top-level) comments and
  yields plain text.
- `extract_job(comment_text) -> list[Job]` — Haiku call via
  `llm.call(prompt_name="extract_job", slice_label="naive", ...)`.
  Honors a `{"not_a_posting": true}` sentinel. Returns one `Job` per
  posting object — including the case where the model returns a
  top-level **list** of objects (multi-role comments).
- `extract_jobs(comments)` — sequential driver with per-comment
  try/except so a single bad comment can't kill the run.
- `compute_run_metrics(...)` — reads `data/logs/llm_calls.jsonl`,
  filters by `slice_label` and a run-start timestamp, returns
  `(total_cost_usd, total_calls)` using the rates in
  `hn_scraper/pricing.py`.
- `render_digest(digest)` — Markdown: header with source, generation
  time, wall-clock, cost, and total counts; sections grouped by
  `work_mode` (Remote → Hybrid → Onsite → Unspecified), alphabetical
  by company within each section; columns Company · Role · Location ·
  Salary · Tech Stack. Em-dashes for empty fields.
- `run(thread_id, max_pages)` — top-level orchestrator. Default:
  auto-discover the latest thread, cap at 5 pages.

## Files changed

New:

- `hn_scraper/naive_scraper.py` — the slice's main module.
- `hn_scraper/pricing.py` — published-rate USD cost calc per model.
- `hn_scraper/prompts/extract_job.md` — strict-JSON system prompt
  with the `not_a_posting` sentinel contract.
- `samples/sample_comment.json` — synthetic fixture for tests.
- `tests/test_naive.py` — extraction, sentinel, fences, normalized
  modes, garbled output, top-level-list handling, scalar-output
  drop, JSONL cost rollup with slice/time filters, digest grouping
  and sorting.
- `docs/decisions/001-thread-discovery.md`
- `docs/decisions/002-extract-job-schema.md`

Modified:

- `hn_scraper/models.py` — concrete `Job`, `ThreadMeta`, `Digest`.
- `hn_scraper/cli/__init__.py` — wired `naive` with `--thread-id`
  and `--max-pages`.
- `STATUS.md` — Slice 1 progression entries.

## Live run results (thread id 47975571 — May 2026)

| Metric                  | First run (pre-fix) | Re-run (post-fix) |
| ----------------------- | ------------------- | ----------------- |
| Top-level comments      | 317                 | 317               |
| Haiku calls (`status=ok`) | 317               | 317               |
| Jobs extracted          | 294                 | **326**           |
| Wall-clock              | 6 min 45 s          | 6 min 39 s        |
| Token-derived USD cost  | $0.4348             | $0.4364           |

Group split on the re-run: Remote 139 · Hybrid 102 · Onsite 73 ·
Unspecified 12.

## What was learned

- **Haiku occasionally returns a top-level JSON list when the
  comment bundles multiple roles.** The first run logged
  `extract_job: non-JSON output, dropping. preview='[\n  {...'`
  and `'list' object has no attribute 'get'` for two such comments.
  Both were caught by the per-comment try/except and logged as
  warnings — the run completed, the rest of the digest was fine,
  and the failure was visible at the next code review pass. This
  is the JSONL telemetry plus per-call logging earning its keep:
  the bug surfaced from the data itself, not from a downstream
  customer report.
- **The fix recovered far more than the two known failures.**
  We expected ~2–6 extra postings (the literal failures observed).
  The actual gain was 32 (294 → 326). Many multi-role comments
  Haiku had been condensing into single records are now
  fanned out into one row per role, which is what the digest
  reader actually wants.
- **The 5 m 45 s wall-clock is dominated by sequential Haiku
  calls** (~317 × ~1.2 s). Per-call parallelism would slash this
  by an order of magnitude — but it's deliberately not done in
  Slice 1: a slow naive path is part of the demo's headline.
  Filed in `Improvements-Backlog.md` with a real trigger.

## Known limitations / honest framing

- **Token-budget truncation on very long multi-role comments.**
  Re-run still showed 2 dropped comments where Haiku started
  emitting a top-level list (`[\n  {\n    "company": ...`) but
  the response was cut off by `max_tokens=600`. `json.loads`
  rejected the truncated string. Cost-driven: bumping the budget
  blanket-style makes the demo's cost number worse for a
  marginal recovery. **Not** fixed in Slice 1. Candidate for the
  Slice 3 polish pass: detect truncation specifically (response
  `stop_reason == "max_tokens"`) and either retry with a higher
  cap or repair the partial JSON.
- **`compute_run_metrics` filter is timestamp + slice label.**
  Concurrent runs of the same slice would double-count. Fine for
  the manual-demo workflow Slice 1 is built for; not safe for
  unattended scheduling. Slice 2's `compare` will inherit the
  same constraint.
- **Pricing is approximate.** `hn_scraper/pricing.py` carries
  Anthropic's published list rates as of 2026-05. Real billing
  is whatever the invoice says. The digest header marks the cost
  as approximate; the comparison in Slice 2 will keep that
  framing.
- **Thread discovery picks the first matching submission.** That
  is correct in steady state because `whoishiring` posts on a
  predictable cadence, but if Anthropic's monthly post is delayed
  the auto-discover would still pick the previous month's
  thread. `--thread-id` is the workaround.

## What's deferred to Slice 2

- The Autobrowse iterative learning loop in `learner.py` —
  Sonnet-driven, runs against the same thread, discovers the HN
  Firebase API at `https://hacker-news.firebaseio.com/v0/`.
- Opus-authored `hn_scraper/skills/who-is-hiring/SKILL.md` —
  human-readable, self-contained, the centerpiece of the
  portfolio demo.
- `hn-scraper graduated` — pure `requests` against the discovered
  API + Haiku per posting; same digest format, slice label
  `"graduated"`.
- `hn-scraper compare` — reads JSONL, groups by `slice_label`,
  prints the side-by-side cost / latency / jobs / $-per-job table.
- `RunTelemetry` Pydantic model — formalizes the JSONL record
  shape now that `compare` actually reads it back.
- Truncated-list recovery (the 2 remaining dropped comments).
