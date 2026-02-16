# Task File Format

## Table of Contents

- [File Structure](#file-structure)
- [Status Workflow](#status-workflow)
- [Parent-Child Hierarchies](#parent-child-hierarchies)
- [Customizing Task Types](#customizing-task-types)

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
| `issue_type` | `bug`, `feature`, `refactor`, `documentation` | Type of work (from `task_types.txt`) |
| `status` | `Ready`, `Editing`, `Implementing`, `Postponed`, `Done` | Current status |
| `labels` | `[ui, backend]` | Categorization labels |
| `created_at` | `YYYY-MM-DD HH:MM` | Creation timestamp |
| `updated_at` | `YYYY-MM-DD HH:MM` | Last modification timestamp |
| `completed_at` | `YYYY-MM-DD HH:MM` | Completion timestamp (set on archival) |
| `assigned_to` | email address | Developer working on the task |
| `issue` | URL | Linked GitHub/GitLab issue |
| `children_to_implement` | `[t10_1, t10_2]` | Remaining child tasks (parent tasks only) |
| `boardcol` | column ID | Board UI column placement |
| `boardidx` | integer | Board UI sort index within column |

---

## Status Workflow

```
Ready → Editing → Implementing → Done → Archived
```

- **Ready** — Task is defined and available for implementation
- **Editing** — Task is being refined (description, requirements)
- **Implementing** — Active development in progress (assigned to someone)
- **Postponed** — Deferred for later
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

## Customizing Task Types

Valid issue types are defined in `aitasks/metadata/task_types.txt` (one type per line, sorted alphabetically). The default types are:

```
bug
documentation
feature
refactor
```

To add a custom type, simply add a new line to the file. All scripts (`ait create`, `ait update`, `ait board`, `ait stats`) read from this file dynamically.
