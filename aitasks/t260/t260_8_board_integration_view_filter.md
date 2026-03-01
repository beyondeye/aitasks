---
priority: medium
effort: medium
depends: [t260_7]
issue_type: feature
status: Ready
labels: [python_tui]
created_at: 2026-03-01 18:11
updated_at: 2026-03-01 18:11
---

## Context

This is child task 8 of the "Create aitasks from Pull Requests" feature (t260). The aitasks framework now has several metadata fields linking tasks to external platforms: `issue:` (linking to GitHub/GitLab/Bitbucket issues) and `pull_request:` + `contributor:` + `contributor_email:` (linking to PRs). Users managing both an aitask-based workflow and a GitHub/GitLab workflow in parallel need a way to quickly see which tasks are connected to external platform items.

**Why this task is needed:** Currently, the board has no filter mechanism beyond full-text search. When managing external contributions and issue-linked tasks, users need to quickly identify and browse only the tasks connected to GitHub/GitLab items, with the external links prominently displayed. This also provides the opportunity to ensure that all URL fields (issue, pull_request) are fully clickable/openable in the task detail dialog.

**Depends on:** t260_2 (board TUI PR display must exist first)

## Key Files to Modify

1. **`aiscripts/board/aitask_board.py`** (~2400 lines) — Main board application
   - Add new filter state and keybinding for "Integration view"
   - Create `IntegrationFilterScreen` modal or toggle-based filter
   - Extend `apply_filter()` to handle integration filter
   - Ensure both `IssueField` and `PullRequestField` are clickable in detail dialog

2. **`aitasks/metadata/board_config.json`** — May need filter persistence in settings

## Reference Files for Patterns

### Existing Filter Infrastructure
- **`aitask_board.py` lines 2484-2496** — `apply_filter()` method: iterates `TaskCard` widgets, toggles `card.styles.display` based on `self.search_filter`. New filters should extend this method.
- **`aitask_board.py` lines 2361** — `self.search_filter` attribute in `KanbanApp.__init__()`. Add `self.integration_filter_active = False` here.
- **`aitask_board.py` lines 2323-2356** — `BINDINGS` list. Add new keybinding here (e.g., `Binding("g", "toggle_integration_view", "Git View")`).
- **`aitask_board.py` lines 2365-2388** — `check_action()` method for conditional footer display.

### IssueField (Already Clickable)
- **`aitask_board.py` lines 1026-1046** — `IssueField(Static)` class. Already has `can_focus = True`, `on_key()` with Enter handling via `webbrowser.open()`, and render hint `(Enter to open)`. This is the pattern to replicate for `PullRequestField`.

### Task Card Display
- **`aitask_board.py` lines 541-625** — `TaskCard.compose()`. Shows how issue indicator (`_issue_indicator()`) is displayed. After t260_2, PR indicator (`_pr_indicator()`) will also be here.

### Board Config & Persistence
- **`aitask_board.py` lines 204-226** — `TaskManager.load_metadata()`. Uses `load_layered_config()` with defaults. Settings stored in `board_config.json` under `settings` key (user-local, persisted in `.local.json`).
- **`aitask_board.py` lines 402-421** — Column collapse as example of toggleable persistent view state.

### Modal Dialog Pattern
- **`aitask_board.py` lines 1435+** — `TaskDetailScreen` as example of modal pushed via `push_screen()`.

## Implementation Plan

### 1. Add integration filter state to `KanbanApp.__init__()`

```python
self.integration_filter_active = False
```

### 2. Add keybinding

In `BINDINGS` list:
```python
Binding("g", "toggle_integration_view", "Git View"),
```

The "g" key is a good mnemonic for "Git/GitHub view". Alternative: "i" for "Integration view".

### 3. Implement `action_toggle_integration_view()`

```python
def action_toggle_integration_view(self):
    """Toggle the integration view filter showing only tasks linked to issues/PRs."""
    self.integration_filter_active = not self.integration_filter_active
    self.apply_filter()
    if self.integration_filter_active:
        self.notify("Integration view: showing tasks linked to issues/PRs", severity="information")
    else:
        self.notify("Integration view: off — showing all tasks", severity="information")
```

### 4. Extend `apply_filter()` method

The current `apply_filter()` only checks `self.search_filter`. Extend it:

```python
def apply_filter(self):
    for card in self.query("TaskCard"):
        visible = True
        
        # Search filter (existing)
        if self.search_filter:
            searchable = f"{card.task_data.filename} {card.task_data.metadata}".lower()
            if self.search_filter not in searchable:
                visible = False
        
        # Integration filter (new)
        if visible and self.integration_filter_active:
            meta = card.task_data.metadata
            has_issue = bool(meta.get("issue", ""))
            has_pr = bool(meta.get("pull_request", ""))
            if not (has_issue or has_pr):
                visible = False
        
        card.styles.display = "block" if visible else "none"
```

### 5. Visual indicator when integration view is active

When the filter is active, provide visual feedback:
- Option A: Change the search box placeholder to indicate filter is active: `"🔗 Integration view active — showing issue/PR-linked tasks only (press 'g' to toggle)"`
- Option B: Add a status indicator in the header or a small label below search box
- Option C: Use Textual's `notify()` (already in step 3) plus change footer binding label to show state: `"Git View ✓"` when active

Recommended: Combine Option A (placeholder change) + Option C (footer label change):

```python
def _update_filter_ui(self):
    search_box = self.query_one("#search_box", Input)
    if self.integration_filter_active:
        search_box.placeholder = "🔗 Integration view — issues/PRs only (g to toggle, Tab to search)"
    else:
        search_box.placeholder = "Search tasks... (Tab to focus, Esc to return to board)"
```

### 6. Enhanced card display in integration view

When integration view is active, make the linked URLs more prominent on the task cards. In `TaskCard.compose()`, check if the integration view is active and show the full URL (or a truncated version) directly on the card, not just the badge:

```python
# In TaskCard.compose() — when integration view is active:
if app.integration_filter_active:
    issue_url = meta.get("issue", "")
    pr_url = meta.get("pull_request", "")
    if issue_url:
        info.append(f"[dim]Issue: {issue_url}[/dim]")
    if pr_url:
        info.append(f"[dim]PR: {pr_url}[/dim]")
```

### 7. Ensure PullRequestField is clickable in detail dialog

After t260_2 adds `PullRequestField`, verify it follows the same pattern as `IssueField`:
- `can_focus = True`
- `on_key()` handler with `event.key == "enter"` → `webbrowser.open(self.url)`
- Render hint: `(Enter to open)`
- Focus styling via `.ro-focused` class

If t260_2 didn't implement this fully, complete it here. The `IssueField` at line 1026 is the exact pattern:

```python
class PullRequestField(Static):
    can_focus = True
    
    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url
    
    def render(self) -> str:
        indicator = _pr_indicator(self.url)
        return f"  [b]Pull Request:[/b] {indicator} {self.url}  [dim](Enter to open)[/dim]"
    
    def on_key(self, event):
        if event.key == "enter":
            import webbrowser
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()
    
    def on_focus(self):
        self.add_class("ro-focused")
```

### 8. Optional: Persist filter state in board_config settings

Store the integration view state so it persists across board restarts:

```python
# In action_toggle_integration_view:
self.manager.settings["integration_view_active"] = self.integration_filter_active
self.manager.save_metadata()

# In __init__ or on_mount:
self.integration_filter_active = self.manager.settings.get("integration_view_active", False)
```

### 9. Update `check_action()` for conditional footer display

```python
def check_action(self, action: str, parameters) -> bool | None:
    if action == "toggle_integration_view":
        return True  # Always show in footer
    # ... existing checks ...
```

## Verification Steps

1. **Test filter toggle:**
   - Create tasks with and without `issue:` / `pull_request:` metadata
   - Run `./ait board`
   - Press `g` to activate integration view
   - Verify only tasks with issue/PR metadata are shown
   - Press `g` again to deactivate — all tasks visible again

2. **Test with search filter combination:**
   - Activate integration view (`g`)
   - Type in search box — verify both filters work together (intersection)
   - Clear search — verify integration filter still applies

3. **Test clickable fields in detail dialog:**
   - Open a task with `issue:` field — press Enter on IssueField — browser opens
   - Open a task with `pull_request:` field — press Enter on PullRequestField — browser opens

4. **Test visual feedback:**
   - When integration view is active, verify placeholder text changes
   - Verify footer shows "Git View" binding

5. **Test persistence (if implemented):**
   - Activate integration view, close board, reopen — verify view state persists

6. **Test with no integration tasks:**
   - Activate integration view when no tasks have issue/PR metadata
   - Verify board shows empty columns (or a helpful message)
