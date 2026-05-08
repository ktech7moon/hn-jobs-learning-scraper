# ADR 001 — Thread discovery for the naive run

**Date:** 2026-05-08
**Status:** Accepted
**Slice:** 1

## Context

The naive run needs to identify "the most recent HN Who's Hiring
thread" without prior knowledge. Three paths considered:

- **(a) Playwright on `/submitted?id=whoishiring`.** The
  `whoishiring` HN account posts the monthly "Ask HN: Who is
  hiring?" thread. Its submitted page lists those posts in
  reverse-chronological order. Pure browser scrape; no API.
- **(b) Algolia HN search API.** `https://hn.algolia.com/api/v1/...`
  with a query for "Who is hiring" by `whoishiring`. Single
  HTTP call, no browser.
- **(c) Require `--thread-id` from the user.** No discovery at
  all; the caller specifies the thread.

## Decision

(a) is the primary path. (c) is supported as `--thread-id` for
reproducibility (CI, demos, and re-runs against a known good
thread). (b) is **explicitly excluded** from Slice 1.

## Why

The whole project is a demonstration of the Autobrowse pattern:
the naive path uses browser rendering, the graduated path uses a
discovered API. If we used Algolia in the naive path we'd
short-circuit the demo's headline — there'd be nothing meaningful
for the learning loop to discover. Browser-scraping the submitted
page keeps the naive path expensive on purpose.

## How to apply

- `naive_scraper.find_latest_thread()` opens
  `https://news.ycombinator.com/submitted?id=whoishiring`,
  reads the first listed story whose title matches
  `Ask HN: Who is hiring`, returns its item id and metadata.
- The CLI accepts `--thread-id <int>`; when provided, discovery
  is skipped and that id is fetched directly.
- Politeness: one Playwright page load, ~1 s pause between
  navigations. Honors HN's `robots.txt` (the comment pages are
  not disallowed).
