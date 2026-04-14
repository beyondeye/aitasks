---
priority: medium
effort: medium
depends: [t540_1, t540_2]
issue_type: feature
status: Ready
labels: [aitask_board, codebrowser, tui]
created_at: 2026-04-14 10:15
updated_at: 2026-04-14 10:15
---

t540_5: teach the `ait board` task detail modal about the new
`file_references` frontmatter field. Add a focusable `FileReferencesField`
widget, wire edit/remove actions through `aitask_update.sh`, and on
enter-per-entry launch codebrowser with the referenced file and lines
focused (via the handoff mechanism from t540_2).

## Context

The board's `TaskDetailScreen` (`aitask_board.py:1765-1914`) renders
per-field widgets keyed on known frontmatter field names. The YAML
parser (`task_yaml.py:69-90`) is whitelist-free and reads all
metadata keys dynamically, but the detail modal's `compose()` only
renders a widget if the code knows about that field. Without this
task, `file_references` would exist in the file and be silently
ignored by the board.

## Depends on

- **t540_1** — needs the `file_references` field and the new
  `--file-ref` / `--remove-file-ref` flags on `aitask_update.sh`.
- **t540_2** — needs `launch_or_focus_codebrowser()` in
  `agent_launch_utils.py` and the `AITASK_CODEBROWSER_FOCUS`
  consumer in codebrowser_app.

## Design decisions (from parent plan)

- **Widget class:** `FileReferencesField` modeled on
  `DependsField` (`aitask_board.py:915-976`) /
  `ChildrenField` (`aitask_board.py:995-1034`). Same focus +
  `on_key(enter)` shape.
- **Multi-entry picker:** if the task has more than one file
  reference, pressing enter opens a `FileReferencePickerScreen`
  modal (modeled on `DependencyPickerScreen`) to choose which
  entry to navigate to. Single-entry case: enter navigates
  immediately.
- **Add/remove actions:** keybindings within the focused field
  (e.g., `a` for add, `d` or `x` for remove). The modal prompts
  for the new `path[:start-end]` string via a simple text input
  widget. Removal prompts for confirmation (this should match
  the existing remove-child UX in `ChildrenField`).
- **Backend updates:** both add and remove shell out to
  `./.aitask-scripts/aitask_update.sh --batch <task_id>
  --file-ref <value>` / `--remove-file-ref <value> --silent`
  via `subprocess.run`, mirroring the existing
  `aitask_board.py:4423-4426` pattern.
- **Navigate action:** enter on a single entry calls
  `launch_or_focus_codebrowser(session, entry)` from
  `agent_launch_utils.py`. The session name comes from the
  board's existing session-discovery helper (likely
  `os.environ.get("TMUX_SESSION")` or the board's
  `self.session_name`).

## Key files to modify

1. `.aitask-scripts/board/aitask_board.py`
   - New `FileReferencesField(Widget)` class next to
     `DependsField` / `ChildrenField`. Fields:
     - `file_refs: list[str]` — the entries from frontmatter
     - `on_key(enter)` → `_open_file_ref()` which either
       navigates immediately (single entry) or pushes
       `FileReferencePickerScreen`
     - `on_key("a")` / `on_key("d")` → add / remove handlers
   - New `FileReferencePickerScreen(ModalScreen)` modeled on
     `DependencyPickerScreen`. Dismisses with the selected
     entry, which the caller feeds to
     `launch_or_focus_codebrowser`.
   - Wire `FileReferencesField` into
     `TaskDetailScreen.compose()` (`aitask_board.py:1822-1914`):
     only render when `meta.get("file_references")` is non-empty.
     When empty, render a placeholder "Add file reference"
     button that opens the add-entry modal (so users can
     populate a task's file_references from the board).
   - Ensure the new field participates in the focus cycle the
     existing detail modal uses (tab order).

2. `.aitask-scripts/board/task_yaml.py` *(maybe)*
   - Parser is dynamic, so usually no change needed. Verify
     that a list of strings under `file_references` round-trips
     through `parse_frontmatter` and the serializer without
     losing brackets or quotes. If the serializer needs a nudge
     to emit the field in a specific position, adjust there.

## Reference files for patterns

- `aitask_board.py:915-976` (`DependsField`) — widget shape,
  focus, on_key handler, and the
  `DependencyPickerScreen`/`TaskDetailScreen` push pattern.
- `aitask_board.py:995-1034` (`ChildrenField`) — add/remove
  handler pattern with `subprocess.run` calls to
  `aitask_update.sh --batch`.
- `aitask_board.py:4423-4426` — subprocess invocation style for
  update script.
- `aitask_board.py:1765-1914` (`TaskDetailScreen.compose`) —
  where to wire the new widget.
- `.aitask-scripts/lib/agent_launch_utils.py`
  `launch_or_focus_codebrowser` (added in t540_2) — the handoff
  helper to call.

## Implementation plan

1. Add `FileReferencesField` widget class near
   `DependsField` / `ChildrenField`.
2. Add `FileReferencePickerScreen` if multi-entry selection is
   needed.
3. Wire the widget into `TaskDetailScreen.compose()`.
4. Implement the enter handler — launch codebrowser via
   `launch_or_focus_codebrowser`.
5. Implement the add action — prompt for input, call
   `aitask_update.sh --file-ref`.
6. Implement the remove action — confirm, call
   `aitask_update.sh --remove-file-ref`.
7. Manual verification with both zero-, one-, and multi-entry
   tasks.

## Verification

- Open `./ait board`, pick a task that already has
  `file_references`, enter its detail modal. Confirm the new
  field renders with each entry visible.
- Focus the field, press enter on a single entry —
  codebrowser opens (or existing window focuses) on that
  file+range.
- Focus the field with multiple entries, press enter — the
  picker modal opens, pick one, codebrowser focuses that
  entry.
- Add a new entry via the add action, confirm the task file
  on disk has the new entry (inspect frontmatter after exiting
  the board).
- Remove an entry via the remove action, confirm the task file
  no longer contains it.
- A task with no `file_references` shows a placeholder "Add"
  affordance; clicking it opens the add-entry modal and
  creates the field from scratch.

## Out of scope

- The codebrowser handoff consumer — t540_2.
- Creating tasks from the codebrowser — t540_4.
- Fold-time union of file_references — t540_7.
