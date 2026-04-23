---
priority: high
effort: medium
depends: [t573_2]
issue_type: feature
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 11:01
updated_at: 2026-04-23 12:35
---

## Context

Surfaces the import flow in the brainstorm TUI. Without this child, users
can only use the feature from the CLI (t573_2). Depends on t573_1
(for `apply_initializer_output`) and t573_2 (for the CLI flag the TUI
shells out to).

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — extend
  `InitSessionModal`, add a new `ImportProposalFilePicker` modal, and
  rework `_on_init_result` / `_run_init` to handle the import path and
  poll for agent completion.

## Reference Files for Patterns

- `InitSessionModal` — `brainstorm_app.py:171-199` — extend to a
  three-button layout returning
  `"blank" | "import:<abs_path>" | None`.
- Existing modal with a DirectoryTree — pattern in
  `.aitask-scripts/codebrowser/file_tree.py:67` (`ProjectFileTree`)
  and its usage in `.aitask-scripts/codebrowser/codebrowser_app.py`.
  Textual's `DirectoryTree` is the base class.
- `_run_init` — `brainstorm_app.py:3050-3065` — the current
  subprocess-based init path; the import path extends this with a
  `--proposal-file` arg and a post-init polling loop.
- `list_agent_files` / status polling —
  `.aitask-scripts/agentcrew/agentcrew_utils.py` (reused in
  `_refresh_status_tab` at `brainstorm_app.py:1745`).
- Textual `set_interval` usage —
  `brainstorm_app.py:1738` (`_status_refresh_timer`).

## Implementation Plan

1. **`InitSessionModal` (three buttons):** replace the two-button row
   with:
   - `Button("Initialize Blank", variant="default", id="btn_init_blank")`
   - `Button("Import Proposal…", variant="primary", id="btn_init_import")`
   - `Button("Cancel", variant="default", id="btn_cancel")`
   Update `@on(Button.Pressed, ...)` handlers; the import button pushes
   `ImportProposalFilePicker` and awaits its dismissed value, then
   dismisses `InitSessionModal` with `f"import:{abs_path}"`. The
   blank button dismisses with `"blank"`. Cancel → `None`.

2. **`ImportProposalFilePicker(ModalScreen)`:**
   - BINDINGS: `escape` → cancel.
   - Composition: header "Select a markdown file for initial proposal",
     Textual `DirectoryTree(".")`, footer with "↵ select  esc cancel".
   - Filter to markdown files only: override `filter_paths()` to
     `[p for p in paths if p.is_dir() or p.suffix.lower() in (".md", ".markdown")]`.
   - `on_directory_tree_file_selected` → `self.dismiss(str(event.path.resolve()))`.
   - `action_cancel` → `self.dismiss(None)`.

3. **`_on_init_result` branching:** replace the single boolean handler
   with a three-way branch:
   ```python
   def _on_init_result(self, result: str | None) -> None:
       if result is None:
           self.exit()
       elif result == "blank":
           self._run_init()   # unchanged path
       elif result.startswith("import:"):
           path = result[len("import:"):]
           self._run_init_with_proposal(path)
   ```

4. **`_run_init_with_proposal(self, path)`:**
   - `@work(thread=True)` — shells to `ait brainstorm init <task> --proposal-file <path>`.
   - If returncode != 0 → notify severity=error and `self.exit()`.
   - On success: parse `INITIALIZER_AGENT:<name>` from stdout to store
     the agent name (default `initializer_bootstrap`).
   - Call `call_from_thread` to set up a polling timer via
     `set_interval(2, self._poll_initializer)`; initial state shows a
     Label "Waiting for initializer agent…" over the (still-hidden)
     DAG pane.

5. **`_poll_initializer(self)`:**
   - Read `<crew_worktree>/initializer_bootstrap_status.yaml` —
     or use `list_agent_files` / existing status helpers.
   - If status is `Completed`:
     - cancel the timer.
     - Call `apply_initializer_output(self.task_num)`.
     - Call `_load_existing_session()` to refresh the UI.
     - Notify "Initial proposal imported".
   - If status is `Error` / `Aborted`:
     - cancel the timer.
     - Notify severity=error with the failure.
     - Call `_load_existing_session()` — the placeholder n000_init
       remains, so the TUI is still usable and the user can retry.
   - Else: keep polling.

6. **Graceful fallback if tmux unavailable:** the underlying agent
   launch already degrades to headless via `is_tmux_available()`
   (see `brainstorm_app.py:67`). The polling logic in step 5 handles
   both cases identically — no extra code needed in this task.

## Verification

- Fresh task with no existing session:
  - `ait brainstorm <N>` → modal shows three buttons.
  - "Initialize Blank" → behaves exactly as today (existing regression
    test: the DAG pane shows `n000_init` with the task-file body).
  - "Import Proposal…" → file-picker opens, only `.md` / `.markdown`
    files + directories are enumerable, selection returns an absolute
    path, the TUI then shows a waiting indicator until the agent
    completes. After completion the DAG pane shows the reformatted
    `n000_init` with visible dimensions in the node detail pane.
  - "Cancel" in the main modal → TUI exits cleanly.
  - `escape` in the file-picker → returns to the main modal (does
    NOT exit the TUI entirely).
- Imported source file is byte-for-byte unchanged after the flow
  (check `md5sum` / `stat` before vs. after).
- Error path: simulate a malformed agent output (truncated output
  file) → TUI notifies "Initializer agent failed" and falls back
  to the placeholder n000_init without crashing.
- No tmux environment (e.g., `TMUX=`): the flow still completes via
  headless fallback; the polling loop still observes `Completed`.
