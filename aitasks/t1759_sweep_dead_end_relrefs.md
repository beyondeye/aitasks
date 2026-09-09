---
priority: low
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [documentation, website]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1661
followup_kind: risk_mitigation
created_at: 2026-09-09 10:31
updated_at: 2026-09-09 11:27
---

## Origin

Risk-mitigation ("after") follow-up for t1707, created at Step 8d after implementation landed.

## Risk addressed

Addresses goal-achievement risk 2 of t1707's plan:

> Only two instances of the dead-end-relref class were found, by inspecting
> `ait artifact` alone; `check_links.py` cannot see this class by construction,
> so others may remain · severity: low

## Goal

Sweep `website/content/` for **mis-targeted** internal links: a `{{< relref >}}`
(or hand-written relative path) whose target page **exists** but contains none
of the subject the link text names.

This class is invisible to every check the repo currently runs:

- `hugo build` fails a `relref` only when the target does not resolve.
- `website/check_links.py` resolves hrefs and anchors; a link to a real page
  with a real (or absent) anchor passes regardless of what the page says.

So the defect is a *semantic* mismatch between link text and target content,
and it needs a different detector than the two above.

## Known instances (both already fixed by t1707)

- `website/content/docs/skills/aitask-trail.md:85` — `ait artifact` ->
  `/docs/commands/task-management` (that page documents only `ait create`,
  `ait ls`, `ait update`).
- `website/content/docs/development/task-format.md:98` — `ait artifact` ->
  `/docs/workflows/implementation-trails` (no `ait artifact` content).

Both were found by hand while chasing a single command name. Nothing
establishes that they are the only two.

## Suggested approach

1. Extract every internal link in `website/content/` as
   `(source_file, line, link_text, target_page[, anchor])`.
2. For each, apply a cheap relevance heuristic — e.g. does the target page (or
   the named anchor's section) contain the link text's distinctive token
   (`ait artifact`, `ait attach`, `By-Trail`, ...)? Backtick-quoted command
   names in link text are the highest-signal case and the cheapest to check.
3. Report misses for human triage rather than failing a build — the heuristic
   will have false positives (link text that is a page title, a prose
   paraphrase, etc.), so this is a report, not a gate, at least initially.
4. Decide only afterwards whether any part is precise enough to add to
   `check_links.py` as a non-blocking warning.

## Coordination

- Overlaps **t1687** (concepts docs gap sweep), which owns the decision on the
  missing `ait attach` / `ait artifact` command-reference pages and does its own
  bidirectional cross-linking. Check t1687's state before planning: if it has
  already created those pages and re-linked, the two known instances above are
  moot and this task is purely the generalized detector.
- t1707's plan (`aiplans/archived/p1707_*.md`) records the full analysis of why
  the existing checks cannot see this class.
