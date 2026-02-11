---
Task: t53_2_add_issue_metadata_field_to_board_ui.md
Parent Task: aitasks/t53_import_gh_issue_as_task.md
Sibling Tasks: aitasks/t53/t53_4_*.md, aitasks/t53/t53_5_*.md
Archived Sibling Plans: aiplans/archived/p53/p53_*_*.md
Branch: main
Base branch: main
---

# Plan: Add `issue` metadata field to board UI (t53_2)

## Context

The `issue` field (a full GitHub URL like `https://github.com/owner/repo/issues/123`) was added to task YAML frontmatter in t53_1. The `aitask_board.py` TUI already parses it via `yaml.safe_load()`, but doesn't display it. This task adds:
1. A compact indicator on task cards
2. A focusable field in the detail view that opens the URL in a browser on Enter

## File to Modify

- `aitask_board/aitask_board.py` (~1,526 lines)

## Implementation Steps

### Step 1: Create `IssueField` widget class (~line 649, after `ParentField`)

Follow the `ParentField` pattern (lines 620-648):

```python
class IssueField(Static):
    """Focusable issue URL field. Press Enter to open in browser."""

    can_focus = True

    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def render(self) -> str:
        return f"  [b]Issue:[/b] [link={self.url}]{self.url}[/link]"

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

### Step 2: Add `IssueField` to `TaskDetailScreen.compose()` (~line 868)

Insert after `assigned_to` field and before the timestamps section:

```python
if meta.get("issue"):
    yield IssueField(meta["issue"], classes="meta-ro")
```

### Step 3: Add platform-aware issue indicator to `TaskCard.compose()` (~line 325)

Add a helper function that detects the platform from the issue URL hostname and returns an appropriate short label:

```python
def _issue_indicator(url: str) -> str:
    """Return a short colored indicator based on issue URL platform."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if "github" in host:
        return "[blue]GH[/blue]"
    elif "gitlab" in host:
        return "[#e24329]GL[/e24329]"
    elif "bitbucket" in host:
        return "[blue]BB[/blue]"
    return "[blue]Issue[/blue]"
```

In the info-building section, after labels, add:

```python
issue = meta.get('issue', '')
if issue:
    info.append(_issue_indicator(issue))
```

## Verification

1. Run `./aitask_board.sh`
2. Find a task with an `issue` field (or temporarily add one to a test task)
3. Verify the card shows "GH" indicator in blue
4. Open the task detail — verify the issue URL is displayed
5. Focus the IssueField and press Enter — verify browser opens the URL

## Final Implementation Notes
- **Actual work done:** Implemented all 3 steps as planned: `IssueField` widget, detail view integration, and platform-aware card indicator with `_issue_indicator()` helper.
- **Deviations from plan:** The `[link=URL]` Rich markup syntax in `IssueField.render()` caused a `MarkupError` because URLs contain `:` and `/` characters that break Rich's markup parser. Replaced with plain text URL display plus a dim `(Enter to open)` hint.
- **Issues encountered:** Rich markup `[link=URL]` is incompatible with URLs in Textual Static widgets. The `ParentField` pattern (plain text + Enter key action) is the correct approach.
- **Key decisions:** Used `urlparse` for platform detection to be robust against subdomains (e.g., `enterprise.github.com`). Added GitLab (orange `GL`) and Bitbucket (blue `BB`) indicators alongside GitHub (`GH`), with generic `Issue` fallback.
- **Notes for sibling tasks:**
  - `_issue_indicator()` is a module-level function near top of file — can be reused if other views need platform detection
  - Rich markup `[link=URL]` does NOT work in Textual widgets — avoid using it for URLs
  - The `issue` field from YAML is available via `meta.get("issue")` with no special parsing needed (yaml.safe_load handles it)

## Post-Implementation

Follow Step 9 of aitask-pick workflow for archival.
