---
title: "Creating Tasks from Code"
linkTitle: "Creating Tasks from Code"
weight: 65
description: "Browse source files, select a line range, and spawn a task pre-seeded with a file reference — with optional auto-merge of overlapping pending tasks."
---

When you spot a TODO, a smell, or a bug while reading a file, you want a task that points at the exact lines so the implementing agent already has the context. The `file_references` frontmatter field is the structured home for those pointers, and `ait codebrowser` + `aitask_create.sh` together turn "I saw something weird on line 42" into a committed task without ever leaving your viewer.

This workflow ties together:

- The `file_references` field on task files
- The `n` keybinding in `ait codebrowser`
- The `--file-ref`, `--auto-merge`, and `--no-auto-merge` flags on `aitask_create.sh`
- The `File Refs` row in the `ait board` task detail dialog — the return trip from task back to code

## The `file_references` frontmatter field

`file_references` is a list of structured pointers to source locations. Each entry is a relative path, optionally followed by a line or range suffix:

```yaml
---
file_references:
  - lib/auth.py                       # whole file
  - lib/auth.py:42                    # single line (1-indexed)
  - lib/auth.py:42-68                 # inclusive range
  - lib/login.py:10-20^30-40^89-100   # compact multi-range on one path
---
```

Rules:

- Lines are **1-indexed and inclusive**.
- Entries use **exact-string dedup** — `foo.py:10-20` and `foo.py:10-20^30-40` coexist.
- Order is preserved.
- Every entry is regex-validated at CLI parse time:
  `^[^:]+(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)?$`

See [Task Format]({{< relref "/docs/development/task-format" >}}) for the complete frontmatter schema.

## Creating a task from the code browser (`n`)

The primary flow is driven from the code viewer in `ait codebrowser`:

1. Launch `ait codebrowser` and navigate to the file you want to reference.
2. Optionally select a range with **Shift+Up / Shift+Down** or a mouse drag. A single cursor line is fine — the current line is used as a fallback.
3. Press **n**.
4. An `AgentCommandScreen` opens with a title like `Create task — lib/auth.py (lines 42-68)` and a pre-filled command:

   ```bash
   ./.aitask-scripts/aitask_create.sh --file-ref "lib/auth.py:42-68"
   ```

5. Choose **Run** (new terminal) or **Run in tmux** (new tmux window). You can edit the command before running — for example, append `--auto-merge` to fold any pending tasks that already reference this file.
6. The normal interactive `aitask_create.sh` flow launches with a banner:

   ```
   Pre-populated file references: lib/auth.py:42-68
   ```

   Walk through description → labels → metadata → finalize as usual.
7. The finalized task has `file_references: ["lib/auth.py:42-68"]` in its frontmatter and is committed to git.

**Fallback behavior:**

| Selection state              | Resulting reference |
|------------------------------|---------------------|
| Multi-line selection         | `path:start-end`    |
| One-line selection           | `path:N`            |
| No selection (cursor only)   | `path:<cursor_line>` |

## Auto-merging overlapping pending tasks

The real leverage of `file_references` is that `aitask_create.sh` can notice when a new task overlaps an existing one and offer to fold them together. This keeps pending work about the same code in one place instead of scattered across near-duplicate tasks.

**How candidates are found:**

After the new task is committed, the create script reads its `file_references`, extracts the distinct paths (stripping any `:N-M^...` suffix), and runs `aitask_find_by_file.sh` on each path. The helper emits `TASK:<id>:<file>` lines for matches. Path-only matching is deliberate — multi-range entries still match by file.

**Three safety layers** gate what actually gets folded:

1. **Status filter** — only tasks with status `Ready` or `Editing` are candidates. `Implementing`, `Done`, `Folded`, and `Postponed` are excluded.
2. **Fold validator** — `aitask_fold_validate.sh --exclude-self` drops anything with children, self, or wrong status.
3. **Explicit opt-in** — folding only runs when you ask for it.

**Default (warn-and-skip):**

Without `--auto-merge`, the script lists the overlapping candidates and continues without folding. In the **interactive** flow launched from the codebrowser `n` flow, you first get an fzf `Yes/No` prompt: "Fold N matching task(s) into tX?" Choosing **No** falls through to the warn-and-skip path. Choosing **Yes** runs the fold chain described below.

**With `--auto-merge`:**

The three-step fold chain runs:

1. `aitask_fold_validate.sh --exclude-self <new_id> <candidate_ids...>`
2. `aitask_fold_content.sh <new_file> <folded_files...> | aitask_update.sh --batch <new_id> --desc-file -` — merges the folded task descriptions into the new task body.
3. `aitask_fold_mark.sh --commit-mode fresh <new_id> <folded_ids...>` — marks each folded task with `status: Folded` and `folded_into: <new_id>`, then commits.

At fold time, `file_references` are **unioned as exact strings** — the primary task absorbs every folded entry verbatim, without any range arithmetic. Duplicates are removed.

## Opening a task's file refs from the board

The board's task detail dialog has a **File Refs** row that closes the loop — from a task card back to the code it describes.

1. In `ait board`, press **Enter** on any task card to open the task detail dialog.
2. The **File Refs** row shows every entry verbatim (or `(none)` dimmed if the list is empty).
3. Use **Up / Down** (or **Tab**) to focus the row, then press **Enter**.

Dispatch depends on the number of entries:

| Entries | Enter behavior |
|---------|---------------|
| 0       | No-op         |
| 1       | Opens `ait codebrowser` on that file, with the cursor placed at the entry's start line (range selected, if any) |
| 2+      | A picker opens first; pick an entry, then dispatch as above |

Under the hood this calls `launch_or_focus_codebrowser(session, entry)` in `.aitask-scripts/board/lib/agent_launch_utils.py`. Inside a tmux session, the launcher **reuses an existing codebrowser window** if one is running and switches it to the target file and line — otherwise it opens a fresh codebrowser process.

## Doing it from the command line

For power users and automation, skip the codebrowser and call the scripts directly:

```bash
# Create a task from a file:line range and auto-fold overlapping pending tasks
./.aitask-scripts/aitask_create.sh --batch --commit \
    --name "rework_token_validation" --priority medium --effort medium \
    --type refactor --labels "auth,tech-debt" \
    --file-ref "lib/auth.py:42-68" \
    --auto-merge \
    --desc "Rework the token validation path"

# Multiple refs, including a multi-range on one path
./.aitask-scripts/aitask_create.sh --batch --commit \
    --name "login_cleanup" \
    --file-ref "lib/login.py:10-20^89-100" \
    --file-ref "lib/auth.py:42-68" \
    --desc "Unify login edge cases"

# Update an existing task's file refs
./.aitask-scripts/aitask_update.sh --batch 42 \
    --file-ref "lib/auth.py:100-150" \
    --remove-file-ref "lib/auth.py:42-68"

# List pending tasks that already reference a file
./.aitask-scripts/aitask_find_by_file.sh lib/auth.py
```

Notes:

- `--auto-merge` is **opt-in**. The default is `--no-auto-merge` (warn-and-skip), which is the safer choice when scripting in CI.
- `aitask_find_by_file.sh` outputs `TASK:<id>:<file>` lines, filtered to `Ready` / `Editing`. It matches on the path only, so multi-range entries still show up.
- `--file-ref` is repeatable on both `aitask_create.sh` and `aitask_update.sh`. On `aitask_update.sh`, pair it with `--remove-file-ref` to drop stale entries.

## See also

- [Task Format]({{< relref "/docs/development/task-format" >}}) — the `file_references` field in the full frontmatter schema
- [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) — the `n` keybinding in context, plus the "Creating Tasks from Code" tutorial section
- [Board How-To]({{< relref "/docs/tuis/board/how-to#how-to-navigate-task-relationships" >}}) — the File Refs row in the relationship table
- [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) — the skill that drives the interactive create flow
- [Follow-Up Tasks]({{< relref "/docs/workflows/follow-up-tasks" >}}) — the sibling workflow for capturing tasks during implementation
