---
Task: t1016_2_anchor_doc_consolidation.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_1_*.md, aitasks/t1016/t1016_3_*.md, aitasks/t1016/t1016_4_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_2_anchor_doc_consolidation
Branch: aitask/t1016_2_anchor_doc_consolidation
Base branch: main
---

# Plan — t1016_2 Schema doc consolidation (anchor)

Document the `anchor` field + `--anchor`/`--followup-of` flags in every schema
surface, and fix the incomplete new-field checklist. Depends on t1016_1.
Excludes the board by-topic VIEW doc (that ships in t1016_4).

## Surfaces (6) + checklist

1. `.claude/skills/task-workflow/task-creation-batch.md` (canonical) — add Input-
   table rows for `--anchor` / `--followup-of` + inheritance-rule prose (child
   inherits root; follow-up flattens; root = no anchor). Single source of truth.
2. `.claude/skills/aitask-create/SKILL.md` (~L258-305) — add both flags to the
   inline list, pointing to the canonical contract (no semantics duplication).
3. `CLAUDE.md` "### Task File Format" (L57-73) — add `anchor: <task_id>`
   (hand-maintained; edit directly).
4. `seed/aitasks_agent_instructions.seed.md` "## Task File Format" (L6-25) — add
   `anchor:`. Then REGENERATE mirrors `AGENTS.md`, `.codex/instructions.md`,
   `.opencode/instructions.md` via the `ait setup` path
   (`aitask_setup.sh::assemble_aitasks_instructions` →
   `update_agentsmd`/`setup_codex_cli`/`setup_opencode_cli`). Do NOT hand-edit the
   generated mirrors.
5. `website/content/docs/development/task-format.md` (Frontmatter Fields table
   L30-59) — add an `anchor: <task_id>` row.
6. `aidocs/framework/aitasks_extension_points.md` (new-field checklist L8-25) —
   record `anchor`, AND extend the checklist to add the missing layers it omits
   today: the `aitask_merge.py` scalar-merge rule + the full doc-surface set
   (seed→mirrors, CLAUDE.md, website task-format, board reference).

Then regenerate skill goldens: `./.aitask-scripts/aitask_skill_rerender.sh`.

## Verification

- `bash tests/test_agent_instructions.sh` — mirrors match the seed.
- `bash tests/test_skill_render_task_workflow.sh` + `./.aitask-scripts/aitask_skill_verify.sh` — clean.
- `grep -n anchor` AGENTS.md .codex/instructions.md .opencode/instructions.md — present post-regen.
- `cd website && hugo build --gc --minify` — succeeds.
- Canonical contract vs inline ref agree on flag names.

## Post-Implementation
Step 9 applies on completion. In Final Implementation Notes, record the exact
`ait setup` invocation used to regenerate the mirrors (useful to siblings/future
field additions).
