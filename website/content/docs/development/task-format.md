---
title: "Task File Format"
linkTitle: "Task Format"
weight: 10
description: "YAML frontmatter schema and conventions for task files"
depth: [advanced]
---

## File Structure

Tasks are markdown files with YAML frontmatter in the `aitasks/` directory. Task files use the naming convention `t<number>_<name>.md`. Executed task files are stored in `aitasks/archived/` and their associated plan files in `aiplans/archived/`.

```yaml
---
priority: high
effort: medium
depends: []
issue_type: feature  # See aitasks/metadata/task_types.txt for valid types
status: Ready
labels: [ui, backend]
created_at: 2026-01-15 10:00
updated_at: 2026-01-15 10:00
---

## Task description here

Detailed description of what needs to be done.
```

### Frontmatter Fields

| Field | Values | Description |
|-------|--------|-------------|
| `priority` | `high`, `medium`, `low` | Task priority for sorting |
| `effort` | `low`, `medium`, `high` | Estimated implementation effort |
| `depends` | `[1, 4]` | List of task numbers this depends on |
| `issue_type` | `bug`, `chore`, `documentation`, `feature`, `performance`, `refactor`, `style`, `test` | Type of work (from `task_types.txt`) |
| `status` | `Ready`, `Editing`, `Implementing`, `Postponed`, `Done`, `Folded` | Current status |
| `labels` | `[ui, backend]` | Categorization labels |
| `created_at` | `YYYY-MM-DD HH:MM` | Creation timestamp |
| `updated_at` | `YYYY-MM-DD HH:MM` | Last modification timestamp |
| `completed_at` | `YYYY-MM-DD HH:MM` | Completion timestamp (set on archival) |
| `assigned_to` | email address | Developer working on the task |
| `issue` | URL | Linked GitHub/GitLab/Bitbucket issue |
| `children_to_implement` | `[t10_1, t10_2]` | Remaining child tasks (parent tasks only) |
| `boardcol` | column ID | Board UI column placement |
| `boardidx` | integer | Board UI sort index within column |
| `folded_tasks` | `[138, 129_5]` | Task IDs folded into this task by `/aitask-explore` or `/aitask-fold` (deleted on archival) |
| `folded_into` | task number | Task this was folded into (set by `/aitask-fold` or `/aitask-explore`) |
| `file_references` | `[path, path:N, path:N-M, path:N-M^N-M]` | Structured pointers to source files / line ranges. 1-indexed, inclusive. Exact-string dedup. See [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}) |
| `verifies` | `[t10_1, t10_2]` | Task IDs this task verifies (used by `manual_verification` sibling tasks that gate release on human-checked behavior) |
| `implemented_with` | `<agent>/<model>` | Agent and model that implemented the task (e.g., `claudecode/opus4_7_1m`). See [Agent attribution]({{< relref "/docs/concepts/agent-attribution" >}}) |
| `pull_request` | URL | Linked pull request URL (mirrors `issue`) |
| `contributor` | name | External contributor credited on the commit (used by PR-import flow) |
| `contributor_email` | email | Email for the contributor's `Co-Authored-By` trailer |

---

## Status Workflow

```
Ready → Editing → Implementing → Done → Archived
                              ↘ Folded (merged into another task)
```

- **Ready** — Task is defined and available for implementation
- **Editing** — Task is being refined (description, requirements)
- **Implementing** — Active development in progress (assigned to someone)
- **Postponed** — Deferred for later
- **Folded** — Task was merged into another task via `/aitask-fold` or `/aitask-explore`; deleted on archival of the primary task
- **Done** — Implementation complete, pending archival
- **Archived** — Task and plan files moved to `archived/` directories

---

## Parent-Child Hierarchies

Tasks support parent-child hierarchies for breaking complex work into subtasks:

- **Parent tasks** live in `aitasks/` (e.g., `aitasks/t10_implement_auth.md`)
- **Child tasks** live in `aitasks/t<parent>/` (e.g., `aitasks/t10/t10_1_add_login.md`)
- **Child plans** live in `aiplans/p<parent>/` (e.g., `aiplans/p10/p10_1_add_login.md`)

Parent tasks track remaining children via the `children_to_implement` frontmatter field. When all children are complete, the parent is automatically archived.

Child task IDs use the format `t<parent>_<child>_<name>.md` where both parent and child identifiers are numbers only. Do not insert tasks "in-between" (e.g., no `t10_1b`). If you discover a missing step, add it as the next available number and adjust dependencies.

---

## Archive Storage

Completed tasks move through the archive lifecycle:

1. **Archived directory** — `aitasks/archived/t150_feature.md` (loose files, recent)
2. **Numbered archives** — `aitasks/archived/_b0/old1.tar.gz` (compressed bundles)

The numbering scheme groups tasks by hundreds:

| Task IDs | Bundle | Directory | Archive Path |
|----------|--------|-----------|-------------|
| 0–99 | 0 | 0 | `archived/_b0/old0.tar.gz` |
| 100–199 | 1 | 0 | `archived/_b0/old1.tar.gz` |
| 900–999 | 9 | 0 | `archived/_b0/old9.tar.gz` |
| 1000–1099 | 10 | 1 | `archived/_b1/old10.tar.gz` |

**Computation:**
- `bundle = task_id / 100` (integer division)
- `directory = bundle / 10` (integer division)
- `path = archived/_b{directory}/old{bundle}.tar.gz`

The `_b` prefix on directory names avoids collision with task child directories (`t<N>/`).

Child tasks are archived with their parent's bundle (e.g., `t130/t130_2_subtask.md` goes into `old1.tar.gz` alongside `t130_feature.md`).

Plan archives follow the same scheme under `aiplans/archived/`.

---

## Customizing Task Types

Valid issue types are defined in `aitasks/metadata/task_types.txt` (one type per line, sorted alphabetically). The default types are:

```
bug
chore
documentation
feature
performance
refactor
style
test
```

To add a custom type, simply add a new line to the file. All scripts (`ait create`, `ait update`, [`ait board`](../../tuis/board/), `ait stats`) read from this file dynamically.

---

**Next:** [Review Guide Format]({{< relref "/docs/development/review-guide-format" >}})
