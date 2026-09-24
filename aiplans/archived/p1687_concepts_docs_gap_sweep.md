---
Task: t1687_concepts_docs_gap_sweep.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1687 — Concepts docs gap sweep

## Context

`website/content/docs/concepts/` is the site's conceptual entry point — "what
each building block of the framework *is* and *why* it exists". It gained no new
entry between topic-anchoring (2026-06-29) and framework-session (2026-09-20),
while everything shipped across v0.25–v0.34 landed in Workflows / Commands /
TUIs / Skills instead. A reader who starts in Concepts gets an incomplete model.

The task body forbids planning against its 2026-09-02 gap table. A
re-verification sweep ran at pick time and the table moved materially.

### What re-verification changed

| Finding | Effect |
|---|---|
| Task notes gained `workflows/task-notes.md`, `commands/note.md`, `skills/aitask-note.md` (t1657_6) | No longer "the biggest hole"; only a concept page remains |
| `concepts/framework-session.md` shipped **2026-09-20** (t1705_10) | Dropped from the gap list; dir is 17 pages, not 16 |
| `premise_baseline` has zero hits in `.aitask-scripts/` / `.claude/skills/` | Not shipped; excluded by the task's own criterion. t1663_5 owns it as a *Workflows* page |
| t635_18 owns a Gates concept page (blocked on t635_37) | **User decision: t1687 writes it**; t635_18 later extends |
| t1231_3 owns `concepts/artifacts.md` + `commands/artifact.md` (blocked on unshipped `gitbranch`) | **User decision: leave both to t1231_3** |
| `ait attach` has no owner anywhere and no `commands/` page | In scope here |
| Note 3's "`sweep_dead_end_relrefs` does not exist" | **Stale** — it is t1759, Done, archived into a bundle |
| `ait trails` has zero site coverage | Real gap, but a TUI/command gap — deferred |
| `ait diffviewer` has zero coverage | **Deliberate** per CLAUDE.md. Not a gap |
| No mermaid support site-wide | Diagrams use box-drawing ASCII in a ```` ```text ```` fence |

### Scope decisions (user-confirmed)

**Include:** gates, attachments (+ `commands/attach.md`), task notes,
cross-repo references, implementation trails, shadow agent.
**Exclude as procedure-shaped:** risk evaluation, manual verification, chat
intake, backlog roadmap. **Too thin for a page:** follow-up provenance, board
columns/groups, sync deferral. **Owned elsewhere:** artifacts, premise
staleness. **Contended prose:** worktrees & admission, parked agents.

## Two constraints that govern every edit

### 1. Name-collision — always use the full `/docs/...` path

Three new pages share a slug with an existing workflow page:
`/docs/concepts/task-notes` vs `/docs/workflows/task-notes`, and likewise
`implementation-trails` and `shadow-agent`. A bare
`{{< relref "shadow-agent" >}}` is **ambiguous and fails the build**. Every
relref in this task is written full-path.

### 2. Link form is per-file, not per-directory

The conventions doc prefers relref, but four target files are dominated by
hand-written relative links and an edit must match its surroundings. Measured:

| File | relref : relative | Form to use |
|---|---|---|
| `workflows/risk-evaluation.md` | 0 : 13 | **relative** |
| `workflows/shadow-agent.md` | 1 : 9 | **relative** |
| `workflows/crash-recovery.md` | 1 : 8 | **relative** |
| `commands/_index.md` tables | 2 : 33 | **relative** |
| all other targets below | relref dominant or exclusive | **relref** |

## Page inventory and weights

All six land on free `+5`-grid slots; **no existing page's frontmatter is
renumbered**, which also keeps the rebase surface minimal for t1231_3 and
t635_18. Free slots on the grid are exactly 45, 55, 85, 105, 115, 125 — six
slots for six pages.

| New page | Weight | `_index.md` group |
|---|---|---|
| `concepts/task-notes.md` | 45 | Data model |
| `concepts/attachments.md` | 55 | Data model |
| `concepts/gates.md` | 85 | Workflow primitives |
| `concepts/implementation-trails.md` | 105 | Lifecycle and infrastructure |
| `concepts/cross-repo-references.md` | 115 | Lifecycle and infrastructure |
| `concepts/shadow-agent.md` | 125 | Workflow primitives |
| `commands/attach.md` | 34 | (Commands, Tools table) |

`shadow-agent` is the one page whose weight sits outside its group's band.
`_index.md` grouping is hand-ordered and already independent of weight — the
existing precedents are agentcrews (75, listed after agent-attribution 80) and
framework-session (95, listed after ide-model 120).

Page shape copies `concepts/framework-session.md`: frontmatter keys in the fixed
order `title`, `linkTitle`, `weight`, `description`, `depth`; then
`## What it is` → optional `###` depth → `## Why it exists` → `## How to use` →
`## See also` → `---` → `**Next:**`.

## Complementary-angle discipline (non-negotiable)

Every one of the six concepts is **already explained inline somewhere**, several
extensively. Without a cap, this task produces the duplicate index the task body
warns against. Each page states only the *model* the existing pages assume, and
carries an explicit no-restate list.

| Page | Its angle | Must NOT restate |
|---|---|---|
| gates | Declared intent vs the framework-derived enforced set, and why enforcement is a claim-time snapshot | `commands/gates.md:9-16` lead definition; `tuis/board/reference.md:462-545` phases/progress (~80 lines, the most detailed declared-vs-enforced prose in the docs) |
| attachments | Content-addressing as the identity model; why a blob is never named by path | — (almost entirely new prose; only two rows exist today) |
| task notes | Why cross-task context is **untrusted by construction**, and what provenance can and cannot prove | `workflows/task-notes.md:9,38-81`; `commands/note.md:129-151` `### Provenance` — the only full `from`/`from_verified`/`base`/`dirty` definition |
| cross-repo refs | Why a logical name resolved at call time is the identity, not a path | `workflows/multi_project.md:11-13,34-51,145-158` |
| implementation trails | Why a sequencing *recommendation* is stored as a versioned artifact rather than re-derived | `workflows/implementation-trails.md:9-47,90-104,125-134`. The artifact substrate itself belongs to t1231_3's `concepts/artifacts.md` — link, do not describe |
| shadow agent | The advisory-only contract and the pane-binding identity (`@aitask_shadow_target`, which has **zero** website presence today — new prose) | `workflows/shadow-agent.md:9-11,28-38,186-188` |

## Reciprocal link map

Back-links are added **only where a page currently explains the concept inline**
— the task's own conditional. Pages that merely use or mention the term, and
pure key/command reference, are excluded. Each child adds its own pages' links
so a page and its links land together.

### → `/docs/concepts/gates`

| File | Insertion point | Form |
|---|---|---|
| `commands/gates.md` | lead ¶ lines 9–16 (no heading); trim the definition to a pointer | relref |
| `development/task-format.md` | gate rows 71–76 under `#frontmatter-fields` | relref |
| `tuis/board/reference.md` | `#gate-progress` (line 493) | relref |
| `workflows/crash-recovery.md` | `## See also` (line 182), beside the existing `concepts/locks` row | **relative** — `[Gates](../../concepts/gates/)` |
| `workflows/risk-evaluation.md` | `## See Also` (line 92), beside the existing `commands/gates` row | **relative** — `[Gates](../../concepts/gates/)` |

Also fix `commands/gates.md:13`, a hand-written
`[task file format](../../development/task-format/)` sitting in the lead being
edited, in a file that is otherwise relref-dominant.

Not qualifying: `skills/aitask-run-gates.md`, `skills/aitask-resume.md`,
`commands/_index.md` Gates table. Author's call:
`skills/aitask-gate-docs-updated.md#why-it-runs-where-it-runs` — link only if
the page covers the machine/human/procedure-backed taxonomy.

### → `/docs/concepts/attachments`

| File | Insertion point | Form |
|---|---|---|
| `development/task-format.md` | `attachments` row (line 60) and `#nested-fields-artifacts-and-attachments` (line 78) | relref |
| `commands/attach.md` (new) | its own lead, `crew.md` pattern | relref |
| `commands/_index.md` | **new row** in the Tools table + a `## Usage Examples` line | **relative** |

Link the bare `ait attach` literal at `task-format.md:98-99` to the new command
page. **Leave the adjacent `ait artifact` literal unlinked** — t1231_3's call.

### → `/docs/concepts/task-notes`

| File | Insertion point | Form |
|---|---|---|
| `workflows/task-notes.md` | `## See also` (line 89) | relref |
| `commands/note.md` | `#provenance` (line 129) | relref |
| `skills/aitask-note.md` | `## Related` (line 58) | relref |

Not qualifying: `concepts/locks.md` (single mention). Never link the board's
"Unsorted / **Inbox**" column — an unrelated homonym.

### → `/docs/concepts/cross-repo-references`

| File | Insertion point | Form |
|---|---|---|
| `workflows/multi_project.md` | `#why-logical-project-names` (line 11) | relref |
| `workflows/cross_project_dependencies.md` | `## See also` (line 122) | relref |
| `development/task-format.md` | `xdeprepo` row (line 39), beside the existing relref | relref |

### → `/docs/concepts/implementation-trails`

| File | Insertion point | Form |
|---|---|---|
| `workflows/implementation-trails.md` | `#what-a-trail-never-does` (line 125) | relref |
| `skills/aitask-trail.md` | `## Related` (line 89) | relref |
| `tuis/board/reference.md` | `#by-trail` (line 249) | relref |
| `concepts/topic-anchoring.md` | `## See also` (line 130) — concept-to-concept | relref |

### → `/docs/concepts/shadow-agent`

| File | Insertion point | Form |
|---|---|---|
| `workflows/shadow-agent.md` | lead ¶ lines 9–11 | **relative** — `(../../concepts/shadow-agent/)` |
| `tuis/minimonitor/_index.md` | `#launching-a-shadow-agent` (line 77) | relref |
| `tuis/minimonitor/how-to.md` | line 187, beside the existing workflow link | relref |
| `tuis/monitor/how-to.md` | line 184, beside the existing workflow link | relref |

Not qualifying: `tuis/monitor/reference.md` (keys and SHADOW-zone mechanics
only), `tuis/monitor/_index.md`. There is **no** `skills/aitask-shadow.md`.
`tuis/minimonitor/` has only `_index.md` and `how-to.md` — no `reference.md`.

## Children

Children auto-depend on siblings, so the contended `_index.md` is never edited
concurrently.

- **t1687_1 — Gates.** `concepts/gates.md` (85) + its five back-links + the
  `commands/gates.md:13` relative-link fix. Sources: `aidocs/gates/*.md`,
  `.aitask-scripts/aitask_gate.sh`.
- **t1687_2 — Attachments.** `concepts/attachments.md` (55),
  `commands/attach.md` (new, shaped on `commands/lock.md`), the
  `commands/_index.md` row and usage line. Sources:
  `aidocs/task_attachments_design.md`, `aidocs/attachment_metadata_bucketing.md`.
- **t1687_3 — Task notes + cross-repo.** `concepts/task-notes.md` (45),
  `concepts/cross-repo-references.md` (115) + their back-links. Sources:
  `aidocs/framework/task_note_mailbox.md`,
  `aidocs/framework/cross_repo_references.md`.
- **t1687_4 — Trails + shadow.** `concepts/implementation-trails.md` (105),
  `concepts/shadow-agent.md` (125) + their back-links. Writes **no** merge line
  (`merged_from` is unshipped; t1647_6 owns it). Sources:
  `aidocs/implementation_trail_design.md`, `aidocs/framework/shadow_agent.md`.
- **t1687_5 — Index, chain, verification.** `_index.md` bullets in the
  established `- **[Link]({{< relref … >}})** — Sentence.` shape; re-check the
  progression; orphan check both directions; run the whole verification block
  and the link-relevance triage over the map above.

  **Next-chain.** 14 of 17 pages form a reading chain; topic-anchoring,
  agentcrews and framework-session sit outside it. Splice the six new pages in
  by weight and close the two pre-existing skips. *This is the one item beyond a
  literal reading of the task's scope — included because six more chain-orphans
  would make the chain misleading, and easy to drop if unwanted.*

## Deferred (spawn follow-ups; do not silently drop)

- **`ait trails` has zero site coverage** — no `commands/` page, no `tuis/`
  page, no mention anywhere.
- **`ait brainstorm` and `ait chatlink` have no `commands/` page.**
- The procedure-shaped and too-thin candidates listed under Scope decisions.

## Risk

### Code-health risk: low
- Documentation-only: new markdown plus `_index.md` and back-link edits; no executable code and no framework behaviour touched · severity: low · → mitigation: none needed
- `concepts/_index.md` is contended by t1231_3 and t635_18; `concepts/locks.md` by t1592/t1593 (this task does not restructure it) · severity: low · → mitigation: inline pre-phase record_page_ownership_notes

### Goal-achievement risk: medium
- Six concepts already explained inline elsewhere, several extensively; without the complementary-angle cap the section becomes the duplicate index the task warns against · severity: medium · → mitigation: inline post-phase link_relevance_triage
- `concepts/gates.md` describes a large, subtle subsystem (declared vs active tuple, digest fallback, retry budgets) and can misdescribe shipped behaviour · severity: medium · → mitigation: inline post-phase gates_page_accuracy_review
- Three new slugs collide with existing workflow pages; a bare relref is ambiguous and a full-path one can still resolve to a real-but-off-topic page · severity: medium · → mitigation: inline post-phase link_relevance_triage
- t635_18 or t1231_3 could still write a page this task writes · severity: medium · → mitigation: inline pre-phase record_page_ownership_notes

### Planned mitigations
- timing: pre-phase | name: record_page_ownership_notes | type: documentation | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: contention on the gates/artifacts pages and _index.md | desc: Before writing any page, note t635_18 and t1231_3 with the ownership decision made here.
- timing: post-phase | name: link_relevance_triage | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: resolve-but-off-topic links and duplicated prose | desc: Run website/check_link_relevance.py and verify every row of the reciprocal link map resolves and is on-topic.
- timing: post-phase | name: gates_page_accuracy_review | type: documentation | priority: high | effort: low | inline_risk: low | added_complexity: medium | addresses: gates concept page accuracy | desc: Re-verify concepts/gates.md against aidocs/gates/*.md and real materialize-active behaviour before commit.

## Verification

From `website/`:

```bash
hugo build --gc --minify          # fails a dead or ambiguous relref
python3 check_links.py --build    # fails dead #fragments and relative paths
python3 check_link_relevance.py   # advisory report; triage the map's rows
```

Hugo 0.166.0 extended is installed locally, so all three run.

Then confirm for the Concepts section:
- every page in the directory is listed in `_index.md`, and every `_index.md`
  bullet points at an existing page (no orphans either way);
- the directory still contains **zero** hand-written relative links
  (it has none today);
- every anchor named in the reciprocal link map still exists;
- no mermaid fence was introduced anywhere.

`check_links.py` exits non-zero on failure but a pipe discards that — use
`set -o pipefail` or check `${PIPESTATUS[0]}`.

## Step 9 (Post-Implementation)

Standard Step 9 cleanup, archival and merge. The `risk_evaluated` gate is active
on this task and must pass before archival.
