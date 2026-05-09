---
name: who-is-hiring
description: Scrapes monthly "Ask HN: Who is hiring?" threads into clean per-posting plain text, ready for an extraction LLM. Use when given an HN hiring thread (id or URL), or trigger phrases like "who is hiring", "HN jobs", "Ask HN hiring thread", "scrape HN hiring".
---

# who-is-hiring

## Problem and approach

Monthly "Ask HN: Who is hiring?" threads contain a few hundred top-level comments, one per job posting. The naive approach — driving a headless browser (Playwright) against `news.ycombinator.com` — works but is slow and expensive: it pays the cost of HTML rendering, pagination ("More" links), and per-page round-trips for content that is fundamentally a flat list of items.

The discovered approach uses the public Hacker News Firebase API (`hacker-news.firebaseio.com/v0`). The thread item itself carries a `kids` array containing the complete ordered list of top-level comment IDs. Each ID is then fetched as an independent JSON document. No browser, no pagination, no auth, no rate-limit headers observed in discovery, and every request is independent so fetches parallelise freely.

## Why this beats the baseline

Baseline (Playwright) on thread 47975571:

- Wall clock: **6 min 39 s**
- Cost: **$0.4364**
- Comments seen: 317
- Jobs extracted: 326

The Firebase strategy fetches the same 317 top-level comments as `1 + 317 = 318` independent JSON GETs against a CDN-backed endpoint. Each individual response in discovery was 1–5 KB and returned in <1 s. With even modest concurrency (e.g. 32 in flight) the fetch phase collapses to seconds rather than minutes, and eliminates the entire browser-automation cost line from the bill (HTML parsing, JS execution, "More" link clicks, per-page navigation latency). The remaining cost is whatever the downstream LLM extractor charges per posting — which is the same in both strategies and is the floor we cannot go below.

What's eliminated:

- Headless browser startup and per-page render
- Pagination ("More" link discovery and clicking)
- HTML parsing of the full HN page chrome
- Sequential page-by-page wall-clock dependency

What remains:

- One small JSON fetch per top-level comment
- HTML-entity decoding inside the `text` field of each comment

## Endpoints

There are exactly two endpoints used.

### 1. Thread item — get the list of top-level comment IDs

```
curl https://hacker-news.firebaseio.com/v0/item/47975571.json
```

Response shape (truncated):

```json
{
  "by": "whoishiring",
  "descendants": 317,
  "id": 47975571,
  "kids": [47975619, 47975944, 48069453, 48070114, ...],
  "score": 1,
  "text": "...",
  "time": 1714579200,
  "title": "Ask HN: Who is hiring? (May 2026)",
  "type": "story"
}
```

The `kids` array is the complete, ordered list of top-level comment IDs. For thread 47975571 it contained 317 IDs, matching the Playwright baseline exactly. No pagination is needed — `kids` is not truncated.

### 2. Comment item — get one posting

```
curl https://hacker-news.firebaseio.com/v0/item/48070114.json
```

Response shape (representative):

```json
{
  "by": "somecompany",
  "id": 48070114,
  "parent": 47975571,
  "text": "ACME Corp | Senior Backend Engineer | Berlin or Remote (EU)<p>We&#x27;re hiring ...<p>Stack: Python, Postgres. Apply: <a href=\"mailto:jobs@acme.example\">jobs@acme.example</a>",
  "time": 1714583000,
  "type": "comment",
  "kids": [48070500, 48070611]
}
```

`parent` equals the thread ID for top-level comments. `kids` on a comment item is replies — **ignore for this skill**, only top-level comments are postings.

## Parsing rules

To turn the raw API responses into clean per-posting plain text:

1. Fetch the thread item. Read `kids`. This is your full list of comment IDs in display order.
2. For each comment ID, fetch the comment item. Fetches are independent — parallelise.
3. **Filter** each fetched comment, keeping only those where ALL of:
   - The response is a non-null JSON object (deleted items can return `null` or an object with `deleted: true`).
   - `deleted` is falsy (missing, `false`, or `null`).
   - `dead` is falsy (missing, `false`, or `null`).
   - `text` is present and non-empty after stripping whitespace.
4. **HTML-to-plain-text conversion** of the `text` field, in this order:
   1. Replace `<p>` (and `<p />`, `</p>`) with a paragraph break (`\n\n`). HN uses `<p>` as a separator between paragraphs, not as a wrapping tag.
   2. Replace `<a href="URL">TEXT</a>` with `TEXT (URL)` — or just `URL` if `TEXT == URL`. Preserves the link target for the extractor.
   3. Strip all remaining HTML tags (`<i>`, `</i>`, etc.).
   4. Decode HTML entities (`&#x27;` → `'`, `&amp;` → `&`, `&gt;` → `>`, `&lt;` → `<`, `&quot;` → `"`, etc.). Use a standard HTML-entity decoder, not a hand-rolled regex.
   5. Collapse runs of 3+ newlines to 2; trim leading/trailing whitespace.
5. Emit one record per surviving comment containing at least: `id`, `by`, `time`, and the cleaned `text`. Pass `text` to the extraction LLM.

## Edge cases

- **Deleted comment.** Item exists but has `deleted: true` and no `text`. Rule: skip.
- **Dead comment** (killed by moderation / flags). Item has `dead: true`. Rule: skip.
- **Item returns `null`.** Firebase returns the JSON literal `null` for IDs that no longer resolve. Rule: skip.
- **Missing `text` field on a non-deleted comment.** Empty posting. Rule: skip — there is nothing for the extractor to read.
- **HTML-encoded entities in `text`** (`&#x27;`, `&amp;`, etc.). Rule: decode entities as the last text-transform step (after tag stripping) so partial-encoded tag-looking sequences inside text don't get stripped.
- **`<p>` as separator, not wrapper.** HN does not emit `</p>`. Rule: treat `<p>` as `\n\n` and don't expect balanced tags.
- **Links via `<a href="...">`.** Rule: preserve URL in plain text — extractor needs apply-to URLs.
- **Replies (`kids` on a comment item).** Not job postings; commentary. Rule: ignore. This skill only walks one level deep from the thread.

## Limitations

- **Top-level only.** This skill does not recurse into reply threads. If a posting's apply-info lives in a reply rather than the top-level comment, it will be missed. Discovery did not find evidence this happens, but it is not ruled out.
- **No retry/backoff strategy specified.** Discovery saw only 200s on a handful of fetches. A production run of 300+ requests should add per-request retry with exponential backoff; concrete tolerance numbers are untested in this iteration.
- **No concurrency ceiling established.** The dossier asserts the API "handles concurrent requests well" based on the Firebase architecture, but no load test was run. Start conservatively (e.g. 16–32 concurrent) and only raise if clean.
- **Job extraction itself is out of scope.** This skill produces clean text per posting. Parsing role/company/location/remote/comp out of that text is the downstream LLM extractor's job.
- **Thread discovery is out of scope.** The thread ID must be supplied. Finding "this month's" hiring thread (via the `whoishiring` user's submissions) is a separate concern.
- **Convergence not formally reached** in the discovery loop (budget exhausted at iteration 8). The endpoint, schema, and parsing rules are established and were exercised against four real comment IDs (47975619, 47975944, 48069453, 48070114), all returning 200 with the expected shape. End-to-end verification across all 317 IDs was not performed in discovery.
- **Extraction-LLM tier matters more than the fetch strategy.** This skill eliminates the browser; the per-posting LLM extraction is now the dominant cost and wall-clock contributor. On a standard-tier Anthropic account, Sonnet 4.6's 50 RPM / 30K input-tok-per-min ceiling makes a Haiku-driven graduated run roughly an order of magnitude faster than a Sonnet-driven one. The graduated CLI defaults to Haiku for that reason; pass `--model claude-sonnet-4-6` if your account has the rate-limit budget for it (and consider `--max-workers 4` to avoid SDK retry storms).

## Reasoning trail

The discovery loop went straight to the Firebase API on iteration 1 rather than scraping HTML, on the hypothesis that HN exposes its data model directly. The thread fetch immediately confirmed that `kids` contains all 317 comment IDs — matching the baseline's comment count exactly — which removed any need to deal with HN's "More" pagination. Iterations 3, 5, 6, and 8 sampled four different comment IDs to confirm the comment item shape was stable: same fields, same HTML-encoded `text`, same `parent` pointing back at the thread. The HTML conventions (`<p>` as separator, `&#x27;` for apostrophe, `<a href>` for links, `<i>` for italics) were observed directly in those samples and dictate the parsing rules above. The strategy is two endpoints and one text-cleaning pipeline; there was nothing further to discover within the budget.
