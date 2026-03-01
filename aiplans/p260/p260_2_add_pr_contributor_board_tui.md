---
Task: t260_2_add_pr_contributor_board_tui.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md, aitasks/t260/t260_3_*.md through t260_7_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Add PR/Contributor Display to Board TUI (t260_2)

## Overview

Add visual indicators for PR-originated tasks in the Python TUI board, following the existing `IssueField` and `_issue_indicator()` patterns.

## Steps

### 1. Add `_pr_indicator()` function (~line 68, after `_issue_indicator()`)

```python
def _pr_indicator(url: str) -> str:
    """Return a Rich markup PR indicator based on the platform URL."""
    url_lower = url.lower()
    if "github.com" in url_lower:
        return "[green]PR:GH[/green]"
    elif "gitlab.com" in url_lower:
        return "[#e24329]MR:GL[/e24329]"
    elif "bitbucket.org" in url_lower:
        return "[blue]PR:BB[/blue]"
    return "[green]PR[/green]"
```

### 2. Add `PullRequestField` widget (~line 1018, after `IssueField`)

```python
class PullRequestField(Static):
    """Clickable PR URL field that opens in browser."""
    can_focus = True

    def __init__(self, url: str, **kwargs):
        self.url = url
        indicator = _pr_indicator(url)
        super().__init__(f"[b]Pull Request:[/b] {indicator} {url}", **kwargs)

    def on_key(self, event):
        if event.key == "enter":
            import webbrowser
            webbrowser.open(self.url)
```

### 3. Update `TaskCard.compose()` (~line 552)

After the `if issue:` block:
```python
pr_url = meta.get('pull_request', '')
if pr_url:
    info.append(_pr_indicator(pr_url))
contributor = meta.get('contributor', '')
if contributor:
    info.append(f"[dim]@{contributor}[/dim]")
```

### 4. Update detail dialog (~line 1491)

After the `if meta.get("issue"):` block:
```python
if meta.get("pull_request"):
    yield PullRequestField(meta["pull_request"], classes="meta-ro")
if meta.get("contributor"):
    contributor_text = f"[b]Contributor:[/b] @{meta['contributor']}"
    if meta.get("contributor_email"):
        contributor_text += f" ({meta['contributor_email']})"
    yield ReadOnlyField(contributor_text, classes="meta-ro")
```

## Verification

1. Create task with PR metadata using aitask_create.sh
2. Run `./ait board` — check PR badge on card, contributor name visible
3. Open detail dialog — check PullRequestField and ContributorField
4. Test Enter key on PullRequestField — should open URL
5. Test tasks WITHOUT PR metadata — no regressions

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_2`
