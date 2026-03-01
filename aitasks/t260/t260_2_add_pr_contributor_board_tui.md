---
priority: medium
effort: low
depends: [t260_1]
issue_type: feature
status: Ready
labels: [python_tui]
created_at: 2026-03-01 15:29
updated_at: 2026-03-01 15:29
---

## Context

This is child task 2 of the "Create aitasks from Pull Requests" feature (t260). After t260_1 adds the `pull_request`, `contributor`, and `contributor_email` metadata fields to the bash scripts, this task adds visual display support for these fields in the Python TUI board application.

**Why this task is needed:** The board TUI already displays issue indicators (GH/GL/BB badges) for tasks with linked issues. Tasks created from pull requests need similar visual indicators so users can quickly identify PR-originated tasks and see contributor info.

**Depends on:** t260_1 (metadata fields must exist for the board to parse and display them)

## Key Files to Modify

1. **`aiscripts/board/aitask_board.py`** (~2400 lines)
   - Add `_pr_indicator(url: str) -> str` function — similar to `_issue_indicator()` at line 68. Returns colored Rich markup badge like `[green]PR[/green]` or platform-specific (`[green]PR:GH[/green]`, `[#e24329]MR:GL[/e24329]`, `[green]PR:BB[/green]`)
   - Add `PullRequestField(Static)` widget — similar to `IssueField` at line 1018. Should have `can_focus = True` and open PR URL in browser on Enter key press
   - Add `ContributorField(Static)` widget — read-only display showing contributor username with platform link
   - In `TaskCard.compose()` (around line 552) — after the `if issue:` block, add PR indicator to card info display
   - In the detail dialog compose method (around line 1491) — after the `if meta.get("issue"):` block, add PullRequestField, ContributorField display

## Reference Files for Patterns

- **`aiscripts/board/aitask_board.py` line 68** — `_issue_indicator()` function: shows how platform-specific indicators are created from URLs
- **`aiscripts/board/aitask_board.py` line 1018** — `IssueField` class: shows the widget pattern with `can_focus`, Enter-to-open-browser behavior
- **`aiscripts/board/aitask_board.py` line 552** — `TaskCard.compose()`: shows where card info badges are added
- **`aiscripts/board/aitask_board.py` line 1491** — Detail dialog: shows where metadata fields are displayed
- **`aiscripts/board/task_yaml.py`** — No changes needed here; the generic YAML parser already preserves all fields including unknown ones

## Implementation Steps

1. **Add `_pr_indicator()` function** (near line 68, after `_issue_indicator()`):
   ```python
   def _pr_indicator(url: str) -> str:
       url_lower = url.lower()
       if "github.com" in url_lower:
           return "[green]PR:GH[/green]"
       elif "gitlab.com" in url_lower:
           return "[#e24329]MR:GL[/e24329]"  # GitLab orange
       elif "bitbucket.org" in url_lower:
           return "[blue]PR:BB[/blue]"
       return "[green]PR[/green]"
   ```

2. **Add `PullRequestField` widget** (near line 1018, after `IssueField`):
   - Same pattern as `IssueField`: inherits from `Static`, stores URL, opens in browser on Enter
   - Display format: `[b]Pull Request:[/b] <url>` with platform indicator

3. **Add `ContributorField` widget** (after `PullRequestField`):
   - Read-only `Static` widget showing `[b]Contributor:[/b] <username> (<contributor_email>)`

4. **Update `TaskCard.compose()`** — Add PR indicator after issue indicator:
   ```python
   pr_url = meta.get('pull_request', '')
   if pr_url:
       info.append(_pr_indicator(pr_url))
   contributor = meta.get('contributor', '')
   if contributor:
       info.append(f"[dim]by {contributor}[/dim]")
   ```

5. **Update detail dialog** — Add PR and contributor fields after issue field:
   ```python
   if meta.get("pull_request"):
       yield PullRequestField(meta["pull_request"], classes="meta-ro")
   if meta.get("contributor"):
       contributor_text = meta["contributor"]
       if meta.get("contributor_email"):
           contributor_text += f" ({meta['contributor_email']})"
       yield ReadOnlyField(f"[b]Contributor:[/b] {contributor_text}", classes="meta-ro")
   ```

## Verification Steps

1. Create a test task with PR metadata:
   ```bash
   echo "Test board PR display" | ./aiscripts/aitask_create.sh --batch --name "test_board_pr" \
     --pull-request "https://github.com/owner/repo/pull/42" \
     --contributor "octocat" \
     --contributor-email "12345+octocat@users.noreply.github.com" \
     --desc-file - --commit
   ```

2. Run the board TUI: `./ait board`
   - Verify PR badge appears on the task card (green "PR:GH" or similar)
   - Verify contributor name appears on the card
   - Open task detail dialog — verify PullRequestField and ContributorField display correctly
   - Press Enter on PullRequestField — verify it attempts to open the URL

3. Test with GitLab URL to verify platform-specific indicator colors

4. Verify tasks WITHOUT PR metadata still display correctly (no regressions)
