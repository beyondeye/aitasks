---
Task: t540_4_codebrowser_create_from_selection.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_2_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_4: codebrowser "create task from selection"

## Scope

Add a `c` keybinding to `ait codebrowser` that spawns interactive
`aitask_create.sh --file-ref <path>:<start>-<end>`, passing the
currently focused file and selected line range. This is the primary
user-facing feature of t540.

## Depends on

- **t540_1** — needs `--file-ref` flag on `aitask_create.sh`.

(Note: t540_4 does NOT depend on t540_2's focus mechanism — it
only *creates* a task from the codebrowser, it does not need to
*navigate* to a file. The navigation direction is t540_5.)

## Exploration results (from parent planning)

- **Codebrowser app entry:**
  `.aitask-scripts/codebrowser/codebrowser_app.py` —
  `CodeBrowserApp` class. `BINDINGS` at lines 130-143. Existing
  bindings: `q tab g e t r d D h H`. `c` is free.

- **Selection and cursor API (public):**
  `.aitask-scripts/codebrowser/code_viewer.py`:
  - `get_selected_range()` (~line 394) — returns `(start, end)`
    1-indexed inclusive or `None`.
  - `_cursor_line` (0-indexed) / `move_cursor()` (~line 358).
  - Fallback when no range: use `(cursor_line + 1, cursor_line + 1)`
    for a single-line ref.

- **Board subprocess-launch pattern to mirror:**
  `.aitask-scripts/board/aitask_board.py:3722-3741`
  (`action_create_task`). It builds a command, wraps it in
  `AgentCommandScreen`, and lets the user choose a
  terminal/tmux launch method. If that `AgentCommandScreen`
  helper is still locked inside `aitask_board.py`, hoist it into
  `.aitask-scripts/lib/agent_launch_utils.py` so both TUIs share
  one implementation (update `aitask_board.py` to import from
  the new location; verify no regression).

- **Repo-relative path:** the codebrowser already has a
  repo-root concept (used by `CodeViewer` for path display).
  Reuse whatever helper it uses — if none exists, compute via
  `os.path.relpath(abs_path, repo_root)` where `repo_root` is
  whatever the file tree uses as its root.

- **Post-completion refresh:** the `r` binding invokes an
  annotation-refresh action. After the spawned subprocess
  returns, call the same handler so the new task's annotation
  appears in the gutter immediately.

## Implementation sequence

1. (If needed) Extract the board's command-launch helper to
   `lib/agent_launch_utils.py`. Update
   `aitask_board.py` imports. Smoke-test board to confirm the
   existing action still works.
2. Add `Binding("c", "create_task", "Create Task")` to
   `CodeBrowserApp.BINDINGS`.
3. Implement `action_create_task()`:
   - Read the focused file path + selection.
   - Compute repo-relative path.
   - Build `--file-ref <rel>:<start>-<end>` argument (or
     `<rel>:<n>` for single line).
   - Launch via the shared helper with the full command.
   - On subprocess completion, call the annotation-refresh
     handler.
4. Manual smoke test.

## Verification

- Multi-line selection: open codebrowser, select lines 10-20 in
  a file, press `c`. A terminal/tmux launches interactive
  `aitask_create.sh`. Walk through the flow. Check that the
  resulting task file has
  `file_references: ["<relpath>:10-20"]`.
- Single-line (no selection): press `c` without selecting a
  range — command has `--file-ref <relpath>:<cursor_line>`.
- Post-return: annotation gutter shows the new task on the
  selected range without manual refresh.
- Keybindings `q g e t r d D h H tab` still behave normally.
- Board `action_create_task` (if launcher was hoisted) still
  opens `aitask_create.sh` exactly as before.

## Post-implementation

Archival via `./.aitask-scripts/aitask_archive.sh 540_4`.
