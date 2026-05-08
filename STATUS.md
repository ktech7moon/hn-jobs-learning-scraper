# hn-jobs-learning-scraper — Status

**Updated:** 2026-05-08 (Slice 1 complete)

## You are here
Slice 1 complete and accepted. Naive Playwright path produces a
real Markdown digest with token-derived cost and wall-clock time.
Latest live run on HN thread 47975571: 326 jobs in 6 min 39 s for
$0.4364. Slice writeup at
[docs/slices/slice-01-naive.md](docs/slices/slice-01-naive.md).
`browserbase/skills` not yet installed (Slice 2).

## Next action
Approve Slice 2 plan: Autobrowse learning loop targeting the same
thread, with the goal of discovering the HN Firebase API and
graduating a `hn_scraper/skills/who-is-hiring/SKILL.md`.

## Recent decisions (most recent first)
- 2026-05-08: `extract_job` returns `list[Job]` so multi-role
  comments (Haiku occasionally emits a top-level JSON list)
  fan out to one record per role. Recovered 32 postings on the
  re-run vs. the first naive run. The whole list is no longer
  dropped because of one bad element.
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
