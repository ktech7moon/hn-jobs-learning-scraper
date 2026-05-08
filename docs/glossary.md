# Glossary

Domain terms used in this project. Add a term here before using it
in code or docs (Working Agreement #6).

- **Thread** — A specific HN "Who's Hiring" submission for a given
  month, identified by an HN item id (e.g. the comments page at
  `https://news.ycombinator.com/item?id=<id>`).
- **Comment** — A child item under the thread. Top-level comments
  are job postings; replies are usually conversation, not jobs.
- **Posting** — The semantic concept of a single hiring posting,
  regardless of source format. Top-level comments map 1:1 to postings.
- **Job** — The structured record extracted from a posting (company,
  role, location, remote/hybrid/onsite, salary, contact, raw_text).
- **Naive run** — End-to-end pipeline that uses Playwright to render
  and parse the HN comment page. Slow, expensive, but works on day
  one with no domain knowledge.
- **Discovery iteration** — One pass of the Autobrowse learning loop:
  the agent forms a hypothesis about a faster path, tries it,
  inspects the result, refines.
- **Graduated skill** — The `SKILL.md` produced when the learning
  loop finds a stable, faster strategy. Self-contained, human-readable,
  loaded by future runs to skip the discovery phase.
- **Graduated run** — End-to-end pipeline that uses the graduated
  `SKILL.md` (in this project: direct Firebase API calls + Haiku
  extraction). Cheap and fast.
