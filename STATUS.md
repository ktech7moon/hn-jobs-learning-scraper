# hn-jobs-learning-scraper — Status

**Updated:** 2026-05-08 (Slice 2 complete, Slice 3 next)

## You are here
Slice 2 complete. The Autobrowse learning loop discovered the HN
Firebase API and graduated `hn_scraper/skills/who-is-hiring/SKILL.md`.
The graduated path runs ~44% faster and ~13% cheaper than the
naive baseline on this Anthropic account tier, with quality at 99.7%
extraction (317 jobs / 318 visible comments on May, 342 / 343 on
April). Wall-clock and cost gates from the Slice 2 brief did not
clear because Anthropic standard-tier rate limits (50 RPM /
30K input-tokens-per-min) impose a 3.2-minute floor on this thread
size; honest writeup in the slice doc flags this and projects the
higher-tier outcome. Portability test PASS — same SKILL.md, two
threads, no re-learning. Slice writeup at
[docs/slices/slice-02-graduated.md](docs/slices/slice-02-graduated.md).

## Next action
Slice 3 polish: README rewrite (60-second pitch + Slice 1 vs. Slice 2
side-by-side), 3-minute Loom recording, GitHub release with the
graduated SKILL.md prominently linked. User wants to review the
Slice 2 doc before kicking off Slice 3.

## Recent decisions (most recent first)
- 2026-05-08: Compare CLI auto-scopes to latest run per slice via
  `run_id` (uuid per CLI invocation, propagated into JSONL by
  `llm.set_current_run_id`). Time-gap heuristic (>300s) is the
  fallback for legacy rows. `--since` is the manual escape hatch.
- 2026-05-08: April digest no longer carries the May-thread
  baseline comparison line. `digest_header_polish_system.md`
  explicitly forbids inventing baselines; `graduated.py` injects
  `naive_baseline_*` keys only for thread 47975571.
- 2026-05-08: Graduated path defaults to Haiku batched (8 comments
  per LLM call). `--model` flag preserves the Sonnet path for
  callers on higher Anthropic tiers; `--batch-size` adjustable.
  Reversal of the original "Sonnet for graduated" instruction —
  Sonnet's 50 RPM ceiling on standard-tier accounts made the demo
  headline impossible.
- 2026-05-08: Discovered API target is HN Firebase
  (`hacker-news.firebaseio.com/v0/`). ADR
  [003](docs/decisions/003-graduated-discovery.md). Algolia ruled
  out (indirection layer); no-JS HTML ruled out (same strategy
  class as naive).
- 2026-05-08: Iteration budget for the learning loop = 8 (raised
  from 5 in the original plan). Loop ran 8/8 without formal
  `declare_convergence` but produced a substantively complete
  SKILL.md; Opus authored the file with a Limitations entry that
  flags the missing convergence honestly.

## Open questions / blockers
- None blocking Slice 3. The Slice 2 doc surfaces two improvements
  (stricter convergence, prompt caching) as Slice 3 candidates but
  they are not gating.

## What's been ruled out
- No database. JSONL logs sufficient for cost/latency data.
- No web UI. CLI only.
- No real email sending. Digest goes to terminal and disk.
- No replication of Browserbase's Craigslist demo.
- No SKILL.md as runtime input — graduated path uses
  `firebase_api.py` constants directly. SKILL.md is human / future-
  agent documentation.
