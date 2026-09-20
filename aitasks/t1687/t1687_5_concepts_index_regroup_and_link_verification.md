---
priority: high
effort: medium
depends: [t1687_4]
issue_type: documentation
status: Ready
labels: [documentation, website, concepts]
gates: [risk_evaluated]
anchor: 1687
created_at: 2026-09-20 12:02
updated_at: 2026-09-20 12:02
---

## Context

Final child of t1687 (Concepts docs gap sweep). Siblings t1687_1..t1687_4 each
write their concept pages **and their own back-links**, but none of them touches
`website/content/docs/concepts/_index.md`. This task reconciles that index,
repairs the reading chain, and runs the whole verification block.

It runs last by sibling auto-dependency, which is deliberate:
`concepts/_index.md` is **contended** — t1231_3 and t635_18 both plan to edit it
(t1705_10's edit already landed). Landing one consolidated regroup spares both a
rebase, and editing it once rather than five times avoids self-conflict.

## Key files to modify

- `website/content/docs/concepts/_index.md` — the only file this task owns
  outright.
- Whichever sibling pages need a `**Next:**` footer adjustment (see below).

## Six new pages to index

| Page | Weight | Group |
|---|---|---|
| `concepts/task-notes.md` | 45 | Data model |
| `concepts/attachments.md` | 55 | Data model |
| `concepts/gates.md` | 85 | Workflow primitives |
| `concepts/implementation-trails.md` | 105 | Lifecycle and infrastructure |
| `concepts/cross-repo-references.md` | 115 | Lifecycle and infrastructure |
| `concepts/shadow-agent.md` | 125 | Workflow primitives |

All six sit on free `+5`-grid slots; **no existing page is renumbered** (that
was a deliberate choice to keep the rebase surface small for t1231_3/t635_18).

`shadow-agent` (125) is the one page whose weight falls outside its group's
band. This is fine and has precedent: `_index.md` grouping is hand-ordered and
already independent of weight — agentcrews (75) is listed after agent-attribution
(80), and framework-session (95) after The IDE model (120). Note it rather than
"fixing" it by renumbering.

## Bullet shape (copy exactly)

```
- **[Tasks]({{< relref "/docs/concepts/tasks" >}})** — Markdown files with YAML frontmatter, one per unit of work.
```

Link text = the page's `linkTitle`. Blurb = a lightly reworded `description`,
capitalized, ending in a period. Em dash with spaces. No `.md`, no trailing
slash, always the full `/docs/...` path.

## The `**Next:**` reading chain

14 of the 17 existing pages form a linear chain via a `**Next:**` footer;
`topic-anchoring.md`, `agentcrews.md` and `framework-session.md` sit outside it.
Adding six more orphans would leave 9 of 23 pages off the chain and make it
actively misleading.

- Splice the six new pages into the chain in weight order.
- Close the two pre-existing skips: `parent-child.md` currently points past
  `topic-anchoring.md`, and `ide-model.md` past `framework-session.md`.

**This item is the one piece beyond a literal reading of t1687's scope.** It was
approved at planning as serving "the section still reads in a sensible
progression", and it is easy to drop: if it looks like scope creep when you get
here, skip it and note the decision — the rest of this task stands alone.

## Orphan check — both directions

- Every `.md` in `website/content/docs/concepts/` (except `_index.md`) appears
  exactly once in `_index.md`.
- Every bullet in `_index.md` resolves to a file that exists.

Both directions were clean before this sweep (17 files ↔ 17 bullets); they must
be clean after (23 ↔ 23).

## Verification (the full block for the whole t1687 sweep)

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
cd website && python3 check_link_relevance.py
```

- `hugo build` fails a dead **or ambiguous** relref. Ambiguity matters here:
  three new slugs (`task-notes`, `implementation-trails`, `shadow-agent`)
  collide with same-named workflow pages, so any bare relref must be caught.
- `check_links.py` catches dead `#fragment` targets and hand-written relative
  paths that the build lets through.
- `check_link_relevance.py` is a **report, not a gate** — reported links never
  change its exit status, and false positives are expected (t1759's first sweep
  reported 4, all four triaged as false positives). Only a failed self-control
  makes it exit non-zero.

**Piping discards the exit status** — use `set -o pipefail` or check
`${PIPESTATUS[0]}`.

Also confirm:
- `website/content/docs/concepts/` still contains **zero** hand-written relative
  links (it had none before this sweep);
- every anchor named in t1687's reciprocal link map still exists;
- no mermaid fence was introduced anywhere (the site has no mermaid support, so
  one would build green and render as a plain code block).

## Post-phase risk mitigation — link_relevance_triage

Run `check_link_relevance.py` and walk **every link added by t1687_1..t1687_5**,
not just the reported ones. The failure class it targets — a link resolving to a
real page that never discusses the subject — passes both `hugo build` and
`check_links.py`, and is exactly the defect t1707 found by hand in two
`ait artifact` links. Record the triage outcome.
