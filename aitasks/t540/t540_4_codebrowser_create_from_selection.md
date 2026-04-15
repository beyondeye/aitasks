---
priority: medium
effort: medium
depends: [t540_1]
issue_type: feature
status: Implementing
labels: [codebrowser, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 10:14
updated_at: 2026-04-15 09:14
---

t540_4: add a `c` keybinding to `ait codebrowser` that spawns
interactive `aitask_create.sh` with `--file-ref <path>:<start>-<end>`
pre-supplied from the currently focused file and selection. This is
the primary user-facing feature of t540.

## Context

The parent task description is literally "identify a file in the ait
codebrowser TUI, select a line range and create an aitask that already
has in its context the file and the affected line-range". t540_1
provides the `--file-ref` flag; t540_4 wires the codebrowser up to use
it via the same subprocess launch pattern the board already uses for
`aitask_create.sh`.

## Depends on

- **t540_1** — needs the `--file-ref` flag on `aitask_create.sh`.

## Design decisions (from parent plan)

- **Spawn interactive mode, not batch.** The existing interactive
  create flow already collects labels, priority, description, etc.
  Replicating that inside the Textual TUI would duplicate significant
  code for little gain.
- **Launch pattern:** mirror the board's
  `aitask_board.py:3722-3741` `action_create_task` path — an
  `AgentCommandScreen` (or the equivalent terminal/tmux launcher)
  that runs `./.aitask-scripts/aitask_create.sh --file-ref
  <path>:<start>-<end>` in the user's preferred terminal/tmux.
- **Keybinding:** `c` — confirmed free in current codebrowser
  `BINDINGS` (existing: `q tab g e t r d D h H`). No collision.
- **Post-create refresh:** call the annotation-refresh action
  (currently bound to `r`) after the subprocess returns, so the
  new task's annotation shows up in the detail pane / gutter
  without a manual refresh.

## Key files to modify

1. `.aitask-scripts/codebrowser/codebrowser_app.py`
   - Add `Binding("c", "create_task", "Create Task")` to the
     `BINDINGS` class-level list (around lines 130-143).
   - Add `action_create_task()` method that:
     a. Reads the currently focused file path from
        `self.project_file_tree` (or wherever the current file is
        tracked — likely `CodeBrowserApp.current_file`).
     b. Reads the selection range from
        `self.code_viewer.get_selected_range()`. When it returns
        `None`, fall back to `code_viewer._cursor_line + 1` and
        use that single-line range (`path:N`).
     c. Converts the file path to a repo-relative form. If the
        codebrowser already has a `repo_root` / `relative_to` helper,
        use it; otherwise compute via `os.path.relpath(path,
        repo_root)`.
     d. Composes the argument string
        `<relpath>:<start>-<end>` (or `<relpath>:<start>` for
        single-line).
     e. Builds the full command:
        `./.aitask-scripts/aitask_create.sh --file-ref <arg>`.
     f. Launches it via the same subprocess/terminal helper the
        board uses. Hoist that helper into
        `.aitask-scripts/lib/agent_launch_utils.py` if it isn't
        already shared, so both TUIs call the same code path.
     g. On subprocess completion, schedule an annotation refresh
        (call `action_refresh_annotations` or whatever `r`'s
        handler is named).

2. `.aitask-scripts/lib/agent_launch_utils.py` *(potentially)*
   - If the board's `AgentCommandScreen`/terminal-launcher helper
     is still locked inside `aitask_board.py`, extract it here so
     both TUIs share it. Keep a thin wrapper in `aitask_board.py`
     that calls into this helper — do not break the existing board
     behavior.

## Reference files for patterns

- `.aitask-scripts/board/aitask_board.py` lines 3722-3741
  (`action_create_task`) — the subprocess-launch pattern to mirror.
- `.aitask-scripts/codebrowser/codebrowser_app.py`
  existing action handlers (e.g., `action_goto_line`,
  `action_explain`) — local idioms for `action_*` methods.
- `.aitask-scripts/codebrowser/code_viewer.py`
  `get_selected_range()` (around line 394), `move_cursor()`
  (around line 358), `_cursor_line`.

## Implementation plan

1. Locate the board's subprocess launcher and decide whether to
   hoist it. If yes: move it to `agent_launch_utils.py`, update the
   board to import from there, run the board to confirm no
   regression.
2. Add the `c` binding and `action_create_task` in
   `codebrowser_app.py`.
3. Implement the path + range extraction and command composition.
4. Wire the post-subprocess annotation refresh.
5. Manual smoke test.

## Verification

- Launch `./ait codebrowser`, navigate to a file,
  shift+down+down+down to select a multi-line range, press `c`.
  Expect: a terminal/tmux launches `aitask_create.sh` with the
  pre-supplied `--file-ref`. Walk through the interactive create
  (priority, effort, labels, etc.). On finalization, the task
  file's frontmatter contains `file_references:
  ["<path>:<start>-<end>"]`.
- Single-line case: press `c` without selecting a range. Expect
  `--file-ref <path>:<cursor_line>` and the resulting task has a
  single-line range in its frontmatter.
- Post-return refresh: the codebrowser's annotation gutter
  immediately shows the new task's annotation on the selected line
  range.
- Regression: pressing any existing keybinding
  (`q g e t r d D h H tab`) still behaves as before.

## Out of scope

- Fold detection / auto-merge — t540_3 (triggered automatically by
  the interactive create once `--file-ref` is present).
- Focus handoff the other direction (board → codebrowser) —
  t540_2 + t540_5.
