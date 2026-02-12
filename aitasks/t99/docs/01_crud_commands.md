<!-- SECTION: Command Reference — CRUD Commands -->
<!-- PLACEMENT: after "### Usage Examples" in Command Reference -->

### ait create

Create new task files with YAML frontmatter metadata. Supports standalone and parent/child task hierarchies.

**Interactive mode** (default — requires fzf):

1. **Parent selection** — Choose "None - create standalone task" or select an existing task as parent from a fzf list of all tasks (shown with status/priority/effort metadata)
2. **Priority** — Select via fzf: high, medium, low
3. **Effort** — Select via fzf: low, medium, high
4. **Issue type** — Select via fzf from `aitasks/metadata/task_types.txt` (bug, documentation, feature, refactor)
5. **Status** — Select via fzf: Ready, Editing, Implementing, Postponed
6. **Labels** — Iterative loop: pick from existing labels in `aitasks/metadata/labels.txt`, add a new label (auto-sanitized to lowercase alphanumeric + hyphens/underscores), or finish. New labels are persisted to the labels file for future use
7. **Dependencies** — fzf multi-select from all open tasks. For child tasks, sibling tasks appear at the top of the list. Select "None" or press Enter with nothing selected to skip
8. **Sibling dependency** (child tasks only, when child number > 1) — Prompted whether to depend on the previous sibling (e.g., t10_1). Defaults to suggesting "Yes"
9. **Task name** — Free text entry, auto-sanitized: lowercase, spaces to underscores, special chars removed, max 60 characters
10. **Description** — Iterative loop: enter text blocks, optionally add file references (fzf file walker with preview of first 50 lines, can also remove previously added references), then choose "Add more description" or "Done - create task"
11. **Post-creation** — Choose: "Show created task" (prints file contents), "Open in editor" ($EDITOR), or "Done"
12. **Git commit** — Prompted Y/n to commit the task file

**Batch mode** (for automation and scripting):

```bash
ait create --batch --name "fix_login_bug" --desc "Fix the login issue"
ait create --batch --parent 10 --name "subtask" --desc "First subtask" --commit
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
| `--commit` | Auto-commit to git |
| `--silent` | Output only filename (for scripting) |

**Key features:**
- Auto-determines next task number from active, archived, and compressed (`old.tar.gz`) tasks
- Child tasks stored in `aitasks/t<parent>/` with naming `t<parent>_<child>_<name>.md`
- Updates parent's `children_to_implement` list when creating child tasks
- Name sanitization: lowercase, underscores, no special characters, max 60 chars

---

### ait ls

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

### ait update

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

---

<!-- SECTION: Claude Code Integration — Create Skills -->
<!-- PLACEMENT: after existing /aitask-create section -->

### /aitask-create

Create a new task file with automatic numbering and proper metadata via Claude Code prompts.

**Usage:**
```
/aitask-create
```

**Workflow:** Claude Code guides you through task creation using `AskUserQuestion` prompts:

1. **Parent selection** — Choose standalone or child of existing task
2. **Task number** — Auto-determined from active, archived, and compressed tasks
3. **Metadata** — Priority, effort, dependencies (with sibling dependency prompt for child tasks)
4. **Task name** — Free text with auto-sanitization
5. **Definition** — Iterative content collection with file reference insertion via Glob search
6. **Create & commit** — Writes task file with YAML frontmatter and commits to git

This is the Claude Code-native alternative — metadata collection happens through Claude's UI rather than terminal fzf. Use `/aitask-create2` for a faster terminal-native experience.

### /aitask-create2

Create a new task file using the terminal-native fzf interface — a faster alternative to `/aitask-create`.

**Usage:**
```
/aitask-create2
```

Launches `./aiscripts/aitask_create.sh` directly in the terminal. All prompts use fzf for fast, keyboard-driven selection:

- Parent task selection with fzf
- Priority, effort, issue type, status via fzf menus
- Labels with iterative fzf selection (existing + new)
- Dependencies via fzf multi-select with sibling tasks listed first
- Task name with auto-sanitization
- Description entry with fzf file walker for inserting file references (includes preview)
- Post-creation: view, edit in $EDITOR, or finish
- Optional git commit

**Batch mode** (for automation by AI agents):

```bash
./aiscripts/aitask_create.sh --batch --parent 10 --name "subtask" --desc "Description"
./aiscripts/aitask_create.sh --batch --parent 10 --name "parallel" --desc "Work" --no-sibling-dep
```

Preferred when speed matters — fzf selections are faster than Claude Code's `AskUserQuestion` prompts.
