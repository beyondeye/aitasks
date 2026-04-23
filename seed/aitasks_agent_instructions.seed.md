# aitasks Framework — Agent Instructions

This project uses the aitasks framework for task management.
Tasks are markdown files with YAML frontmatter stored in git.

## Task File Format

Task files use YAML frontmatter with these fields:

```yaml
---
priority: high|medium|low
effort: high|medium|low
depends: [1, 3]
issue_type: bug|feature|chore|documentation|performance|refactor|style|test
status: Ready|Editing|Implementing|Postponed|Done|Folded
labels: [ui, backend]
assigned_to: email
boardcol: now|next|backlog
boardidx: 50
folded_tasks: [2, 4]     # merged child tasks
folded_into: 1            # parent task ID if folded
issue: https://...        # linked issue tracker URL
---
```

## Task Hierarchy

Parent tasks live in `aitasks/` (e.g., `aitasks/t130_feature_name.md`).
Child tasks live in subdirectories: `aitasks/t130/t130_1_subtask.md`,
`t130_2_subtask.md`, etc. Children auto-depend on siblings.

Plans mirror the task structure: parent plans in `aiplans/`, child plans
in `aiplans/p130/p130_1_subtask.md`.

## Git Operations on Task/Plan Files

When committing changes to files in `aitasks/` or `aiplans/`, always use
`./ait git` instead of plain `git`. This ensures correct branch targeting
when task data lives on a separate branch.

- `./ait git add aitasks/t42_foo.md`
- `./ait git commit -m "ait: Update task t42"`
- `./ait git push`

In legacy mode (no separate branch), `./ait git` passes through to plain `git`.

## Commit Message Format

```
<type>: <description> (tNN)
```

Types match `issue_type` values: `bug`, `feature`, `chore`, `documentation`,
`performance`, `refactor`, `style`, `test`. Also `ait` for framework-internal
changes (task/plan file operations).

Code commits use `<type>: <description> (tNN)`. Plan/task file commits use
`ait: <description>`. Never mix code and task/plan files in the same commit.

## Folded Task Semantics

Folded tasks are **merged** into the primary task — not superseded or
replaced. At fold time the folded content is incorporated into the primary
task's description (see `## Merged from t<N>` headers). The folded file
remains on disk only as a reference for post-implementation cleanup; it is
deleted during archival. Always use "merged" / "incorporated" language —
never "superseded" / "replaced".

## Manual Verification Tasks

Tasks with `issue_type: manual_verification` dispatch to a
Pass/Fail/Skip/Defer checklist loop instead of the plan+implement flow.
They are used for behavior only a human can validate (TUI flows, live
agent launches, multi-screen navigation, on-disk artifact inspection).
After a regular task that produces UX-affecting changes, the workflow
may offer to queue a follow-up manual-verification task.
