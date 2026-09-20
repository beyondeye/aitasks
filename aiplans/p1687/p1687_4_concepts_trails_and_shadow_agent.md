---
Task: t1687_4_concepts_trails_and_shadow_agent.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
---

# t1687_4 — Implementation trails and shadow agent

## Goal

- `concepts/implementation-trails.md` — weight **105**,
  *Lifecycle and infrastructure*
- `concepts/shadow-agent.md` — weight **125**, *Workflow primitives*

Both are advisory-by-construction primitives: one an advisory *artifact*, one an
advisory *agent*.

## Read this first — these are the two worst duplication risks in the sweep

`workflows/implementation-trails.md` and `workflows/shadow-agent.md` each
already contain a full conceptual treatment. The user was shown this at planning
and chose "write both, **strictly complementary**". That choice is binding:

| Already owns | Do not restate |
|---|---|
| `workflows/implementation-trails.md:9-47` | what a trail is; waves, classifications, observations, exclusions |
| `workflows/implementation-trails.md:90-104` | freshness and drift |
| `workflows/implementation-trails.md:125-134` | "advisory by construction" — fully covered there already |
| `workflows/shadow-agent.md:9-11` | what a shadow is |
| `workflows/shadow-agent.md:28-38` | what happens once it is running |
| `workflows/shadow-agent.md:186-188` | advisory-only |

If a paragraph you are about to write could be pasted into the workflow page
without looking out of place, it belongs there, not here.

## Implementation

### 1. `concepts/implementation-trails.md` (weight 105)

Angle: **why a sequencing recommendation is stored as a versioned artifact
rather than re-derived each time.**

Cover:

- the analysis is expensive and perishable; re-deriving it produces a *different*
  answer, so the durable thing must be the recommendation plus its evidence;
- versioning: a refresh produces a new version rather than overwriting, so an
  earlier recommendation stays retrievable and a drift check has something to
  compare against;
- ownership: a trail belongs to a task, and `scope.topics` lists members rather
  than their anchor roots;
- separation from topics: a task has exactly one topic but may appear in several
  trails, and a trail may span several topics — link
  `concepts/topic-anchoring.md` for the anchoring model.

**Hard limits:**

- The artifact substrate itself (`art:<id>` handles, manifests, immutable
  versions, backends) belongs to **t1231_3's `concepts/artifacts.md`**, which
  does not exist yet. Link
  `{{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments`
  for the frontmatter shape. **Do not describe the artifact store, and do not
  create or pre-link `concepts/artifacts.md`** — a relref to a non-existent page
  fails the build.
- **No merge line.** `merged_from` / merged trails have not shipped to the
  website and **t1647_6 owns them**. Write nothing about merging; t1647_6 adds
  it when its feature lands.

Source: `aidocs/implementation_trail_design.md`,
`aidocs/implementation_trail.schema.json`.

### 2. `concepts/shadow-agent.md` (weight 125)

Angle: **the advisory-only contract and the pane-binding identity.**

Cover:

- **the binding.** A shadow is bound to its followed agent by the tmux pane
  option `@aitask_shadow_target`. This has **zero** website presence today — it
  exists only in `CLAUDE.md:376` and in tests — so it is entirely new prose and
  the page's most valuable content. Pane options die with the pane, which is
  what stops a recycled pane id carrying a stale binding (the same mechanism
  `concepts/framework-session.md` describes for `@aitask_record` — link it);
- **the contract**: read-only, never types into the followed pane, never
  auto-launches a follow-up. The user stays the one who answers prompts and
  approves plans;
- **capture → context-fetch → skill**: the shadow reads a *capture* of the
  followed pane rather than sharing its session, which is why it can re-read on
  demand and why its view can lag.

Source: `aidocs/framework/shadow_agent.md`.

Note `weight: 125` sits outside the *Workflow primitives* band. That is
intentional and has precedent (agentcrews 75 is listed after agent-attribution
80; framework-session 95 after ide-model 120) — grouping in `_index.md` is
hand-ordered and independent of weight. Do not renumber existing pages.

### 3. Back-links

| File | Insertion point | Form (measured) |
|---|---|---|
| `workflows/implementation-trails.md` | `#what-a-trail-never-does` (line 125) | relref — its only cross-section link is a relref to `/docs/concepts/...` |
| `skills/aitask-trail.md` | `## Related` (line 89) | relref (6:1) |
| `tuis/board/reference.md` | `#by-trail` (line 249) | relref (12:1) |
| `concepts/topic-anchoring.md` | `## See also` (line 130) | relref (6:0) |
| `workflows/shadow-agent.md` | lead ¶, lines 9-11 | **relative** `(../../concepts/shadow-agent/)` (1:9) |
| `tuis/minimonitor/_index.md` | `#launching-a-shadow-agent` (line 77) | relref (9:2) |
| `tuis/minimonitor/how-to.md` | line 187, beside the existing workflow link | relref (23:0) |
| `tuis/monitor/how-to.md` | line 184, beside the existing workflow link | relref (15:1) |

`concepts/topic-anchoring.md` already links the trails *workflow* page at lines
21 and 136 — add the concept link beside it, do not silently replace it.

### 4. Do not link

- `tuis/monitor/reference.md` — shadow appears only as keybinding rows and
  SHADOW-*zone* mechanics; it explains the preview column, never the concept.
- `tuis/monitor/_index.md` — shadow named only as an excluded companion pane.
- There is **no** `skills/aitask-shadow.md`. Do not invent a link to it.
- `tuis/minimonitor/` has **no** `reference.md` — only `_index.md` and
  `how-to.md`. A relref to `/docs/tuis/minimonitor/reference` fails the build.

## Post-phase (risk mitigations)

### link_relevance_triage (shared with t1687_5)

Re-read both new pages against their workflow counterparts and delete anything
that merely repeats them. These two pages are where the duplicate-index failure
is most likely to appear.

## Constraints

- **Slug collision:** `/docs/concepts/implementation-trails` and
  `/docs/concepts/shadow-agent` both collide with same-named workflow pages.
  **Always write the full `/docs/...` path.** Run `hugo build` before
  committing — it is the check that catches an ambiguous relref.
- **No mermaid** on this site.
- Current-state-only prose.
- Do **not** touch `concepts/_index.md` — t1687_5 owns it.

## Verification

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
```

Check `${PIPESTATUS[0]}` or `set -o pipefail`. Confirm `#by-trail`,
`#what-a-trail-never-does` and `#launching-a-shadow-agent` still exist.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. The `risk_evaluated` gate is active and
must pass before archival.
