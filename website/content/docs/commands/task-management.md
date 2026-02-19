---
title: "Task Management"
linkTitle: "Task Management"
weight: 20
description: "ait create, ait ls, and ait update commands"
---

## ait create

Create new task files with YAML frontmatter metadata. Supports standalone and parent/child task hierarchies.

**Interactive mode** (default — requires fzf):

0. **Draft management** — If drafts exist in `aitasks/new/`, a menu appears: select a draft to continue editing, finalize (assign real ID and commit), or delete — or create a new task
1. **Parent selection** — Choose "None - create standalone task" or select an existing task as parent from a fzf list of all tasks (shown with status/priority/effort metadata)
2. **Priority** — Select via fzf: high, medium, low
3. **Effort** — Select via fzf: low, medium, high
4. **Issue type** — Select via fzf from `aitasks/metadata/task_types.txt` (bug, chore, documentation, feature, performance, refactor, style, test)
5. **Status** — Select via fzf: Ready, Editing, Implementing, Postponed
6. **Labels** — Iterative loop: pick from existing labels in `aitasks/metadata/labels.txt`, add a new label (auto-sanitized to lowercase alphanumeric + hyphens/underscores), or finish. New labels are persisted to the labels file for future use
7. **Dependencies** — fzf multi-select from all open tasks. For child tasks, sibling tasks appear at the top of the list. Select "None" or press Enter with nothing selected to skip
8. **Sibling dependency** (child tasks only, when child number > 1) — Prompted whether to depend on the previous sibling (e.g., t10_1). Defaults to suggesting "Yes"
9. **Task name** — Free text entry, auto-sanitized: lowercase, spaces to underscores, special chars removed, max 60 characters. Preview shows `draft_*_<name>.md` (real ID is assigned during finalization)
10. **Description** — Iterative loop: enter text blocks, optionally add file references (fzf file walker with preview of first 50 lines, can also remove previously added references), then choose "Add more description" or "Done - create task"
11. **Post-creation** — Choose: "Finalize now" (claim real ID and commit), "Show draft", "Open in editor" ($EDITOR), or "Save as draft" (finalize later via `ait create` or `--batch --finalize`)

**Batch mode** (for automation and scripting):

```bash
# Creates draft in aitasks/new/ (no network needed)
ait create --batch --name "fix_login_bug" --desc "Fix the login issue"

# Auto-finalize: claim real ID and commit immediately (requires network)
ait create --batch --name "add_feature" --desc "New feature" --commit

# Finalize a specific draft
ait create --batch --finalize draft_20260213_1423_fix_login.md

# Finalize all pending drafts
ait create --batch --finalize-all

# Child task (auto-finalized with --commit)
ait create --batch --parent 10 --name "subtask" --desc "First subtask" --commit

# Read description from stdin
echo "Long description" | ait create --batch --name "my_task" --desc-file -
```

| Option | Description |
|--------|-------------|
| `--batch` | Enable batch mode (non-interactive) |
| `--name, -n NAME` | Task name (required, auto-sanitized) |
| `--desc, -d DESC` | Task description text |
| `--desc-file FILE` | Read description from file (use `-` for stdin) |
| `--priority, -p LEVEL` | high, medium, low (default: medium) |
| `--effort, -e LEVEL` | low, medium, high (default: medium) |
| `--type, -t TYPE` | Issue type from task_types.txt (default: feature) |
| `--status, -s STATUS` | Ready, Editing, Implementing, Postponed (default: Ready) |
| `--labels, -l LABELS` | Comma-separated labels |
| `--deps DEPS` | Comma-separated dependency task numbers |
| `--parent, -P NUM` | Create as child of parent task number |
| `--no-sibling-dep` | Don't auto-add dependency on previous sibling |
| `--assigned-to, -a EMAIL` | Assignee email |
| `--issue URL` | Linked issue tracker URL |
| `--commit` | Claim real ID and commit to git immediately (auto-finalize) |
| `--finalize FILE` | Finalize a specific draft from `aitasks/new/` (claim ID, move to `aitasks/`, commit) |
| `--finalize-all` | Finalize all pending drafts in `aitasks/new/` |
| `--silent` | Output only filename (for scripting) |

**Key features:**
- Tasks are created as **drafts** in `aitasks/new/` by default (no network required). Finalization claims a globally unique ID from an atomic counter on the `aitask-ids` git branch
- Drafts use timestamp-based filenames (`draft_YYYYMMDD_HHMM_<name>.md`) and are local-only (gitignored)
- Child task IDs are assigned via local scan (safe because the parent's unique ID acts as a namespace)
- Atomic counter fallback: in interactive mode, warns and asks for consent to use local scan; in batch mode, fails hard if counter is unavailable
- Child tasks stored in `aitasks/t<parent>/` with naming `t<parent>_<child>_<name>.md`
- Updates parent's `children_to_implement` list when creating child tasks
- Name sanitization: lowercase, underscores, no special characters, max 60 chars
- Duplicate ID detection: `ait ls` warns if duplicate task IDs are found; `ait update` fails with a suggestion to run `ait setup`

---

## ait ls

List and filter tasks sorted by priority, effort, and blocked status.

```bash
ait ls -v 15                    # Top 15 tasks, verbose
ait ls -v -l ui,backend 10     # Filter by labels
ait ls -v -s all --tree 99     # Tree view, all statuses
ait ls -v --children 10 99     # List children of task t10
```

| Option | Description |
|--------|-------------|
| `[NUMBER]` | Limit output to top N tasks |
| `-v` | Verbose: show status, priority, effort, assigned, issue |
| `-s, --status STATUS` | Filter by status: Ready (default), Editing, Implementing, Postponed, Done, all |
| `-l, --labels LABELS` | Filter by labels (comma-separated, matches any) |
| `-c, --children PARENT` | List only children of specified parent task number |
| `--all-levels` | Show all tasks including children (flat list) |
| `--tree` | Hierarchical tree view with children indented under parents |

**Sort order** (unblocked tasks first, then): priority (high > medium > low) → effort (low > medium > high).

**View modes:**
- **Normal** (default) — Parent tasks only. Parents with pending children show "Has children" status
- **Children** (`--children N`) — Only child tasks of parent N
- **All levels** (`--all-levels`) — Flat list of all parents and children
- **Tree** (`--tree`) — Parents with children indented using `└─` prefix

**Metadata format:** Supports both YAML frontmatter (primary) and legacy single-line format (`--- priority:high effort:low depends:1,4`).

---

## ait update

Update task metadata fields interactively or in batch mode. Supports parent and child tasks.

**Interactive mode** (default — requires fzf):

1. **Task selection** — If no task number argument given, select from fzf list of all tasks (shown with metadata). Can also pass task number directly: `ait update 25`
2. **Field selection loop** — fzf menu showing all editable fields with current values:
   - `priority [current: medium]`
   - `effort [current: low]`
   - `status [current: Ready]`
   - `issue_type [current: feature]`
   - `dependencies [current: None]`
   - `labels [current: ui,backend]`
   - `description [edit in editor]`
   - `rename [change filename]`
   - `Done - save changes`
   - `Exit - discard changes`
3. **Per-field editing:**
   - **priority/effort/status/issue_type** — fzf selection from valid values
   - **dependencies** — fzf multi-select from all tasks (excluding current), with "Clear all dependencies" option
   - **labels** — Iterative fzf loop: select existing label, add new label (sanitized), clear all, or done
   - **description** — Shows current text, then offers "Open in editor" ($EDITOR with GUI editor support for VS Code, Sublime, etc.) or "Skip"
   - **rename** — Text entry for new name (sanitized), displays preview of new filename
4. **Save** — Select "Done" to write changes. "Exit" discards all changes
5. **Git commit** — Prompted Y/n to commit

**Batch mode** (for automation):

```bash
ait update --batch 25 --priority high --status Implementing
ait update --batch 25 --add-label "urgent" --remove-label "low-priority"
ait update --batch 25 --name "new_task_name" --commit
ait update --batch 10_1 --status Done           # Update child task
ait update --batch 10 --remove-child t10_1      # Remove child from parent
```

| Option | Description |
|--------|-------------|
| `--batch` | Enable batch mode |
| `--priority, -p LEVEL` | high, medium, low |
| `--effort, -e LEVEL` | low, medium, high |
| `--status, -s STATUS` | Ready, Editing, Implementing, Postponed, Done |
| `--type TYPE` | Issue type from task_types.txt |
| `--deps DEPS` | Dependencies (comma-separated, replaces all) |
| `--labels, -l LABELS` | Labels (comma-separated, replaces all) |
| `--add-label LABEL` | Add a single label (repeatable) |
| `--remove-label LABEL` | Remove a single label (repeatable) |
| `--description, -d DESC` | Replace description text |
| `--desc-file FILE` | Read description from file (use `-` for stdin) |
| `--name, -n NAME` | Rename task (changes filename) |
| `--assigned-to, -a EMAIL` | Assignee email (use `""` to clear) |
| `--issue URL` | Issue tracker URL (use `""` to clear) |
| `--add-child CHILD_ID` | Add child to `children_to_implement` |
| `--remove-child CHILD_ID` | Remove child from `children_to_implement` |
| `--children CHILDREN` | Set all children (replaces list) |
| `--boardcol COL` | Board column ID |
| `--boardidx IDX` | Board sort index |
| `--commit` | Auto-commit to git |
| `--silent` | Output only filename |

**Key features:**
- Auto-updates `updated_at` timestamp on every write
- Child task format: use `10_1` or `t10_1` to target child tasks
- When a child task is set to Done, automatically removes it from parent's `children_to_implement` and warns when all children are complete
- Parent tasks cannot be set to Done while `children_to_implement` is non-empty
