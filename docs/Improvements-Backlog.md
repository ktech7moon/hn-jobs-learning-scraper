# Improvements Backlog

Ideas worth keeping but not building now. Every entry has a **trigger
condition** — the specific event that brings it back. No trigger,
no entry. When a trigger fires, move the item into a slice plan;
don't grow this file into a wishlist.

---

## Phase 2 candidates

- **Per-call parallelism on the naive path** — the 6 min 39 s
  wall-clock on Slice 1's live run is dominated by ~317 sequential
  Haiku calls at ~1.2 s each. A bounded thread / asyncio pool
  (e.g. 8–16 in flight) would slash that by an order of magnitude.
  Deliberately not done in Slice 1: a slow naive path is part of
  the demo's headline (graduated path looks dramatically faster).
  TRIGGER: a client requests a "fast naive baseline" or wants the
  naive path itself to be production-quality, not a foil.

- **Multi-thread support (scrape last 6 months of "Who's Hiring")** —
  TRIGGER: a client asks for trend analysis across multiple months
  in a discovery call.

- **Email digest delivery** — TRIGGER: the portfolio piece converts
  into an actual subscription product.

- **Other HN threads (Show HN, Ask HN)** — TRIGGER: same client asks
  for broader HN coverage.

- **Slack / Discord webhook output** — TRIGGER: a client requests
  team-channel delivery.

---

## Infrastructure deferrals

- **Database (SQLite or Postgres) for job history** — TRIGGER: we
  need to deduplicate jobs across runs, OR a client asks for a
  searchable history of past hiring threads.

- **Web UI (any flavor)** — TRIGGER: a client buyer cannot or will
  not run a CLI and the deal depends on a hosted demo.

- **Cron / scheduler** — TRIGGER: the digest needs to run unattended
  on a recurring cadence as part of a paid engagement.

- **Production deployment (cloud, container, etc.)** — TRIGGER: the
  project leaves "runs on my laptop" status and is sold as a service.

---

## Open issues

- **Telemetry accounting: digest header vs `hn-scraper compare` disagree
  on graduated runs.** Same May v3 graduated run reports different
  numbers in two places: the digest header at
  `data/digests/47975571-graduated.md` says **$0.3462 / 40 calls**, and
  `hn-scraper compare` says **$0.3782 / 41 calls**. Gap is 1 call /
  $0.0320. Root cause unknown — likely different scoping (digest
  may count extraction-only calls; compare may include the Opus
  digest-header-polish call and/or one extra row) but not verified.
  ACTION: trace which calls each path includes, pick a canonical
  truth, regenerate the digest or annotate the discrepancy.
  TRIGGER: Slice 3 polish pass — the README and Loom both quote one
  of these numbers, so they must agree before the repo is publicized
  more widely.
