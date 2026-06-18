---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t1016_1]
issue_type: documentation
status: Implementing
labels: [child_tasks]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-17 13:35
updated_at: 2026-06-18 12:36
---

## Context

Documentation-consolidation child of t1016 (anchor task topic grouping). After
t1016_1 adds the `--anchor` / `--followup-of` flags and the `anchor` frontmatter
field, the new field + inheritance rule must be documented in EVERY surface that
enumerates the task schema, so agents/users don't drift. A blast-radius review
established the schema is documented in **6** surfaces (not 3), and that the
`aitasks_extension_points.md` new-field checklist is itself **incomplete**
(it omits `aitask_merge.py` and several doc surfaces) — this child fixes both.

Depends on t1016_1 (the flags must exist to document them accurately).

NOTE: the board "by-topic" VIEW doc (`website/.../tuis/board/reference.md` base-
view row) is intentionally NOT here — it ships with the board feature in t1016_4.
This child covers the FRONTMATTER-SCHEMA docs (the `anchor` field) + the
canonical creation contract + the extension-points checklist.

## Key Files to Modify

1. `.claude/skills/task-workflow/task-creation-batch.md` — canonical creation
   contract: document `--anchor` and `--followup-of` + the inheritance rule
   (child inherits parent's root; follow-up flattens to root; root has no anchor).
2. `.claude/skills/aitask-create/SKILL.md` (~L258-305 inline batch-flag list) —
   add both flags; point to the canonical contract (don't re-specify semantics —
   avoid drift).
3. `CLAUDE.md` "### Task File Format" (L57-73) — add `anchor: <task_id>` to the
   YAML block (hand-maintained file; edit directly).
4. `seed/aitasks_agent_instructions.seed.md` "## Task File Format" (L6-25) — add
   `anchor:` to the YAML block. This seed REGENERATES the mirrors `AGENTS.md`,
   `.codex/instructions.md`, `.opencode/instructions.md` via `aitask_setup.sh`
   (`assemble_aitasks_instructions`) — do NOT hand-edit those generated files.
5. `website/content/docs/development/task-format.md` (### Frontmatter Fields
   table, L30-59) — add an `anchor: <task_id>` row (authoritative reference).
6. `aidocs/framework/aitasks_extension_points.md` (new-field checklist, L8-25) —
   (a) record `anchor` against the checklist; (b) EXTEND the checklist to add the
   previously-missing layers: the `aitask_merge.py` scalar-merge rule and the full
   doc-surface set (seed → mirrors, CLAUDE.md, website task-format, board
   reference).

## Reference Files for Patterns

- Instruction-mirror regeneration: `aitask_setup.sh::assemble_aitasks_instructions`
  (~L1053-1090) + `insert_aitasks_instructions` (~L1093-1125); invoked by
  `update_agentsmd` (L1153), `setup_codex_cli` (L1939), `setup_opencode_cli`
  (L2090). Regenerate by re-running the relevant `ait setup` path; verified by
  `tests/test_agent_instructions.sh`.
- Skill goldens regeneration: `./.aitask-scripts/aitask_skill_rerender.sh` (auto-
  renders Codex/OpenCode skill variants from the Claude source — no separate port
  task); verified by `tests/test_skill_render_task_workflow.sh` and
  `./.aitask-scripts/aitask_skill_verify.sh`.
- The current field rows in `website/.../development/task-format.md` (e.g.
  `boardcol`, `folded_tasks`) show the table format to mirror.

## Implementation Plan

1. Edit the canonical `task-creation-batch.md` (add the Input-table rows +
   inheritance-rule prose). This is the single source of truth.
2. Edit `aitask-create/SKILL.md` inline list to add both flags, referencing the
   canonical contract.
3. Hand-edit `CLAUDE.md` Task File Format block.
4. Edit `seed/aitasks_agent_instructions.seed.md`; regenerate the 3 mirrors via
   the appropriate `ait setup` invocation; confirm markers preserved.
5. Add the `anchor` row to the website task-format table.
6. Update + extend `aitasks_extension_points.md` checklist.
7. Regenerate skill goldens (`aitask_skill_rerender.sh`).

## Verification Steps

- `bash tests/test_agent_instructions.sh` — generated mirrors match the seed.
- `bash tests/test_skill_render_task_workflow.sh` and
  `./.aitask-scripts/aitask_skill_verify.sh` — clean (skill goldens regenerated
  in the same commit).
- `grep -n anchor` the canonical contract and the inline ref → flag names agree;
  `grep -n anchor` AGENTS.md / .codex/instructions.md / .opencode/instructions.md
  → all present after regeneration.
- Website: `cd website && hugo build --gc --minify` (or the repo's lint) succeeds.

## Notes for sibling tasks

- Edit the SEED, never the generated instruction mirrors — `test_agent_instructions.sh`
  will fail if a mirror diverges from its seed.
- Keep semantics defined once (canonical `task-creation-batch.md`); other surfaces
  point to it rather than duplicating the inheritance rule.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-18T09:36:24Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-18T09:36:25Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-18T09:46:20Z status=pass attempt=1 type=human
