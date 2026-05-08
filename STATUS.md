# hn-jobs-learning-scraper — Status

**Updated:** 2026-05-08

## You are here
Scaffolding complete. Empty package, working CLI with placeholder
subcommands, `llm.py` wrapper with JSONL telemetry, `prompts/`
directory in place, `browserbase/skills` not yet installed.
Slice 1 (naive Playwright scraper) not started.

## Next action
Approve Slice 1 plan: naive Playwright scraper that fetches the
most recent HN "Who's Hiring" thread, extracts structured `Job`
records via Haiku, writes a Markdown digest, and logs total
cost/latency to `data/logs/`.

## Recent decisions (most recent first)
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
