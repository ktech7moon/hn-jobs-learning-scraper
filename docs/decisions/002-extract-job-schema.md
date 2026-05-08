# ADR 002 — Extract-job schema and prompt contract

**Date:** 2026-05-08
**Status:** Accepted
**Slice:** 1

## Context

Each top-level comment in a Who's Hiring thread is, by HN
convention, a single hiring posting. The naive run sends each
comment's text to Haiku and expects a structured `Job` record back.

We need to decide:
1. What fields the `Job` model carries.
2. What the model returns when a comment is **not** a posting
   (off-topic, meta, "great list, thanks", etc.).
3. Whether to send the comment's HTML or its plain text.

## Decision

**`Job` fields (Slice 1):**

| Field           | Type                                              | Notes |
| --------------- | ------------------------------------------------- | ----- |
| `company`       | `str`                                             | Best-effort; use `"Unknown"` if missing. |
| `role`          | `str`                                             | A short title. May be a list ("SWE, EM") collapsed by the model. |
| `location_text` | `str`                                             | Raw location string from the posting. |
| `work_mode`     | `Literal["remote","hybrid","onsite","unspecified"]` | Inferred from the posting language. `unspecified` when ambiguous. |
| `salary_range`  | `str \| None`                                     | Free-form ("$150k–$200k", "€60-90k", `None` if absent). |
| `tech_stack`    | `list[str]`                                       | Empty list `[]` is the natural "not specified" sentinel. |
| `contact`       | `str \| None`                                     | Email / form URL / "see profile". `None` if absent. |
| `raw_text`      | `str`                                             | The comment's plain text, for traceability. |

**Not-a-posting sentinel:** the model returns
`{"not_a_posting": true}` when the comment is not a job posting.
The extractor returns `None` for those and they are dropped from
the digest.

**Input format:** plain text only. We extract `comment.text_content()`
from the rendered HN page and send that as the user message. The
system prompt is loaded from `extract_job.md`. Rationale: HN's
HTML wrapping (`<div class="commtext c00">`, `<a class="reply">`,
etc.) is pure noise to the model and inflates input tokens by
~30% with zero accuracy benefit. The earlier scaffolding stub
mentioned `comment_html`; this is the deliberate refinement.

## Why

`tech_stack` is high-signal for the digest's audience (hiring
managers eyeballing what's being asked for). `[]` reads cleanly
as "not specified" without an extra Optional wrapper. The
sentinel pattern keeps the LLM contract simple — one JSON shape
or the sentinel; no exception paths.

## How to apply

- `hn_scraper/models.py` defines `Job` exactly as above.
- `hn_scraper/prompts/extract_job.md` is the system prompt and
  enforces the JSON schema with explicit field names and the
  `not_a_posting` sentinel. The prompt is loaded with no kwargs
  (so `str.format` is not invoked, avoiding `{`/`}` escaping
  pain) and the comment text is passed as the user message.
- `naive_scraper.extract_job(text)` calls
  `llm.call(prompt_name="extract_job", model=settings.cheap_model,
  slice_label="naive", ...)`, parses the JSON output, and returns
  `Job | None`.
