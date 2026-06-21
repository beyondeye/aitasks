---
priority: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [aitask_board, child_tasks]
created_at: 2026-06-17 00:51
updated_at: 2026-06-21 10:03
completed_at: 2026-06-21 10:03
boardidx: 140
---

## Goal

Introduce an **anchor task** relationship so loosely-related and *future / follow-up* tasks can be organized around a subject **without forcing them into a rigid parent-child tree**, and surface that grouping on the board (where tasks are picked).

This complements parent-child + `depends` + `labels`; it does not replace them. Today there is **no** `epic`/`topic`/`group`/`anchor` concept — only directory-based parent-child (single parent, fixed at creation, sibling-serialized), `depends`, `folded_*`, and display-only `labels`.

## Confirmed design decisions (from brainstorm)

1. **Enforcement: BOTH.** The inheritance rule is enforced in `aitask_create.sh` (so it is structurally unbypassable by any caller — every creation skill and helper funnels through this one script) **and** documented in the canonical Batch Task Creation Procedure (`.claude/skills/task-workflow/task-creation-batch.md`).
2. **Children inherit anchor from parent.** A child auto-gets `anchor = parent.anchor-or-id`, so a board topic-group spans the whole parent-child subtree **plus** loose follow-ups as one cluster. (Anchor subsumes parent-child for grouping purposes.)
3. **Board: field + group-by-anchor view.** Ship the editable anchor field AND a new board "by-topic" view/swimlane that clusters tasks by anchor, modeled on the existing **inflight** alternate-layout precedent in `board/aitask_board.py`.

## Anchor semantics

- New frontmatter field: `anchor: <task_id>` (scalar). Empty/absent ⇒ the task is itself a topic root.
- **Group key = `anchor` if set, else own id.** Roots and their followups therefore share a key with **zero graph traversal** (simple equality — cheap on the board, no cycle risk).
- **Flattened inheritance ("inherit" rule):** spawning B from A sets `B.anchor = (A.anchor or A.id)`. Anchor **always points at the root**, never chains. Spawning a follow-up of a follow-up still resolves to the same root.

## Enforcement / plumbing (the "automatic" mechanism)

- Add to `aitask_create.sh`:
  - `--anchor <id>` — explicit low-level override (validate the id exists, like `--deps`).
  - `--followup-of <source_id>` — the high-level flag: the **script reads the source task's `anchor` and sets `anchor = source.anchor or source_id`**. This is where the inheritance rule lives.
  - Emit `anchor:` in `create_task_file()`, `create_child_task_file()` (child: resolve from `--parent`), and `create_draft_file()` (carry through `--finalize`).
- Child creation (`--parent`) auto-resolves `anchor = parent.anchor-or-id` per decision #2.
- Add editable `anchor` to `aitask_update.sh` (same read-modify-write scalar pattern as `assigned_to`/`boardcol`) so the board can edit it.
- **Spawn-site wiring (the blast radius of "automatic"):** thread `--followup-of <source_id>` into each site that currently spawns a follow-up but records no provenance:
  - `aitask-qa` follow-up test tasks (knows its target task).
  - risk-mitigation tasks (`task-workflow/risk-mitigation-followup.md`).
  - archive deferred-carryover (`aitask_archive.sh`).
  - verification follow-up (`aitask_verification_followup.sh`).
  - **Caveat — `aitask-review`:** review usually has no single source task (it reviews a diff/area), so by default it creates a *root*, not a follow-up. Do NOT force an anchor there; only pass `--followup-of` when a specific reviewed task is the clear source.

## Board (group-by-anchor view + edit)

- Editable anchor field in the task detail/edit screen → persists via `aitask_update.sh --anchor`.
- New "by-topic" base view (sibling of all/locked/free/**inflight**) that re-buckets tasks into per-anchor swimlanes. Group label = root task's title; tasks without an anchor and with no followups appear ungrouped.
- Consider topic-colored card borders (reuse the existing priority-border infra as the pattern).

## Single-source-of-truth consolidation

`.claude/skills/task-workflow/task-creation-batch.md` is **already** the one canonical creation contract; all skills delegate to it (explore, qa, review, pr-import, wrap, planning child-creation, contribution-review). To finish the "one place" goal:
- Document the `--anchor` / `--followup-of` flags + the inheritance rule in that procedure.
- Audit the inline batch-flag reference in `aitask-create/SKILL.md` (lines ~258-305) and CLAUDE.md "Task File Format" so they point to / agree with the canonical contract rather than drifting.

## Blast radius / files

- `.aitask-scripts/aitask_create.sh` (flags, resolution logic, frontmatter emit ×3 paths, help, validation).
- `.aitask-scripts/aitask_update.sh` (editable `--anchor`, parse + write).
- `.aitask-scripts/board/task_yaml.py` (normalize `anchor` task-id like `depends`).
- `.aitask-scripts/board/aitask_board.py` (Task model field, by-topic view, editable field, card display).
- `.claude/skills/task-workflow/task-creation-batch.md` (+ rendered profile/agent variants — regenerate goldens).
- Spawn-site skills/helpers: aitask-qa, risk-mitigation-followup, `aitask_archive.sh`, `aitask_verification_followup.sh`.
- CLAUDE.md "Task File Format" + `aidocs/framework/aitasks_extension_points.md` (new-field checklist).
- `seed/` templates if frontmatter schema is seeded.
- Tests for each of the above (testability-first).

## Suggested decomposition (testability-first — to be set during planning)

1. **Schema + script enforcement:** `aitask_create.sh` `--anchor`/`--followup-of` + resolution + `aitask_update.sh --anchor`; child auto-inherit. Owns: unit tests for inheritance (root, follow-up, follow-up-of-follow-up flattening, child-from-parent).
2. **Procedure/doc consolidation:** Batch Task Creation Procedure + CLAUDE.md + extension-points; regenerate goldens.
3. **Spawn-site wiring:** qa / risk-mitigation / carryover / verification-followup pass `--followup-of`; review caveat honored. Each with a test.
4. **Board:** Task model field, editable anchor in detail screen, group-by-anchor view/swimlane, card display.

## Acceptance criteria

- Creating a follow-up via `--followup-of <src>` sets `anchor` to `src.anchor` when present, else `src` (flattened to root; never chains).
- A child auto-inherits `anchor = parent.anchor-or-id`.
- `anchor` is editable from the board and persists via `aitask_update.sh`.
- The board offers a by-anchor grouping view that clusters root + subtree + loose follow-ups under one topic.
- The inheritance rule is enforced in `aitask_create.sh` (verified by test) AND documented in the single canonical Batch Task Creation Procedure; no competing creation-procedure doc reachable from CLAUDE.md contradicts it.

## Open considerations (resolve in planning)

- **Re-anchoring semantics:** with the flattened model, a task's followups point at the root, not at it — so editing one task's anchor moves only that task. Moving/merging a whole topic means re-pointing all tasks sharing the root id; consider a board "re-anchor group" action vs. single-task edit.
- **Archived anchor root:** when the root completes/archives, the anchor id remains a stable group key — confirm the board still renders the topic (group by id, don't require the root file to be active).
- **Validation:** `--anchor`/`--followup-of` should reject non-existent ids (mirror `validate_deps`); local-only for v1 (no cross-repo anchors).
