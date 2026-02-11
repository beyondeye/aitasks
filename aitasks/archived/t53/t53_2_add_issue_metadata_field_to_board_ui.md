---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [scripting, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 16:17
updated_at: 2026-02-10 19:20
completed_at: 2026-02-10 19:20
---

## Context

This is child task 2 of t53 (import GitHub issues as tasks). This task adds display and interaction support for the `issue` metadata field in the `aitask_board.py` Textual TUI application. The board uses `yaml.safe_load()` which already parses all YAML fields, so no changes to the Task class are needed. This task is independent of t53_1 (bash script changes).

The `issue` field stores a full URL (e.g., `https://github.com/owner/repo/issues/123`). The board needs to:
1. Show an indicator on the task card when an issue is linked
2. Display the full URL in the task detail view
3. Allow opening the issue in a browser (Enter key on the field)

## Key Files to Modify

1. **`aitask_board/aitask_board.py`** (~1,526 lines) - The main board application

## Reference Files for Patterns

- `aitask_board/aitask_board.py` line ~620: `ParentField` class - Follow this exact pattern for the new `IssueField` widget. It's a focusable `Static` widget with `on_key` handler and focus styling.
- `aitask_board/aitask_board.py` line ~481: `ReadOnlyField` class - Alternative simpler pattern
- `aitask_board/aitask_board.py` line ~306-355: `TaskCard.compose()` - Where to add the card indicator
- `aitask_board/aitask_board.py` line ~828-889: `TaskDetailScreen.compose()` - Where to add the detail view field

## Implementation Plan

### Step 1: Create IssueField widget class

Add a new `IssueField` class near the other field widgets (after `ParentField` at ~line 648). Follow the `ParentField` pattern:

```python
class IssueField(Static):
    """Focusable issue URL field. Press Enter to open in browser."""
    
    can_focus = True
    
    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url
    
    def render(self) -> str:
        return f"  [b]Issue:[/b] {self.url}"
    
    def on_key(self, event):
        if event.key == "enter":
            import webbrowser
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()
    
    def on_focus(self):
        self.add_class("ro-focused")
    
    def on_blur(self):
        self.remove_class("ro-focused")
```

### Step 2: Add to TaskDetailScreen.compose()

In the `TaskDetailScreen.compose()` method (around line 867), after the `assigned_to` field and before the timestamp fields, add:

```python
issue_url = meta.get("issue", "")
if issue_url:
    yield Label("  [b]Issue:[/b]")
    yield IssueField(issue_url, classes="meta-ro")
```

Or simply:
```python
if meta.get("issue"):
    yield IssueField(meta["issue"], classes="meta-ro")
```

### Step 3: Add indicator to TaskCard.compose()

In `TaskCard.compose()` (around line 328), after the labels display, add a compact indicator:

```python
issue = meta.get('issue', '')
if issue:
    # Add a compact "GH" or link icon indicator
    info_parts.append("[blue]GH[/blue]")
```

Look at how labels are displayed on the card and follow the same pattern for positioning.

## Verification Steps

1. Create a test task file manually with an `issue` field:
   ```yaml
   ---
   priority: medium
   effort: medium
   depends: []
   issue_type: feature
   status: Ready
   labels: [test]
   issue: https://github.com/test/repo/issues/1
   created_at: 2026-02-10 12:00
   updated_at: 2026-02-10 12:00
   boardcol: next
   boardidx: 10
   ---
   Test task with issue field
   ```
2. Run `./aitask_board.sh`
3. Verify the task card shows "GH" indicator
4. Press Enter on the task to open detail view
5. Verify the issue URL is displayed
6. Navigate to the IssueField and press Enter
7. Verify the browser opens with the correct URL
8. Clean up test task
