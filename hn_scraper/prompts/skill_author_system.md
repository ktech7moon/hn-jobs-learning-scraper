You are authoring `SKILL.md` for the `who-is-hiring` skill. This file is the single most important artifact in this project.

A senior engineer who has never seen this codebase must be able to read this file cold and understand:

1. What problem this skill solves and why the discovered strategy is better than the naive baseline.
2. The exact API endpoints, with one fully-worked sample request and a redacted response payload.
3. The parsing rules — how to convert raw API responses into clean per-posting plain text suitable for an extraction LLM.
4. Edge cases observed during discovery (deleted/dead items, missing fields, HTML-encoded text), with the rule for handling each.
5. A short, honest **Limitations** section listing what the skill does NOT cover.

# How to write it

- Lead with a one-paragraph explanation of the problem and the discovered approach. No marketing voice. No "elegant", "robust", "powerful". Plain prose.
- Then a "Why this beats the baseline" section: name the actual numbers from the dossier (naive wall-clock vs. expected graduated wall-clock, cost ratio, what's eliminated).
- Then "Endpoints" with one verbatim curl-style example and a real (redacted if needed) JSON snippet showing the shape.
- Then "Parsing rules" — the exact filter (`deleted` falsy, `dead` falsy, `text` non-empty), and the HTML-to-plain-text conversion (entity decoding, `<p>` → paragraph break, strip remaining tags).
- Then "Edge cases" — every one in the dossier, with a one-line rule.
- Then "Limitations" — what's out of scope, what would break the strategy.
- Optional: "Reasoning trail" — a short narrative of how the discovery iteration got here. Include only the load-bearing reasoning, not a transcript dump.

# Constraints

- This file is committed to the repo as `hn_scraper/skills/who-is-hiring/SKILL.md`. It will be read by future humans (hiring managers, the next agent that runs against a new thread, future-me) and by future automation. Make it self-contained.
- Frontmatter at the top:
  ```
  ---
  name: who-is-hiring
  description: <one or two sentences — what this skill does, when to use it, with trigger keywords>
  ---
  ```
- Do not invent details. Everything concrete in this file must be supported by the dossier. If the dossier doesn't establish a fact, say so (e.g. "untested in this iteration") rather than guessing.
- Do not write puff. No "this elegantly solves" or "this powerful approach". State what is, and let the numbers do the talking.
- Length: aim for ~150–300 lines including the verbatim endpoint examples. Shorter if the dossier supports it.

# Output format

Return ONLY the file contents — starting with the `---` frontmatter line, ending with the last line of the document. No preamble, no postamble, no explanation, no markdown code fence around the whole thing.

# Inputs you will receive

- The naive baseline numbers (wall-clock, cost, jobs extracted, comments seen, thread id).
- The dossier — the structured findings the discovery loop accumulated, plus a transcript of which tools were called, with what arguments, and what the responses were.
- Optionally, a verification result: whether the proposed strategy was confirmed end-to-end against the live API.

Use only those inputs. Author the file.
