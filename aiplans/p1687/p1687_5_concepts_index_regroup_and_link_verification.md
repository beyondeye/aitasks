---
Task: t1687_5_concepts_index_regroup_and_link_verification.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
---

# t1687_5 — Concepts index, reading chain, and verification

## Goal

Reconcile `website/content/docs/concepts/_index.md` with the six pages the
siblings added, repair the `**Next:**` reading chain, and run the verification
block for the whole t1687 sweep.

This is the last child by sibling auto-dependency, which is deliberate:
`concepts/_index.md` is contended (t1231_3 and t635_18 both plan to edit it;
t1705_10's edit already landed). One consolidated regroup spares them a rebase
and avoids five siblings conflicting on one file.

## Pre-flight

Confirm all six sibling pages exist before editing the index — a bullet pointing
at a missing page fails the build:

```bash
ls website/content/docs/concepts/{task-notes,attachments,gates,implementation-trails,cross-repo-references,shadow-agent}.md
```

If any is missing, the owning sibling has not landed; stop and report rather
than writing a bullet for it.

## Implementation

### 1. Add six bullets to `_index.md`

The file has three `##` groupings, each a short lead-in then a bullet list.
Bullet shape, copied exactly from line 14:

```
- **[Tasks]({{< relref "/docs/concepts/tasks" >}})** — Markdown files with YAML frontmatter, one per unit of work.
```

Link text = the page's `linkTitle`; blurb = a lightly reworded `description`,
capitalized, ending in a period; em dash with spaces; no `.md`, no trailing
slash, always the full `/docs/...` path.

| Page | Weight | Group |
|---|---|---|
| `task-notes` | 45 | **Data model** |
| `attachments` | 55 | **Data model** |
| `gates` | 85 | **Workflow primitives** |
| `implementation-trails` | 105 | **Lifecycle and infrastructure** |
| `cross-repo-references` | 115 | **Lifecycle and infrastructure** |
| `shadow-agent` | 125 | **Workflow primitives** |

Place each bullet in weight order **within its group**, which is how the file
mostly reads today.

### 2. Do not renumber, and do not "fix" the one mismatch

All six weights sit on free `+5`-grid slots and no existing page's frontmatter
is touched. This was chosen to keep the rebase surface small for t1231_3 and
t635_18, which both edit this file.

`shadow-agent` (125) falls outside the *Workflow primitives* band. Leave it:
grouping here is hand-ordered and already independent of weight — agentcrews
(75) is listed after agent-attribution (80), and framework session (95) after
The IDE model (120). Renumbering to "tidy" this would maximise exactly the
conflict this ordering was designed to avoid.

### 3. Re-check the progression

With three groups now holding 8 / 8 / 7 bullets, confirm each group still reads
as a progression and its lead-in sentence still describes its members. A fourth
grouping is **not** warranted at this size — it becomes worth revisiting only if
the deferred procedure-shaped candidates (risk evaluation, manual verification,
chat intake, backlog roadmap) are later added.

### 4. The `**Next:**` reading chain

14 of the 17 pre-existing pages form a linear chain via a `**Next:**` footer.
`topic-anchoring.md`, `agentcrews.md` and `framework-session.md` sit outside it.
Adding six more orphans would leave 9 of 23 pages off the chain.

- Splice the six new pages into the chain in weight order.
- Close the two pre-existing skips: `parent-child.md` currently points past
  `topic-anchoring.md`, and `ide-model.md` past `framework-session.md`.

**This is the one item beyond a literal reading of t1687's scope.** It was
approved at planning as serving "the section still reads in a sensible
progression". It is also the easiest thing here to drop: if on arrival it looks
like scope creep, skip it, note the decision in the task, and the rest of this
task stands unaffected.

### 5. Orphan check, both directions

```bash
cd website/content/docs/concepts
ls *.md | grep -v '^_index.md$' | sed 's/\.md$//' | sort > /tmp/pages.txt
grep -o 'relref "/docs/concepts/[a-z-]*"' _index.md \
  | sed 's|.*/||; s|"||' | sort > /tmp/bullets.txt
diff /tmp/pages.txt /tmp/bullets.txt && echo "no orphans either direction"
```

Both directions were clean before the sweep (17 ↔ 17); they must be clean after
(23 ↔ 23).

## Post-phase (risk mitigations)

### link_relevance_triage

Run the report and walk **every link added by t1687_1..t1687_5**, not only the
rows it reports:

```bash
cd website && python3 check_link_relevance.py
```

It is a **report, not a gate** — reported links never change its exit status and
false positives are expected (t1759's first sweep reported 4, all four triaged
as false positives). Only a failed self-control makes it exit non-zero.

It targets the one failure class no gate catches: a link that resolves to a real
page which never discusses the subject. That is exactly the defect t1707 found
by hand in two `ait artifact` links. Record the triage outcome in the task.

Also re-confirm the two protected literals are still unlinked (t1231_3's
decision, not ours):

```bash
grep -n 'ait artifact' website/content/docs/development/task-format.md \
                        website/content/docs/skills/aitask-trail.md
```

## Verification (the full block for the whole sweep)

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
cd website && python3 check_link_relevance.py
```

- `hugo build` fails a dead **or ambiguous** relref. Ambiguity matters: three
  new slugs (`task-notes`, `implementation-trails`, `shadow-agent`) collide with
  same-named workflow pages.
- `check_links.py` catches dead `#fragment` targets and hand-written relative
  paths the build lets through.

**Piping discards the exit status** — use `set -o pipefail` or check
`${PIPESTATUS[0]}`. The verdict banner goes to stderr, so it survives
`2>&1 | tail` even when the status does not.

Also confirm:

```bash
# concepts/ must still contain zero hand-written relative links
grep -rn '](\.\./' website/content/docs/concepts/ | wc -l    # expect 0
# the site must still contain no mermaid fence
grep -rn '```mermaid' website/content/ | wc -l               # expect 0
```

And confirm every anchor named in t1687's reciprocal link map still exists.

## Follow-ups to spawn (recorded by the parent; do not silently drop)

- **`ait trails` has zero site coverage** — no `commands/` page, no `tuis/`
  page, no mention anywhere on the site. A real gap, but a TUI/command gap
  rather than a concept one.
- **`ait brainstorm` and `ait chatlink` have no `commands/` page.**
- The procedure-shaped candidates deliberately excluded from this sweep (risk
  evaluation, manual verification, chat intake, backlog roadmap) and the
  too-thin ones (follow-up provenance, board columns/groups, sync deferral).

Note `ait diffviewer`'s absence from the site is **deliberate** per `CLAUDE.md`
— do not file it as a gap.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. The `risk_evaluated` gate is active and
must pass before archival. This being the last child, verify the parent t1687's
plan is complete before the parent is archived.
