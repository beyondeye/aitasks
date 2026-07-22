---
Task: t1162_5_work_report_documentation.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_1_work_report_gatherer_helper.md, aitasks/t1162/t1162_2_work_report_codeagent_operation.md, aitasks/t1162/t1162_3_work_report_skill_and_wrappers.md, aitasks/t1162/t1162_4_board_w_work_report_flow.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_*_*.md
Worktree: aiwork/t1162_5_work_report_documentation
Branch: aitask/t1162_5_work_report_documentation
Base branch: main
---

# Plan: t1162_5 — Work-report documentation

## Context

Documents the complete work-report feature (skill, workflow, board shortcut,
operation). Runs LAST — before writing, read the ARCHIVED sibling plans
(`aiplans/archived/p1162/p1162_1..4_*.md`) and the LANDED sources (SKILL.md,
board code, `aitask_codeagent.sh`) — document current source, not this plan's
expectations (they may have drifted; the live source is the truth). Follow
`aidocs/framework/documentation_conventions.md`: current-state-only, no
version history, genericize supported-agent references ("your coding agent",
not a hardcoded agent list), and use generic invented example project/task
names in samples.

## Files

1. **`website/content/docs/skills/aitask-work-report.md`** (new) — skill
   reference: invocation (`/aitask-work-report [--columns <csv> [--tasks
   <csv>]]`), interactive vs board-launched paths, horizon labeling,
   fail-closed stale-selection behavior, report structure, the completion
   projection (data-derived from 7/30-day completion throughput; projection
   not commitment; insufficient-history fallback), and that no report file is
   written. Model an existing page: `skills/aitask-changelog.md`.
2. **`website/content/docs/skills/_index.md`** — add a row in the appropriate
   categorized table (Task Management group, alongside changelog/stats).
3. **`website/content/docs/workflows/work-report.md`** (new) — end-to-end
   workflow: board `w` flow (column multi-select → task multi-select → agent
   dialog), direct skill invocation, review/editing loop, projection reading
   guidance for managers. Model: `workflows/explain.md`.
4. **`website/content/docs/workflows/_index.md`** — add a bullet in the
   matching group (hand-curated manual list — REQUIRED for the page to be
   discoverable; see project memory).
5. **`website/content/docs/tuis/board/reference.md`** — Keyboard Shortcuts
   table row: `w` | Work Report | persistent kanban views, focused column.
6. **`website/content/docs/tuis/board/how-to.md`** — short narrative section:
   focus a column, press `w`, adjust selections, launch.
7. **`website/content/docs/commands/codeagent.md`** — add `work-report` to
   the supported-operations list (read-only analysis operation, lightweight
   default model).

Do NOT mention `diffviewer`; keep documented-TUIs list unchanged (board,
monitor, minimonitor, codebrowser, settings, brainstorm).

## Verification

- `cd website && hugo build --gc --minify` succeeds (requires Hugo extended
  ≥0.155.3, Go ≥1.23, Dart Sass, Node 18+ — `npm install` first if needed).
- New pages render; internal links/relrefs resolve during build.
- Grep the built output (or run the dev server) for the new pages' titles.
- Cross-check every documented flag/behavior against the landed SKILL.md and
  board code (no drifted claims).

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9. This
is the last planned child — archiving it archives the parent when
`children_to_implement` empties (the aggregate manual-verification sibling,
if created, will be the actual final child).
