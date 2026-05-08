# hn-jobs-learning-scraper — Status

**Updated:** 2026-05-08 (Slice 1 in flight)

## You are here
Slice 1 in progress. Naive Playwright scraper is being implemented:
auto-discovers the latest "Who's Hiring" thread via
`/submitted?id=whoishiring`, extracts `Job` records via Haiku,
groups by work_mode in a Markdown digest, captures cost/latency.
`browserbase/skills` not yet installed (Slice 2).

## Next action
Run `hn-scraper naive` end-to-end against a real HN thread and show
the user the digest output. No optimization or polish before that
review.

## Recent decisions (most recent first)
- 2026-05-08: Slice 1 scope locked: thread discovery via Playwright
  on `/submitted?id=whoishiring` (no Algolia — API discovery is
  Slice 2 territory). Job schema includes `tech_stack: list[str]`
  with `[]` as the natural "not specified" sentinel. Digest groups
  by work_mode, alphabetical by company within group, columns:
  Company · Role · Location · Salary · Tech Stack. Cost reporting
  appears in both digest header and the Slice 2 `compare` command.
- 2026-05-08: Use Python 3.13 (this machine ships 3.12 and 3.13;
  no 3.11 installed). `pyproject.toml` keeps `requires-python = ">=3.11"`
  and ruff `target-version = "py311"` so the codebase stays
  3.11-compatible. User approved.
- 2026-05-08: Target site is HN "Who's Hiring", not Craigslist.
  Reasoning: differentiated from Browserbase's own demo;
  audience-relevant; has a discoverable Firebase API for the
  graduation step.
- 2026-05-08: Two-slice plan plus polish slice. Time-boxed
  8–16 hours total.

## Open questions / blockers
- None yet.

## What's been ruled out
- No database. JSONL logs sufficient for cost/latency data.
- No web UI. CLI only.
- No real email sending. Digest goes to terminal and disk.
- No replication of Browserbase's Craigslist demo.
