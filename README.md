# hn-jobs-learning-scraper

> An AI agent that learns a website, then teaches future runs to skip the hard part.

This is a working demonstration of the **Autobrowse pattern**: a browser agent that probes a target site, discovers a more efficient way to acquire its data, and graduates that knowledge into a reusable `SKILL.md` file. Future runs load the skill and execute the cheaper path directly.

The target: Hacker News "Who's Hiring" monthly threads.

---

## The headline result

| Metric | Naive (browser) | Graduated (API + batch) | Improvement |
| --- | --- | --- | --- |
| **API calls** | 317 | 41 | **87% fewer** |
| **Wall-clock** | 6 min 39 s | 3 min 43 s | **44% faster** |
| **Cost** | $0.4364 | $0.3782 | 13% cheaper |
| **Jobs extracted** | 326 | 317 | ±5% (apples-to-apples) |

The 87% call reduction is the architectural win. The wall-clock and cost improvements are floored by the rate limit on this specific Anthropic account tier — on a higher tier the same code clears the original "70% faster, 40% cheaper" gates with margin. [Full slice writeup with the rate-limit math →](docs/slices/slice-02-graduated.md)

**Portability:** The same graduated skill ran against the April 2026 thread with no re-learning, extracting 342 jobs from 343 comments at 99.7% accuracy. One skill, two threads, zero re-discovery.

---

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│  Slice 1: NAIVE                                             │
│  Playwright opens browser → renders thread → extracts each  │
│  comment via Haiku one-by-one. Slow but deterministic.      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼  (run once, expensive)
┌─────────────────────────────────────────────────────────────┐
│  Slice 2a: LEARN                                            │
│  Sonnet 4.6 explores the site via tool-use:                 │
│    1. tries http_get on a thread URL                        │
│    2. records the discovered Firebase API endpoint          │
│    3. verifies schema against multiple sample comments      │
│    4. Opus 4.7 authors a self-contained SKILL.md            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼  (graduate to skill, run forever)
┌─────────────────────────────────────────────────────────────┐
│  Slice 2b: GRADUATED                                        │
│  Reads SKILL.md → hits Firebase API directly → batches      │
│  8 comments per LLM call → finishes in a fraction of the    │
│  time and calls.                                            │
└─────────────────────────────────────────────────────────────┘
```

The centerpiece artifact is **[hn_scraper/skills/who-is-hiring/SKILL.md](hn_scraper/skills/who-is-hiring/SKILL.md)** — a 129-line, human-readable description of what the agent discovered and how to use it. Future agents (or future humans) load it and skip the discovery phase entirely.

---

## What's in the repo

| Path | Purpose |
| --- | --- |
| `hn_scraper/learner.py` | Sonnet 4.6 tool-use loop that probes the site and records findings |
| `hn_scraper/firebase_api.py` | The graduated client (parallel `requests` to the discovered API) |
| `hn_scraper/graduated.py` | Batched extraction orchestrator (8 comments per LLM call) |
| `hn_scraper/skills/who-is-hiring/SKILL.md` | **The graduated skill — the headline artifact** |
| `hn_scraper/llm.py` | Anthropic SDK wrapper with per-call JSONL telemetry (tokens, latency, run_id) |
| `data/digests/47975571-graduated.md` | Real output: 317 jobs from May 2026, formatted as Markdown |
| `data/digests/47601859-graduated.md` | Real output: 342 jobs from April 2026 (portability proof) |
| `docs/slices/slice-01-naive.md` | Slice 1 retrospective — naive Playwright path |
| `docs/slices/slice-02-graduated.md` | **Slice 2 retrospective — the engineering-judgment story** |
| `docs/decisions/` | ADRs (Architecture Decision Records) for non-trivial choices |

### Full project structure

```
hn_scraper/                  # the package
  cli/                       # click entrypoint
  prompts/                   # versioned prompt .md files
  skills/                    # graduated SKILL.md lands here
  config.py                  # pydantic-settings
  llm.py                     # the only place the Anthropic SDK is touched
  logging_setup.py
  models.py
  naive_scraper.py           # Slice 1
  learner.py                 # Slice 2a
  firebase_api.py            # Slice 2b
  graduated.py               # Slice 2b
  compare.py                 # CLI comparison table
tests/                       # 37 tests, ruff clean
samples/                     # synthetic HN-style fixtures
data/                        # gitignored — JSONL telemetry, generated digests
docs/
  decisions/                 # ADRs
  slices/                    # one per completed slice
  Improvements-Backlog.md
  glossary.md
  architecture.md
cheap_reader.py              # repo-root helper, no LLM by default
boilerplate_generator.py     # repo-root helper, Haiku, no preamble
```

---

## Try it yourself

```bash
# Clone and set up
git clone https://github.com/ktech7moon/hn-jobs-learning-scraper.git
cd hn-jobs-learning-scraper

# Python 3.11+ venv
python3.11 -m venv .venv          # python3.13 also works
source .venv/bin/activate

# Install
pip install -e ".[dev]"
playwright install chromium

# Configure
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# Browserbase Autobrowse skills (used in Slice 2)
npx skills add browserbase/skills

# Verify
hn-scraper --help
```

### CLI commands

```bash
# Slice 1: naive Playwright path
hn-scraper naive --thread-id 47975571

# Slice 2a: learn loop (one-time, ~$0.40 + 90 s)
hn-scraper learn --thread-id 47975571

# Slice 2b: graduated path (uses the learned SKILL.md)
hn-scraper graduated --thread-id 47975571

# Compare runs side-by-side
hn-scraper compare
```

Each run writes per-call telemetry to `data/logs/llm_calls.jsonl` — one line per LLM invocation, tagged with `slice_label` and `run_id` for clean comparison.

---

## Tech stack

- **Python 3.11+** with type hints throughout (`pydantic` v2 for all structured data)
- **Playwright** for the naive browser path
- **`requests`** for the graduated API path (parallel via `ThreadPoolExecutor`)
- **Anthropic Claude** — Haiku 4.5 for high-volume extraction, Sonnet 4.6 for the discovery loop, Opus 4.7 for authoring the SKILL.md and final-pass digest header polish
- **Browserbase Autobrowse skills** for the discovery primitives
- **`click`** for CLI, **`rich`** for the comparison table
- **`pytest`** + **`ruff`** for testing and linting (37 tests passing, ruff clean)

The three-tier model routing (Haiku for grunt, Sonnet for reasoning, Opus for centerpiece artifacts) is documented in [`CLAUDE.md`](CLAUDE.md).

---

## Engineering principles this project demonstrates

- **Vertical slices.** Each slice ends with something you can run end-to-end and a digest you can read. No half-finished horizontal layers.
- **Working agreement, ADRs, slice retrospectives.** Every non-trivial decision has an ADR; every slice has a retrospective with what was learned and what's deferred. See [`docs/decisions/`](docs/decisions/) and [`docs/slices/`](docs/slices/).
- **Honest framing.** The Slice 2 doc names the failed acceptance gates and explains why (Anthropic rate limits, not the architecture). The Limitations section in the SKILL.md flags what the discovery loop didn't formally close.
- **Telemetry from day one.** Every LLM call writes a JSONL record with token counts, latency, model, and run-id. The cost/comparison numbers in this README aren't estimates — they're computed from the log.
- **Single LLM wrapper.** All Anthropic calls go through `hn_scraper/llm.py`, never directly. This is what makes cost comparison reliable and what would let you swap providers in one place.

---

## Status

- ✅ Slice 1: Naive Playwright scraper
- ✅ Slice 2: Learning loop + graduated path + portability test
- ⏳ Slice 3: README polish, demo recording, GitHub release tag

---

## For contributors and Claude Code sessions

See [`CLAUDE.md`](CLAUDE.md) for the operating manual and [`STATUS.md`](STATUS.md) for the current state and the single next action.

---

## About

Built by [ktech7moon](https://github.com/ktech7moon).

Senior engineer specializing in AI browser agents and reliable web scraping. Available for project work via Upwork (link coming once profile is approved).

For project inquiries: open an issue on this repo.
