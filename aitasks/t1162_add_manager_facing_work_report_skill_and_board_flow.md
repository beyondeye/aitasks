---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [skills, ui, reporting, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1162_5, t1162_6]
created_at: 2026-07-19 12:22
updated_at: 2026-07-24 10:29
boardidx: 140
---

## Context

`aitask-changelog` summarizes work that landed since the previous release. A complementary forward-looking workflow is needed for reporting what will be worked on today or this week to managers. Task membership must come from selected `ait board` columns, and each column's top-to-bottom `boardidx` order represents priority.

## Goal

Add a manager-facing `/aitask-work-report` skill and a contextual `w` action in the board TUI. The workflow must let users choose columns and include or exclude individual tasks before launching an agent, then produce an editable Markdown draft without writing a report file.

## Requirements

### Deterministic report input

- Add an internal gatherer that reads board configuration and active parent tasks, validates requested columns and task IDs, and returns structured data grouped in left-to-right board-column order.
- Preserve ascending `boardidx` order within every column. Include the dynamic Unsorted column when it exists.
- Support `/aitask-work-report --columns <comma-separated-column-ids>` with optional `--tasks <comma-separated-task-ids>`; normalize optional `t` prefixes and reject tasks outside the selected columns.
- Without explicit arguments, interactively select columns and review the ordered task list for inclusion/exclusion. With explicit task IDs, validate them and skip duplicate membership prompts.
- Treat the gatherer as an internal skill helper; do not add a new public `ait` CLI command.

### Manager-facing skill

- Add the canonical profile-agnostic skill and supported-agent wrappers following the repository's skill-authoring conventions.
- Ask for a report horizon on every run: Today, This week, or a custom label. The period labels the report but does not silently change task membership.
- Read each selected task's description, metadata, active plan when present, dependencies, and relevant child-task context.
- Draft first-person, manager-friendly Markdown containing a short focus summary, column-grouped ordered priorities with outcome and current status, task IDs for traceability, and a final blockers/manager-asks section.
- Include exactly the selected tasks. Do not invent dates, estimates, progress, commitments, dependencies, or blockers, and avoid implementation-level file/symbol detail.
- Present the draft for review/editing in the agent session only; do not automatically write a dated or repository report file.
- Use the shared satisfaction-feedback procedure with `skill_name: work-report`.

### Board workflow

- Register a customizable, footer-visible `w` binding named Work Report.
- Enable it only in persistent kanban views when a focused card or collapsed-column placeholder identifies a column; hide it in In-Flight/By-Topic views and when no reportable column is focused.
- First show a column multi-select with the focused column checked by default.
- Then show a task multi-select grouped by the chosen columns, with every underlying parent task checked by default. Use full column contents regardless of current search or board filters.
- Follow the existing SelectionList interaction: Space toggles, Enter confirms, Escape cancels. Preserve board ordering after exclusions.
- Do not launch when no columns or no tasks remain selected; show a clear notification instead.
- Launch the shared agent-command dialog with explicit `--columns` and `--tasks` arguments so the agent receives the exact board-reviewed selection.

### Agent dispatch and documentation

- Register `work-report` as a configurable read-only code-agent operation for Claude Code, Codex, and OpenCode, defaulting to the same lightweight model class used by `explain`.
- Treat the Codex operation as read-only analysis so it launches in default mode rather than forced Plan Mode.
- Add a skill reference page, a dedicated work-reporting workflow page, board shortcut/how-to documentation, and skills/workflows index entries.

## Verification

- Test gather ordering, multi-column grouping, selected subsets, optional `t` prefixes, invalid/moved/missing tasks, dynamic Unsorted behavior, duplicates, and empty selections.
- Add board Pilot/unit coverage for focused-column defaults, collapsed placeholders, full-column behavior under filters/search, selection cancellation, empty selection, footer visibility, shortcut registration, stable ordering, and exact launch arguments.
- Add dispatch dry-run tests for each supported agent and the Codex read-only policy.
- Run skill/wrapper verification and packaging/install coverage, plus documentation link/build checks.
- Manually smoke-test focusing a board column, pressing `w`, changing both selections, launching an agent, choosing a period, and confirming that the report contains exactly the selected tasks in board order.
