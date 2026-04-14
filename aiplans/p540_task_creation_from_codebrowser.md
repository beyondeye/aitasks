---
Task: t540_task_creation_from_codebrowser.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# t540 — Task creation from codebrowser TUI

## Context

Today `aitask_create.sh` only accepts file attachments by dropping raw paths
into the description body — no structured field, no line ranges, no way for
other tooling to find "tasks about file X". The `ait codebrowser` TUI (Textual,
`.aitask-scripts/codebrowser/codebrowser_app.py`) already supports line-range
selection via `CodeViewer.get_selected_range()` but has no "create task"
binding.

The user wants the inverse workflow: highlight a file + line range in the
codebrowser and spawn an aitask whose context already points at that file:line.
When it does, the creation flow should detect existing pending tasks that
reference the same file and offer to fold them into the new one (reusing the
existing `aitask_fold_*` scripts). Because a new frontmatter field is being
added, `aitask_update.sh` AND `ait board`'s task-detail modal must also
understand it. The board should further expose a new action from the
`file_references` detail field that jumps into `ait codebrowser` with the
referenced file open and lines pre-selected — mirroring the recent minimonitor
"m" shortcut that switches back to full `ait monitor` with a specific
codeagent focused (tmux env-var handoff at
`.aitask-scripts/monitor/minimonitor_app.py:510-549`). As an independent
quality-of-life improvement, the interactive label picker in `aitask_create.sh`
should offer a "use labels from previous task" option, stored per-user in
`aitasks/metadata/userconfig.yaml`.

Complexity is high: it spans bash create/update/fold scripts, a new query
helper, the Python Textual codebrowser app, the board's task-detail modal, and
a per-user config field. Per user instructions, this must be split into child
tasks.

## Design decisions (confirmed with user)

1. **`file_references` storage** — new frontmatter YAML list of strings in the
   form `path` or `path:N` or `path:N-M` (1-indexed inclusive). Mirrors the
   existing `labels` / `depends` shape: simple to serialize, easy to grep and
   parse without yq.
2. **Codebrowser → create invocation** — codebrowser spawns *interactive*
   `aitask_create.sh --file-ref <path>:<start>-<end>` through the same
   subprocess/terminal pattern the board TUI uses
   (`aitask_board.py:3722-3741`, `AgentCommandScreen`). No in-TUI Textual
   form — the interactive bash flow handles labels/priority/description for
   free.
3. **Auto-merge scope** — the "tasks already referencing this file" check runs
   any time `aitask_create.sh` sees a `--file-ref`, not only from the
   codebrowser path. Uniform behavior.
4. **Field propagation (from user feedback)** — new frontmatter fields touch
   three layers: the bash scripts that write them (`aitask_create.sh`,
   `aitask_update.sh`), and the board's `TaskDetailScreen`
   (`aitask_board.py:1765-1914`) which renders per-field widgets. All three
   must be updated in lock-step.
5. **Board → codebrowser handoff** — mirror minimonitor's "m" action: set a
   tmux session env var (`AITASK_CODEBROWSER_FOCUS=<path>:<start>-<end>`),
   then switch to an existing codebrowser window or spawn a new one. The
   codebrowser app consumes the env var on startup and on a periodic poll
   (same `_consume_focus_request` pattern as `monitor_app.py:548-572`).

## Child task split

### t540_1 — Foundation: `file_references` in bash (create, update, find)

Everything else depends on this. Keep it focused on plumbing.

- **`file_references` frontmatter field** — YAML list of strings, entries are
  `path`, `path:N`, or `path:N-M` (1-indexed inclusive). Serialized by
  `create_task_file()` in `aitask_create.sh:1122-1184` alongside the existing
  `labels` field.
- **`--file-ref PATH[:START[-END]]` flag** — repeatable, added to both
  `aitask_create.sh` (parse_args `:115-143`) and `aitask_update.sh`
  (parse_args `:177-223`). In `aitask_update.sh`, pair with
  `--remove-file-ref PATH[:START[-END]]` for surgical removal (matches the
  existing `--remove-child` idiom). `--file-ref` appends, there is no
  "replace-all" variant in the first pass.
- **New helper `.aitask-scripts/aitask_find_by_file.sh <path>`** — scans
  active `aitasks/*.md` and `aitasks/t*/t*_*.md`, prints one
  `TASK:<task_id>:<task_file>` line per pending (`Ready`|`Editing`) task
  whose `file_references` contains a matching path (path-only match, line
  ranges ignored). Skips `Implementing`/`Postponed`/`Done`/`Folded`. Mirrors
  the structured-output convention of `aitask_query_files.sh` /
  `aitask_fold_validate.sh`. Uses portable grep/awk only (no PCRE — CLAUDE.md
  portability notes).
- **New library helper in `.aitask-scripts/lib/task_utils.sh`** —
  `get_file_references(<task_file>)` that parses the frontmatter list. Same
  sed/awk style as existing helpers.
- **New test** — `tests/test_file_references.sh` covering: batch create with
  `--file-ref` (single, multiple, with ranges), batch update add/remove,
  `aitask_find_by_file.sh` hit and miss, status-filter exclusion,
  round-tripping through the task file.

Dependencies: none (within t540).

### t540_2 — Codebrowser focus mechanism (CLI + env-var handoff)

Prerequisite for the board → codebrowser handoff (t540_5) and also a cleaner
way for any caller to navigate the codebrowser. Ship it early so downstream
children can target it.

- **CLI arg on `aitask_codebrowser.sh` / `codebrowser_app.py`** —
  `--focus PATH[:START[-END]]`. Parsed in a new `main()` arg block in
  `codebrowser_app.py` (currently just `CodeBrowserApp().run()` — no argparse
  present). On startup, if set, select the file in `ProjectFileTree`, open it
  in `CodeViewer`, set the cursor and selection.
- **Env-var handoff** — mirror
  `monitor_app.py._consume_focus_request()` (lines 548-572). Add
  `_consume_codebrowser_focus()` in `codebrowser_app.py` that reads
  `AITASK_CODEBROWSER_FOCUS` from the tmux session env, processes it once,
  and unsets it. Wire it into:
  - startup (after the app mounts, so a freshly-spawned window picks it up),
  - a periodic `set_interval` poll (so a pre-existing codebrowser window
    reacts to a hot handoff from the board).
- **Shared launcher helper** — `launch_or_focus_codebrowser(session,
  focus_value)` added to `.aitask-scripts/lib/agent_launch_utils.py`
  alongside the existing `maybe_spawn_minimonitor` / `launch_in_tmux`
  helpers (lines 162-279). Sets the env var, then either selects an existing
  codebrowser window or spawns a new one with `ait codebrowser --focus
  <value>` as the fallback command.
- Manual verification: from a second shell, run
  `tmux set-environment -t <session> AITASK_CODEBROWSER_FOCUS
  path/to/file.py:40-55` while codebrowser is open; confirm the viewer jumps
  to that range within one poll interval.

Dependencies: none.

### t540_3 — Auto-merge detection in `aitask_create.sh`

- After `aitask_create.sh` parses its args and confirms at least one
  `--file-ref` was supplied, iterate the distinct paths and call
  `aitask_find_by_file.sh` for each. Collect the union of matching task IDs
  (de-dup).
- **Interactive mode**: present the matches via fzf (`Select tasks to merge
  into the new task`) with the same `>> Done / >> None` exit options the
  label picker uses. User picks zero, some, or all.
- **Batch mode**: add `--auto-merge` / `--no-auto-merge` flags; default is
  `--no-auto-merge` for backwards compatibility. When `--auto-merge` is set
  and matches are found, fold all of them (no prompt).
- **Fold mechanics** — the new task must exist on disk before
  `aitask_fold_content.sh` / `aitask_fold_mark.sh` can run. Sequence:
  1. Write the new task file as normal (honoring all interactive answers,
     including `file_references`).
  2. Run `aitask_fold_validate.sh --exclude-self <new_id> <match_id1> ...`
     to drop any ineligible matches.
  3. Pipe `aitask_fold_content.sh <new_task_file> <matched_files...>`
     through `aitask_update.sh --batch <new_id> --desc-file -` to merge
     descriptions.
  4. Run `aitask_fold_mark.sh --commit-mode fresh <new_id> <match_ids...>`
     to mark folded tasks and commit.
  This reuses the fold scripts verbatim and keeps the fold commit separate
  from task-creation.

**Auto-merge exclusion safety — three layers:**

The concern is: when task A was folded into task B for `foo.py`, and the user
later creates task C also referencing `foo.py`, task A must not resurface as
a merge candidate, and the transitive relationship must be preserved. Three
layers make this safe:

1. **Source-level filter in `aitask_find_by_file.sh` (t540_1):** the helper
   only returns tasks with `status ∈ {Ready, Editing}`. Folded tasks
   (`status: Folded`, set by `aitask_fold_mark.sh` when marking) are
   excluded at scan time. So task A from the example never appears in the
   candidate list.
2. **Pre-fold validation via `aitask_fold_validate.sh`:** even if a Folded
   task somehow reached the fold step (e.g., raced with a concurrent fold),
   `aitask_fold_validate.sh` rejects it with `INVALID:<id>:status_Folded`
   (see `aitask_fold_validate.sh` status check). The create script must
   skip any such INVALID lines and proceed only with the VALID set.
3. **Transitive handling in `aitask_fold_mark.sh`:** when the user folds
   task B (which itself has `folded_tasks: [A]`) into new task C, the mark
   script re-points A's `folded_into` to C and adds A to C's `folded_tasks`
   as a transitive entry (deduped). Nothing re-folds A's content — the
   original merge into B already captured it, and that content is now part
   of C via the B→C body merge. Result: A, B, C form a single chain with C
   as the current primary.

**Note on `file_references` union across folds:** the frontmatter list
union is handled by t540_7 (below), which extends the fold-mark script to
merge the primary's and folded tasks' `file_references` entries (deduped,
preserving both paths and ranges). t540_3 just needs to trust that by the
time `aitask_fold_mark.sh` returns, the primary's `file_references` reflects
the full union.

Dependencies: **t540_1**. (Benefits from t540_7 but does not strictly
require it — t540_3 would still work with the body-only fold described in
t540_1, only the frontmatter union would be missing.)

### t540_4 — Codebrowser: "Create task from selection" action

- **New keybinding** in `codebrowser_app.py` `BINDINGS` (lines 130-143) —
  `c` → `action_create_task`. Confirm no collision with existing `g`, `e`,
  `t`, `r`, `d`, `D`, `h`, `H`, `tab`, `q` bindings.
- **`action_create_task()`** — read the currently focused file from
  `ProjectFileTree`, read line range from `CodeViewer.get_selected_range()`
  (returns 1-indexed `(start, end)` or `None`; when `None`, fall back to
  `_cursor_line + 1` as both start and end). Format as
  `<repo_relative_path>:<start>-<end>` (single line → `path:N`).
- **Launch pattern** — reuse the same subprocess launch the board uses at
  `aitask_board.py:3722-3741`. Build the command as
  `./.aitask-scripts/aitask_create.sh --file-ref <path>:<start>-<end>` and
  spawn it in the user's preferred terminal/tmux. Hoist the board's launcher
  helper into a shared location in `.aitask-scripts/lib/` if it isn't already,
  so both TUIs share the exact same spawn code path.
- **Post-completion refresh** — after the subprocess returns, call the
  codebrowser's annotation-refresh action (currently bound to `r`) so the new
  task shows up in the detail pane.

Dependencies: **t540_1**.

### t540_5 — Board: `FileReferencesField` widget + edit + codebrowser launch

- **New focusable field widget** `FileReferencesField` in
  `aitask_board.py`, modeled on `DependsField` (lines 915-976) /
  `ChildrenField` (lines 995-1034). Same focus + enter-handler shape.
- **Wire into `TaskDetailScreen.compose()`** (`aitask_board.py:1822-1914`):
  if `meta.get("file_references")` is non-empty, render the new field. The
  board's frontmatter parser (`task_yaml.py:69-90`) is dynamic, so the field
  is read "for free" — only the modal needs the new widget.
- **Per-entry enter action** — when a single `file_references` entry is
  focused (or picker-selected if multiple), call the new
  `launch_or_focus_codebrowser(session, entry)` helper from
  `agent_launch_utils.py` (added in t540_2). The focus handoff uses the
  env-var mechanism so an existing codebrowser window responds in-place.
- **Edit actions** — `add` and `remove` actions on the field call
  `aitask_update.sh --batch <task_id> --file-ref <value>` and
  `--remove-file-ref <value>` respectively (flags added in t540_1). Use the
  same `subprocess.run(..., "--silent")` idiom the board already uses at
  `aitask_board.py:4423-4426`.
- Manual verification: open `./ait board`, pick a task with
  `file_references`, enter the detail modal, focus the new field, press
  enter on an entry — confirm codebrowser opens (or existing window focuses)
  with the right file and line range.

Dependencies: **t540_1** (flags + field) and **t540_2** (focus mechanism +
launch helper).

### t540_7 — Union `file_references` across folded tasks during fold

Extends the existing fold machinery so that when task A (with
`file_references: ["foo.py:10-20"]`) is folded into task B (with
`file_references: ["foo.py:30-50", "bar.py"]`), B ends up with
`file_references: ["foo.py:30-50", "bar.py", "foo.py:10-20"]` — the
deduped union, preserving both paths and ranges. This keeps the structured
list accurate after fold, so the auto-merge find helper (t540_3) sees the
full picture on subsequent creations and the board's file_references
widget (t540_5) can navigate to every referenced range.

- **Where the union happens** — inside `aitask_fold_mark.sh`, not
  `aitask_fold_content.sh`. The mark script already touches the primary's
  frontmatter (setting `folded_tasks`), so extending it to also read each
  folded task's `file_references` and write the union to the primary keeps
  fold-mechanics cohesive and atomic with the fold commit.
- **Dedup semantics** — exact-string match on each list entry. Two entries
  `foo.py:10-20` and `foo.py:10-20` collapse; `foo.py:10-20` and
  `foo.py:30-50` are kept as distinct entries. Path-only entries
  (`foo.py`) and path+range entries (`foo.py:10-20`) are kept as distinct
  — we do not attempt range-merging in the first pass because range union
  semantics (contiguous vs disjoint, inclusive vs exclusive) are
  non-trivial and can be refined later.
- **Preserve order** — primary's existing entries first (order preserved),
  then each folded task's new entries appended in fold-argument order, then
  deduped by first occurrence.
- **Library helper** — add `union_file_references(primary_file, folded_file1
  ...)` to `.aitask-scripts/lib/task_utils.sh` (pair it with the
  `get_file_references()` helper from t540_1). Call it from
  `aitask_fold_mark.sh` as part of the primary-frontmatter-update step.
  The helper's output goes into the same in-memory frontmatter rewrite that
  already sets `folded_tasks`, so only one write occurs.
- **Transitive-fold interaction** — when B is folded into C and B's
  `folded_tasks: [A]` is transitively re-pointed to C, A's `file_references`
  entries must also be unioned into C (not only B's). The mark script
  already iterates transitive task files to update `folded_into`; extend
  that loop to also read `file_references` and feed them into the union.
- **New test** — `tests/test_fold_file_refs_union.sh`: set up primary with
  `file_references: [a.py:1-5]`, folded task with
  `file_references: [b.py, a.py:10-20]`, run the fold, assert the primary
  ends with `[a.py:1-5, b.py, a.py:10-20]` (exact ordering). Also cover
  the transitive case.
- **No regressions** — existing `tests/` fold tests (if any) must still
  pass. If `aitask_fold_mark.sh` is covered by an existing test, update it
  to account for the new field.

Dependencies: **t540_1** (needs `get_file_references()` helper and field
format). Independent of t540_2, t540_3, t540_4, t540_5, t540_6.

### t540_6 — "Use labels from previous task" option (independent QoL)

- **`last_used_labels` in userconfig** — new per-user field in
  `aitasks/metadata/userconfig.yaml`:
  ```yaml
  last_used_labels: [codebrowser, aitask-create]
  ```
  Gitignored with the rest of `userconfig.yaml`.
- **Library helpers** — `get_last_used_labels()` / `set_last_used_labels(csv)`
  in `.aitask-scripts/lib/task_utils.sh`, mirroring `get_user_email()` at
  lines 163-170. Same grep/sed pattern (no yq).
- **Interactive picker change** — in `get_labels_interactive()`
  (`aitask_create.sh:801-899`), if `last_used_labels` is non-empty, prepend
  an extra fzf option to the first iteration's menu:
  `>> Use labels from previous task (label1, label2)`. When selected, pre-fill
  `SELECTED_LABELS` with that list and continue the normal add-loop minus
  this option (don't present it again the rest of the session).
- **Persist on exit** — after `get_labels_interactive()` finalizes
  `SELECTED_LABELS`, call `set_last_used_labels "$SELECTED_LABELS"`.
- **New test** — `tests/test_last_used_labels.sh`: seed `userconfig.yaml`
  with `last_used_labels`, round-trip through the helpers, confirm the
  option appears only when non-empty.

Dependencies: none — can land in parallel with any other child.

## Dependency graph

```
t540_1 ─┬── t540_3  (t540_7 recommended to land first for best UX)
        ├── t540_4
        ├── t540_5 ──┐
        └── t540_7   │
                     │
t540_2 ──────────────┘

t540_6 (independent)
```

Natural implementation order: **1**, then **2** and **7** in parallel,
then **3, 4, 5**, then **6** any time. t540_7 before t540_3 means the
auto-merge flow lands with full frontmatter union from day one.

## Files affected

| File | Children |
|---|---|
| `.aitask-scripts/aitask_create.sh` | t540_1, t540_3, t540_6 |
| `.aitask-scripts/aitask_update.sh` | t540_1 |
| `.aitask-scripts/aitask_fold_mark.sh` | t540_7 |
| `.aitask-scripts/lib/task_utils.sh` | t540_1, t540_6, t540_7 |
| `.aitask-scripts/lib/agent_launch_utils.py` | t540_2, t540_4, t540_5 |
| `.aitask-scripts/aitask_find_by_file.sh` *(new)* | t540_1 |
| `.aitask-scripts/codebrowser/codebrowser_app.py` | t540_2, t540_4 |
| `.aitask-scripts/codebrowser/code_viewer.py` *(maybe)* | t540_2, t540_4 |
| `.aitask-scripts/aitask_codebrowser.sh` | t540_2 |
| `.aitask-scripts/board/aitask_board.py` | t540_5 |
| `tests/test_file_references.sh` *(new)* | t540_1 |
| `tests/test_fold_file_refs_union.sh` *(new)* | t540_7 |
| `tests/test_last_used_labels.sh` *(new)* | t540_6 |

## Verification (overall)

- `bash tests/test_file_references.sh` and `bash tests/test_last_used_labels.sh`
  pass.
- Regression spot-check: `bash tests/test_draft_finalize.sh` and
  `bash tests/test_archive_scan.sh`.
- `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh
  .aitask-scripts/aitask_find_by_file.sh .aitask-scripts/lib/task_utils.sh`
  clean.
- End-to-end cold path: open `./ait codebrowser`, select a file + line
  range, press `c`, finalize via the interactive create, confirm frontmatter
  has `file_references: ["<path>:<start>-<end>"]`, confirm the auto-merge
  prompt fires when another pending task already references that file.
- End-to-end hot path: open `./ait board`, pick a task with
  `file_references`, enter the detail modal, focus the file-references field,
  press enter — confirm an existing or newly-spawned codebrowser window lands
  on the right file with the right lines selected.

## Post-implementation

Standard `.aitask-scripts/aitask_archive.sh <child>` for each child as it
completes; parent t540 auto-archives when the last child is done (see Step 9
of task-workflow).
