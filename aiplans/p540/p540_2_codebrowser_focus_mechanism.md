---
Task: t540_2_codebrowser_focus_mechanism.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Archived Sibling Plans: aiplans/archived/p540/p540_1_foundation_file_references_field.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_2: codebrowser focus mechanism (verified)

## Context

`ait codebrowser` has no programmatic way to be told "open this file at these
lines." Both cold-launch (CLI) and hot-handoff (already running) paths must be
supported so siblings t540_4 (create-from-selection) and t540_5 (board → jump)
can drive it without parsing magic. Mirrors minimonitor's `m` shortcut handoff
exactly.

## Verification result

The original plan was sound. Two corrections from reading current code:

1. **`.aitask-scripts/aitask_codebrowser.sh:36`** already exec's
   `"$PYTHON" "$SCRIPT_DIR/codebrowser/codebrowser_app.py" "$@"`. The `$@`
   forwarding is in place — implementation step 4 from the original plan is a
   **no-op**.
2. **Value format must accept t540_1's compact form.** Parent task description
   says `PATH[:START[-END]]` but `aiplans/archived/p540/p540_1_*.md` LOCKED the
   format to `PATH[:RANGE_SPEC]` where
   `RANGE_SPEC = N(-M)?(^N(-M)?)*`. For round-trip with t540_5/t540_3, the
   parser must accept compact multi-range entries. Codebrowser only displays a
   single contiguous selection, so multi-range collapses to outer span:
   `min(starts)..max(ends)`.

Anchors confirmed:
- `monitor/minimonitor_app.py:510` `action_switch_to_monitor` — the env-var +
  `tmux list-windows` + `select-window`/`new-window` handoff to mirror.
- `monitor/monitor_app.py:549` `_consume_focus_request` — the `tmux
  show-environment`/parse/return pattern. `_clear_focus_request` at L575
  (`set-environment -u`). Called from `_refresh_data` at L496 and the poll is
  registered in `on_mount`/`_start_monitoring` at L465 via
  `set_interval(self._refresh_seconds, self._refresh_data)`.
- `codebrowser/codebrowser_app.py:730-732` — bare `__name__ == "__main__"`
  block, no argparse, no `main()`. `_open_file_by_path` already exists at
  L639 and handles file load, tree selection, info-bar reset, and explain
  data — **reuse it** rather than reimplementing.
- `codebrowser/code_viewer.py`: `move_cursor` at L358 (0-indexed param,
  posts `CursorMoved`), `get_selected_range` at L394 (returns 1-indexed
  tuple), selection state `_selection_start` / `_selection_end` /
  `_selection_active` at L61-63, `extend_selection` at L371 (extends from
  current cursor — not directly usable for setting an arbitrary selection).
- `lib/agent_launch_utils.py`: `launch_in_tmux` at L162-211,
  `maybe_spawn_minimonitor` at L213-297, file ends at L333.

## Design

- **Env var:** `AITASK_CODEBROWSER_FOCUS`.
- **Value format (LOCKED):** `path` | `path:RANGE_SPEC` matching t540_1.
  Codebrowser parses → `(rel_path, start_line, end_line)`. Multi-range
  collapses to outer span. Single line `path:42` becomes `(p, 42, 42)`.
  Plain `path` becomes `(p, None, None)` → file opens at line 1, no
  selection.
- **Cold-launch path:** `--focus VALUE` CLI flag → argparse in new `main()` →
  `CodeBrowserApp(initial_focus=VALUE)` → consumed in `on_mount` before any
  env-var lookup.
- **Hot-handoff path:** session env var consumed in `on_mount` (after the
  CLI focus, if any) and via `set_interval(1.0, ...)` poll. Each consume
  unsets the var via `tmux set-environment -t <session> -u
  AITASK_CODEBROWSER_FOCUS` so it is one-shot.
- **Selection mechanism:** after `_open_file_by_path()` loads the file,
  set `code_viewer._cursor_line = end - 1`, `_selection_start = start - 1`,
  `_selection_end = end - 1`, `_selection_active = True`, then call
  `_ensure_viewport_contains_cursor()`, `_rebuild_display()`,
  `_scroll_cursor_visible()`, and `post_message(CursorMoved(end, total))`.
  This mirrors what `extend_selection` does at the end of its body — same
  state mutation, just with arbitrary endpoints. Single-line case:
  `start == end`, no selection set.
- **Tmux session detection:** mirror `monitor_app._detect_tmux_session`
  pattern (`tmux display-message -p '#S'`). Store as `self._tmux_session`
  on `__init__`. If `None` (not in tmux), the consumer is a no-op — the
  cold-launch CLI path still works.
- **Launcher helper:** new `launch_or_focus_codebrowser(session, focus_value,
  window_name="codebrowser")` in `lib/agent_launch_utils.py`, alongside
  `maybe_spawn_minimonitor`. Logic: set env var first → list windows →
  if `codebrowser` present, `select-window`; else `new-window` running
  `./ait codebrowser --focus <value>` (the `--focus` flag primes the cold
  launch so the new process doesn't have to wait for its first poll).
  Returns `(success: bool, error: str | None)` matching `launch_in_tmux`'s
  shape.

## Key files to modify

### 1. `.aitask-scripts/codebrowser/codebrowser_app.py`

- **`__init__`**: accept `initial_focus: str | None = None`; store on
  `self._initial_focus`. Detect tmux session via subprocess and store on
  `self._tmux_session: str | None`.

- **New helper `_parse_focus_value(value: str) -> tuple[str, int | None, int | None] | None`:**
  Strips leading/trailing whitespace. If empty → `None`. Splits on the
  first `:` → `(path, rest)`. If no rest → `(path, None, None)`.
  Otherwise: split `rest` on `^` into one or more `N` or `N-M` segments;
  parse each into `(start, end)`; collapse to
  `(min(all_starts), max(all_ends))`. Return `(path, start, end)`. On any
  parse failure, return `None` (and the caller logs/notifies).

- **New method `_consume_codebrowser_focus(self) -> str | None`:**
  Mirrors `monitor_app._consume_focus_request` lines 549-573 — runs
  `tmux show-environment -t <session> AITASK_CODEBROWSER_FOCUS`, parses
  the `KEY=value` line, returns the value or `None`. Returns `None` if
  `self._tmux_session` is `None`.

- **New method `_clear_codebrowser_focus(self) -> None`:**
  Mirrors `monitor_app._clear_focus_request` L575 — `tmux set-environment
  -t <session> -u AITASK_CODEBROWSER_FOCUS`. No-op if session is `None`.

- **New method `_apply_focus(self, focus_value: str) -> None`:**
  Calls `_parse_focus_value`. On parse failure: `self.notify(f"Invalid
  focus value: {focus_value}", severity="warning")` and return. Resolves
  the path to absolute (relative to `self._project_root`); if it does not
  exist, notify and return. Calls `self._open_file_by_path(rel_path)`
  (the existing helper at L639 — handles tree selection, viewer load,
  explain data, info bar). Then if `start` and `end` are not `None`,
  set the selection state on the `CodeViewer` directly:
  ```python
  code_viewer = self.query_one("#code_viewer", CodeViewer)
  code_viewer._cursor_line = end - 1
  if start != end:
      code_viewer._selection_start = start - 1
      code_viewer._selection_end = end - 1
      code_viewer._selection_active = True
  code_viewer._ensure_viewport_contains_cursor()
  code_viewer._rebuild_display()
  code_viewer._scroll_cursor_visible()
  code_viewer.post_message(
      code_viewer.CursorMoved(end, code_viewer._total_lines)
  )
  ```

- **New method `_consume_and_apply_focus(self) -> None`:**
  Calls `_consume_codebrowser_focus`. If a value is returned, calls
  `_clear_codebrowser_focus()` (one-shot) and then `_apply_focus(value)`.
  This is what the `set_interval` poll calls.

- **`on_mount` hook:** add a new `on_mount` method on `CodeBrowserApp`
  (none currently exists at the App level; the file_tree's
  `on_directory_tree_directory_selected` is unrelated). It should:
  1. If `self._initial_focus` is set, call
     `self._apply_focus(self._initial_focus)` and clear it. Use
     `self.call_after_refresh(...)` so the file tree is mounted first.
  2. Then call `self._consume_and_apply_focus()` (in case a hot focus
     came in between launch and mount).
  3. Register `self.set_interval(1.0, self._consume_and_apply_focus)`.

- **New `main()`:** at module bottom, add:
  ```python
  def main() -> None:
      import argparse
      parser = argparse.ArgumentParser(prog="codebrowser")
      parser.add_argument(
          "--focus",
          metavar="PATH[:RANGE_SPEC]",
          default=None,
          help="Open the codebrowser focused on PATH at the given line range. "
               "RANGE_SPEC is N, N-M, or N-M^K-L (multi-range collapses to outer span). "
               "Also consumable via the AITASK_CODEBROWSER_FOCUS tmux session env var.",
      )
      args = parser.parse_args()
      app = CodeBrowserApp(initial_focus=args.focus)
      app.run()

  if __name__ == "__main__":
      main()
  ```
  Replace the existing 2-line `__main__` block (L730-732) with this. The
  existing `./ait codebrowser` invocation (no args) still works because
  `--focus` defaults to `None`.

- **Module docstring:** add a short note documenting
  `AITASK_CODEBROWSER_FOCUS` and `--focus` (the file currently has no
  module docstring; add one).

### 2. `.aitask-scripts/aitask_codebrowser.sh`

**No change.** L36 already passes `"$@"` to the python entry point.

### 3. `.aitask-scripts/lib/agent_launch_utils.py`

Add new function after `maybe_spawn_minimonitor` (after L297, before
`load_tmux_defaults` at L300):

```python
def launch_or_focus_codebrowser(
    session: str,
    focus_value: str,
    window_name: str = "codebrowser",
) -> tuple[bool, str | None]:
    """Set the focus env var and bring the codebrowser to the given range.

    If a window named *window_name* already exists in *session*, selects
    it; otherwise creates a new window running ``./ait codebrowser --focus
    <focus_value>``. The env var is set first so both reuse and
    cold-launch paths see it.

    Returns ``(success, error_message)``. On success, error_message is
    ``None``.
    """
    # 1. Set env var first (covers both reuse and cold-launch paths).
    try:
        result = subprocess.run(
            ["tmux", "set-environment", "-t", session,
             "AITASK_CODEBROWSER_FOCUS", focus_value],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return False, "tmux set-environment failed"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"tmux set-environment error: {e}"

    # 2. Does the codebrowser window already exist?
    try:
        lw = subprocess.run(
            ["tmux", "list-windows", "-t", session,
             "-F", "#{window_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if lw.returncode != 0:
            return False, "tmux list-windows failed"
        names = lw.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"tmux list-windows error: {e}"

    try:
        if window_name in names:
            sel = subprocess.run(
                ["tmux", "select-window", "-t",
                 f"{session}:{window_name}"],
                capture_output=True, timeout=5,
            )
            if sel.returncode != 0:
                return False, "tmux select-window failed"
        else:
            nw = subprocess.run(
                ["tmux", "new-window", "-t", f"{session}:",
                 "-n", window_name,
                 "./ait", "codebrowser", "--focus", focus_value],
                capture_output=True, timeout=5,
            )
            if nw.returncode != 0:
                return False, "tmux new-window failed"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"tmux switch error: {e}"

    return True, None
```

Note: `subprocess` is already imported at L17.

## Implementation sequence

1. Add `_parse_focus_value`, `_consume_codebrowser_focus`,
   `_clear_codebrowser_focus`, `_apply_focus`,
   `_consume_and_apply_focus`, and `on_mount` to `CodeBrowserApp` in
   `codebrowser_app.py`. Extend `__init__` for `initial_focus` and
   `_tmux_session` detection.
2. Replace the `__main__` block with `main()` + argparse.
3. Add module docstring documenting `--focus` / env var.
4. Add `launch_or_focus_codebrowser` to `agent_launch_utils.py`.
5. Manual smoke test all four paths (Verification below).
6. (No shellcheck — no shell scripts changed.) Quick syntax check via
   `python -c "import ast; ast.parse(open('...').read())"` on the two
   modified `.py` files.

## Verification

- **No-arg launch (regression):**
  ```bash
  ./ait codebrowser
  ```
  Plain TUI launches as before, no errors.

- **Cold CLI:**
  ```bash
  ./ait codebrowser --focus .aitask-scripts/aitask_create.sh:100-150
  ```
  Opens with `aitask_create.sh` selected in the tree, viewer scrolled to
  the range, and lines 100-150 highlighted as a selection. Cursor info
  bar shows `Sel 100-150`.

- **Compact multi-range form (forward compat with t540_1):**
  ```bash
  ./ait codebrowser --focus .aitask-scripts/aitask_create.sh:50-60^120-130
  ```
  Lands on the outer span 50-130 (selection collapses for display).

- **Single-line:**
  ```bash
  ./ait codebrowser --focus .aitask-scripts/aitask_create.sh:42
  ```
  Cursor at line 42, no selection.

- **Path-only:**
  ```bash
  ./ait codebrowser --focus README.md
  ```
  README opens at line 1, no selection.

- **Hot env-var (run codebrowser in one tmux window, then in another shell):**
  ```bash
  tmux set-environment -t aitasks AITASK_CODEBROWSER_FOCUS \
      tests/test_terminal_compat.sh:10-20
  ```
  The running codebrowser jumps to that range within ~1s. The env var is
  cleared after consume — running `tmux show-environment -t aitasks
  AITASK_CODEBROWSER_FOCUS` should report it as unset.

- **Window-reuse via helper (from a third python shell):**
  ```python
  import sys
  sys.path.insert(0, ".aitask-scripts/lib")
  from agent_launch_utils import launch_or_focus_codebrowser
  ok, err = launch_or_focus_codebrowser(
      "aitasks",
      "aiplans/p540/p540_2_codebrowser_focus_mechanism.md:1-10",
  )
  print(ok, err)
  ```
  Existing codebrowser window comes to the foreground and lands on the
  range. Calling the helper a second time with a different range
  re-focuses the same window.

- **Cold launch via helper (no codebrowser window present):**
  After `tmux kill-window -t aitasks:codebrowser`, re-run the helper
  call above — a new `codebrowser` window is created and lands on the
  range.

- **Invalid focus value:**
  ```bash
  ./ait codebrowser --focus "nonexistent.py:abc"
  ```
  Codebrowser launches normally and shows a notify warning "Invalid
  focus value: nonexistent.py:abc" — does not crash.

## Out of scope

- The actual "create task from selection" keybinding inside codebrowser →
  t540_4.
- The board `FileReferencesField` widget that calls
  `launch_or_focus_codebrowser` → t540_5.
- Range-union normalization of compact multi-range entries → deliberately
  deferred per t540_1's locked design.

## Post-implementation

Standard archival per task-workflow Step 9:
```bash
./.aitask-scripts/aitask_archive.sh 540_2
```

The archived plan will serve as the primary reference for t540_4 (which
will call `_open_file_by_path` and the focus helpers), and for t540_5
(which will call `launch_or_focus_codebrowser` from the board). Final
Implementation Notes must capture: the exact CodeViewer selection-state
mutation pattern, any deviations in tmux session detection, and any
issues with the `set_interval` poll cadence.
