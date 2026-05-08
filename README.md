# hn-jobs-learning-scraper

Autobrowse-pattern learning scraper for Hacker News "Who's Hiring"
threads — first run uses browser automation, graduated runs use
the discovered Firebase API for ~10× cost reduction.

**Status:** Pre-MVP (scaffolding only). Slice 1 not yet started.
This README will be rewritten in the polish slice.

---

## What it does (planned)

1. **Naive run** (`hn-scraper naive`). Playwright fetches the most
   recent HN "Who's Hiring" thread, parses the rendered comments,
   extracts a structured `Job` record per top-level comment via
   Haiku, and writes a Markdown digest. Cost and latency are
   logged.
2. **Learning loop** (`hn-scraper learn`). The Autobrowse loop
   iterates, discovers the public HN Firebase API at
   `https://hacker-news.firebaseio.com/v0/`, and graduates a
   self-contained `SKILL.md`.
3. **Graduated run** (`hn-scraper graduated`). Loads the `SKILL.md`
   and runs the cheaper API-driven path. Same digest format.
4. **Compare** (`hn-scraper compare`). Reads the JSONL telemetry
   and prints a table: total cost, total latency, jobs extracted,
   $ per job — naive vs. graduated.

---

## Getting Started

```bash
# clone
git clone <this-repo> hn-jobs-learning-scraper
cd hn-jobs-learning-scraper

# environment
python3.11 -m venv .venv      # 3.11+ works; this repo was scaffolded on 3.13
source .venv/bin/activate

# install
pip install -e ".[dev]"
playwright install chromium

# config
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

# Browserbase Autobrowse skills (used in Slice 2)
npx skills add browserbase/skills

# verify
hn-scraper version
hn-scraper --help
```

---

## Project Structure

```
hn_scraper/      # the package
  cli/           # click entrypoint
  prompts/       # versioned prompt .md files
  skills/        # graduated SKILL.md lands here
  config.py      # pydantic-settings
  llm.py         # the only place the Anthropic SDK is touched
  logging_setup.py
  models.py
  naive_scraper.py
  learner.py
tests/
samples/         # synthetic HN-style fixtures (no real-content commits)
data/            # gitignored — JSONL telemetry, generated digests
docs/
  decisions/     # ADRs
  slices/        # one per completed slice
  Improvements-Backlog.md
  glossary.md
  architecture.md
cheap_reader.py            # repo-root helper, no LLM by default
boilerplate_generator.py   # repo-root helper, Haiku, no preamble
```

---

## Roadmap

- **Slice 1 — Naive scraper.** End-to-end Playwright path producing
  a real digest with cost/latency captured.
- **Slice 2 — Learning loop + graduation.** Autobrowse loop
  discovers the Firebase API; Opus authors the graduated `SKILL.md`;
  `compare` shows the cost/latency delta.
- **Slice 3 — Polish.** Marketing-grade README rewrite, architecture
  diagram, Loom demo script, v1.0.0 tag.

---

## For contributors and Claude Code sessions

See [CLAUDE.md](./CLAUDE.md) for the operating manual and
[STATUS.md](./STATUS.md) for the current state and the single
next action.

---

## License

MIT — see [LICENSE](./LICENSE).
