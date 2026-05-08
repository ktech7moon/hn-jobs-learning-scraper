# CLAUDE.md — Operating Manual for hn-jobs-learning-scraper

This file is the persistent operating manual for any Claude Code
session working on this project. `STATUS.md` is the working memory.
Read both at the start of every session.

---

## Project Context

`hn-jobs-learning-scraper` is a public **portfolio piece** demonstrating
the **Autobrowse pattern**: an AI browser agent that learns a target
website through iteration and graduates a reusable `SKILL.md` file
that future runs load to skip the expensive discovery phase.

Target: Hacker News "Who's Hiring" monthly threads. The first run
uses Playwright to fetch and parse the rendered comment thread.
Through iteration the agent discovers the public Firebase API at
`https://hacker-news.firebaseio.com/v0/` and graduates a `SKILL.md`
that future runs use directly — collapsing expensive page rendering
into cheap API calls.

**Audience:** hiring managers reviewing my Upwork / Contra / Toptal
profiles. In 60 seconds of scanning the README and watching a 3-minute
Loom they need to see (1) I understand the Autobrowse / persistent-memory
pattern that defines current cutting-edge agent development; (2) I
write production-quality Python with proper observability and tests;
(3) the README is clear enough that a non-engineer founder can follow
what the project does and why it matters.

**Time-box:** ~8–16 hours of focused work across 2–3 vertical slices.
This is a portfolio piece, not a product. Polish on user-visible
surfaces (README, CLI output, the digest format, the graduated
`SKILL.md`) directly drives client conversion. Polish on internal
architecture matters only to the extent it makes the code legibly
senior-level.

**Non-obvious constraints:**
- No real API keys, no proprietary data, no private logic in the repo.
- Don't recreate Browserbase's own Craigslist demo verbatim. HN
  "Who's Hiring" is the target — different vertical, same pattern.
- Respect HN's robots.txt and rate limits. Use the public Firebase
  API once discovered; don't hammer the site.
- The graduated `SKILL.md` must be human-readable and self-contained —
  it's part of the demo. Anyone reading it should understand the
  discovered strategy without running the code.

---

## VENV REQUIREMENT — READ BEFORE RUNNING ANYTHING

**All Python work in this project happens inside `.venv`. Always.**

Before any `python`, `pip`, `pytest`, `ruff`, `playwright`, or
`hn-scraper` command:

1. Confirm `.venv` is active. Run `which python` — it must resolve
   to `.venv/bin/python`. Run `which pip` — it must resolve to
   `.venv/bin/pip`.
2. If either resolves anywhere else, **stop**. Activate the venv
   first: `source .venv/bin/activate` from the project root.
3. If `.venv` does not exist, **stop** and tell the user.

**Never** run `pip install` against system Python. **Never** run
`python` from outside the venv for this project. **No** `pipx`,
`--user`, or homebrew Python deps. **No** exceptions.

If a future session starts with `.venv` inactive, the first action
is `source .venv/bin/activate`. Verify with `which python` before
running anything else.

---

## Session Start Protocol

Always, in this order:

1. Read `STATUS.md` first. It tells you where the project is and
   the single next action.
2. Read `docs/Improvements-Backlog.md` if the task touches a
   deferred feature.
3. Activate `.venv` and verify (`which python` resolves into `.venv`).
4. Then proceed.

---

## Technical Stack

### Current phase
- Python 3.11+ on a standard `venv` (this machine ships 3.13;
  `requires-python = ">=3.11"`).
- `anthropic` (Claude SDK) — accessed only through `hn_scraper/llm.py`.
- `playwright` — naive path and the early discovery iterations.
- `requests` — graduated path, hitting the Firebase API.
- `pydantic` v2 — typed models for `Job`, `Posting`, `Digest`,
  `RunTelemetry`.
- `click` — CLI.
- `rich` — terminal output for the digest.
- Dev: `pytest`, `pytest-mock`, `ruff` (lint and format).
- **Browserbase skills (NOT a Python dep):** installed separately
  via `npx skills add browserbase/skills`. They run alongside the
  Python project, not inside it.

### Future stack — DO NOT install yet
- No database. JSONL logs in `data/logs/` are sufficient for the
  cost/latency comparison.
- No web UI. CLI + Markdown digest is enough for the Loom demo.
- No cron / scheduler. The user runs the CLI manually for the demo.
- No email integration. Digest goes to terminal and disk.
- No production deployment. This runs on the user's laptop.

---

## Three-Tier Model Routing

**Default down, not up.** Per-record extraction never touches Opus.
A bad `SKILL.md` hurts the portfolio; a slightly wonky job extraction
is recoverable.

| Tier      | Model ID                          | Use for                                                                                       |
| --------- | --------------------------------- | --------------------------------------------------------------------------------------------- |
| Cheap     | `claude-haiku-4-5-20251001`       | Per-comment Job extraction; format conversion; sample fixture generation. **Default.**       |
| Workhorse | `claude-sonnet-4-6`               | Learning-loop logic; debugging; integration tests; "try a different approach" agent decisions. |
| Premium   | `claude-opus-4-7`                 | Authoring the graduated `SKILL.md`; final README polish; final tone review on digest output. |

**Skip the LLM entirely** when a deterministic tool will do:
- Need to dump a file? `cat` / `Read` / `cheap_reader.py <path>` (no LLM).
- Need boilerplate sample data? `boilerplate_generator.py` (Haiku, no preamble).
- Need to find a symbol? `grep` / `rg` (no LLM).
- Need to count tokens? Use the SDK count helper, not a model call.

The per-job extraction pass processes 100+ comments per thread. Use
Haiku. Reserve Opus for high-leverage user-visible work.

---

## Design Principles

- Build vertical slices, not horizontal layers. Each slice ends with
  something runnable end-to-end that produces a real digest.
- Prefer simple solutions. No premature ORMs, frameworks, or
  abstractions. CLI-only — no UI.
- Type hints everywhere. Pydantic models for `Job`, `Posting`,
  `Digest`, and the cost/latency telemetry record.
- Ask before adding any dependency beyond the listed set.
- Ask before non-obvious architectural decisions (the `SKILL.md`
  format, the cost-tracking schema, the digest layout).
- No speculative features. Build what was asked.
- No half-finished implementations. Stop and say so if blocked.
- Comment the WHY, never the WHAT. The discovered Firebase API
  endpoints get a comment explaining HOW the agent found them
  and WHY using them is faster — that context is the demo.
- No defensive validation at internal boundaries. Validate at
  system boundaries only (HN HTML parsing, Firebase API responses,
  CLI input).
- Edit existing files when possible; create new files only when
  necessary.
- Never invent data. If a Loom demo needs a sample digest, run
  the real scraper against a real HN thread.
- Never hardcode API keys. Read from `hn_scraper/config.py` only.
- All LLM calls go through `hn_scraper/llm.py` — never call the
  Anthropic SDK directly from product code.

---

## Working Agreement

1. **SESSION START:** Read `STATUS.md` first, every time.
2. **SESSION END:** Update `STATUS.md` — bump Updated date, update
   "You are here", set exactly ONE Next Action, prepend any new
   decisions to Recent Decisions.
3. **ARCHITECTURE DECISIONS:** Any non-trivial decision (library
   choice, schema, API contract, model selection, error handling
   strategy) gets a new ADR in `docs/decisions/` before implementing.
   Format: `NNN-short-title.md`, sequentially numbered.
4. **SLICE COMPLETION:** When a slice is done, create
   `docs/slices/slice-NN-name.md` (goal, what was built, files
   changed, what was learned, known limitations, what's deferred).
   Add an entry to the Slice Log in CLAUDE.md.
5. **DEFERRED IDEAS:** Any idea worth keeping but not building now
   goes in `docs/Improvements-Backlog.md` WITH A TRIGGER CONDITION
   (the specific event that brings it back). No trigger = not in
   backlog.
6. **NEW DOMAIN TERMS:** Add to `docs/glossary.md` before using in
   code. (Likely terms: "thread", "comment", "posting", "graduated
   skill", "naive run", "graduated run", "discovery iteration".)
7. **DEPENDENCIES:** No new dependency without an ADR with at least
   one alternative considered.
8. **CLARIFYING QUESTIONS:** When the user's request is ambiguous,
   ASK before assuming. The user prefers a question over a wrong guess.
9. **CONFIRMATION BEFORE HIGH-BLAST-RADIUS ACTIONS:** Even with
   general authorization, stop and confirm before pushing to any
   remote, deletions, force-pushes, dropping data, sending external
   messages, or any irreversible action.
10. **EXACTLY ONE NEXT ACTION:** STATUS.md has exactly one. If you
    can't pick one, surface the tension; don't paper over it with
    a list.
11. **HONEST FRAMING:** If you do 3 of 5 things spec-compliant, name
    done / documented / deferred precisely. Never overstate.

---

## Claude Code Tool Discipline

- TodoWrite for any task with 3+ steps. Mark complete immediately,
  not in batches. One item `in_progress` at a time.
- Plan before non-trivial implementations. Plan, get user feedback,
  then edit.
- Parallel tool calls when independent. Don't serialize independent
  reads/searches.
- Edit > Write for existing files. Edit sends only the diff.
- Don't re-read a file you just edited.
- Use Read/Edit/Write — not `cat`/`sed`/`awk`/`echo>`. Reserve Bash
  for shell-only operations.
- Match response length to question complexity. Don't pad.
- Save long tool outputs to files: `cmd | tee /tmp/out.txt`, then
  Read selectively.

---

## Code-Writing Discipline

- No speculative features.
- No half-finished implementations.
- Comment the WHY, never the WHAT.
- No defensive validation at internal boundaries.
- No backwards-compat shims unless required.
- Edit existing files; create new files only when necessary.

---

## Git Discipline

- Small, atomic commits. One logical change per commit.
- Subject line ≤70 chars. Body explains the WHY.
- Never `git add -A` or `git add .` — add by name to avoid sweeping
  in secrets and binaries.
- Verify `.gitignore` covers `.env` before first commit.
- Never `--no-verify` to skip hooks unless authorized.
- Never amend a published commit.
- Never push to a remote without explicit user authorization.
- Destructive ops (force-push, hard-reset, `branch -D`, `clean -f`):
  never without explicit approval, never on `main`/`master`.

---

## LLM Integration Notes

- All LLM calls flow through `hn_scraper/llm.py`. Product code
  imports `call()` from there; it never imports `anthropic` directly.
- Every `call()` writes one JSONL line to `data/logs/llm_calls.jsonl`
  with timestamp, prompt name, model, token counts, latency,
  status, and a `slice_label` (e.g. `"naive"`, `"graduated"`,
  `"scaffolding"`) so we can later separate cost between the two
  paths for the demo.
- Message content is **never** logged (privacy). Only metadata.
- Prompts live in `hn_scraper/prompts/` as `.md` files and are
  loaded by `load_prompt(name, **kwargs)`. Prompts are versioned
  in git like code.

---

## Permissions

`.claude/settings.json` pre-authorizes routine commands (Edit/Write/Read,
`pip`, `pytest`, `ruff`, `make`, `git status`, etc.) and denies
destructive ones. A `PreToolUse` hook at
`.claude/hooks/pre-bash-firewall.sh` enforces a hard firewall on
every Bash call — including `--dangerously-skip-permissions` mode.
The hook blocks `rm`, destructive git ops, `sudo`, network-pipe-to-shell,
and `python -c` filesystem-mutation injections. **Hooks bypass the
bypass.** That's intentional. The hook depends on `jq`.

If you need to do something the firewall blocks, ask the user — do
not try to work around the hook.

---

## Project Structure

```
hn-jobs-learning-scraper/
├── hn_scraper/
│   ├── __init__.py            # __version__ = "0.1.0"
│   ├── config.py              # typed configuration (pydantic-settings)
│   ├── logging_setup.py       # logging configuration
│   ├── llm.py                 # Anthropic SDK wrapper with telemetry
│   ├── models.py              # Pydantic: Job, Posting, Digest, RunTelemetry
│   ├── cli/
│   │   └── __init__.py        # click entrypoint
│   ├── prompts/
│   │   ├── __init__.py        # load_prompt(name, **kwargs)
│   │   ├── extract_job.md     # used in Slice 1
│   │   └── README.md
│   ├── naive_scraper.py       # Slice 1
│   ├── learner.py             # Slice 2
│   └── skills/                # graduated SKILL.md lands here (Slice 2)
├── tests/
├── samples/                   # synthetic sample HN comment HTML
├── data/                      # gitignored, local-only
│   └── logs/
├── scratch/                   # gitignored, throwaway
├── docs/
│   ├── architecture.md
│   ├── glossary.md
│   ├── Improvements-Backlog.md
│   ├── decisions/
│   └── slices/
├── cheap_reader.py            # repo-root helper (no LLM by default)
├── boilerplate_generator.py   # repo-root helper (Haiku, no preamble)
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── STATUS.md
├── LICENSE
├── Makefile
├── .env.example
├── .gitignore
├── .editorconfig
└── .claude/
    ├── settings.json
    └── hooks/pre-bash-firewall.sh
```

---

## Slice Log

<!-- Append one bullet per completed slice. Format:
- YYYY-MM-DD — Slice NN: <name>. See docs/slices/slice-NN-name.md. -->

- 2026-05-08 — Slice 01: Naive Playwright scraper. 326 jobs from
  HN thread 47975571 in 6 min 39 s for $0.4364. See
  [docs/slices/slice-01-naive.md](docs/slices/slice-01-naive.md).
