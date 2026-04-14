---
Task: t540_5_board_file_references_field.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_2_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_5: board `FileReferencesField` widget

## Scope

Teach the `ait board` task-detail modal about the new
`file_references` frontmatter field. Add a focusable widget, wire
edit/remove actions through `aitask_update.sh`, and on enter-per-entry
launch codebrowser (via t540_2's focus mechanism) with the referenced
file + lines in focus.

## Depends on

- **t540_1** — needs `file_references` field +
  `aitask_update.sh --file-ref` / `--remove-file-ref` flags.
- **t540_2** — needs
  `launch_or_focus_codebrowser(session, focus_value)` in
  `lib/agent_launch_utils.py` and the codebrowser consumer.

## Exploration results (from parent planning)

- **`TaskDetailScreen`:** `.aitask-scripts/board/aitask_board.py:1765-1914`
  (ModalScreen). `compose()` at ~1822-1914 renders per-field
  widgets keyed on known field names. Parser
  (`board/task_yaml.py:69-90`) is whitelist-free, so a new field
  is read automatically — only `compose()` needs the new widget.

- **Widget class patterns to mirror:**
  - `DependsField` at `aitask_board.py:915-976` — focusable field
    with `on_key(enter)` → `_open_dep()` which either pushes a
    `TaskDetailScreen` (single) or a `DependencyPickerScreen`
    (multi).
  - `ChildrenField` at `aitask_board.py:995-1034` — add/remove
    handler pattern with `subprocess.run` calls to
    `aitask_update.sh --batch`.

- **Subprocess invocation idiom:**
  `aitask_board.py:4423-4426` uses
  `subprocess.run(["./.aitask-scripts/aitask_update.sh",
  "--batch", parent_num, "--remove-child", child_id, "--silent"],
  capture_output=True, text=True, timeout=10)`. Use this exact
  idiom for add/remove.

- **Session name discovery:** reuse whatever the board already
  uses (there's a session discovery pattern already in use for
  `launch_in_tmux` calls — trace from the existing board
  `maybe_spawn_minimonitor` usage around `action_create_task`
  /`action_pick`).

## Design

- **`FileReferencesField(Widget)`** — new class near
  `DependsField`:
  - Props: `file_refs: list[str]` from metadata.
  - `on_key("enter")` → `_open_file_ref()`:
    - 0 entries: no-op (or trigger add).
    - 1 entry: call
      `launch_or_focus_codebrowser(session, entry)`.
    - ≥2 entries: push `FileReferencePickerScreen`, on selection
      call the same launcher.
  - `on_key("a")` → add entry via input modal, then
    `aitask_update.sh --batch <task_id> --file-ref <value>
    --silent`. Refresh metadata after.
  - `on_key("d")` (or `"x"`) → confirm modal, then
    `aitask_update.sh --batch <task_id> --remove-file-ref
    <value> --silent`. Refresh.

- **`FileReferencePickerScreen(ModalScreen)`** — model on
  `DependencyPickerScreen`. Shows each entry as a row, dismisses
  with the chosen string.

- **Compose wiring** (`TaskDetailScreen.compose`):
  - Always yield the field: when `meta.get("file_references")` is
    non-empty, pass the list; when empty, pass `[]` and the
    widget renders an "Add file reference" placeholder so the
    field can be populated from the board (this is useful for
    tasks the user didn't originally create with file refs).

## Implementation sequence

1. Add `FileReferencesField` class near `DependsField`.
2. Add `FileReferencePickerScreen` (only needed if multi-entry
   UX diverges from the single-entry flow).
3. Wire the widget into `TaskDetailScreen.compose()`.
4. Implement enter-launch handler that calls
   `launch_or_focus_codebrowser`.
5. Implement add/remove handlers via `subprocess.run` to
   `aitask_update.sh`.
6. Ensure focus cycle (tab order) includes the new widget.
7. Manual verification for zero/one/multi-entry tasks.

## Verification

- Open `./ait board`, pick a task with
  `file_references: [foo.py:10-20, bar.py]`, enter detail
  modal → the new field renders, focusable.
- Press enter on a single-entry field → codebrowser focuses
  (or spawns) with the right file+range.
- Press enter on a multi-entry field → picker modal, select an
  entry, codebrowser focuses that one.
- Add action: enter a new ref via the modal, confirm the task
  file on disk gains the entry.
- Remove action: remove an entry, confirm the task file on
  disk loses it.
- Empty-state placeholder: pick a task with no `file_references`
  — the placeholder "Add file reference" affordance opens the
  add modal and creates the field fresh.

## Post-implementation

Archival via `./.aitask-scripts/aitask_archive.sh 540_5`.
