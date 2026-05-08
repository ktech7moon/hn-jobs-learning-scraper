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
