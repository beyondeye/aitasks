---
Task: t106_missing_install_doc_for_windows_and_gh.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t106 requested several installation documentation improvements. Most items were already addressed by previous tasks t133 (created `docs/installing-windows.md`) and t134 (added `gh auth login` to README, cleaned up Windows docs). Two small gaps remain.

## Changes

### 1. Add inline Windows/WSL note in README Quick Install

**File:** `README.md` (after line 73, the closing ``` of the first curl block)

Insert a blockquote note right after the curl install command so Windows users see it immediately, rather than 26 lines later at the end of the section:

```markdown
> **Windows users:** Run this inside a WSL shell, not PowerShell. See the [Windows/WSL guide](docs/installing-windows.md).
```

The existing full callout at the bottom of Quick Install (line 98) stays as-is.

### 2. Add cross-reference note in `docs/installing-windows.md`

**File:** `docs/installing-windows.md`

Instead of duplicating the `gh auth login` documentation, add a brief note after the "Install aitasks" section (after `ait setup`) pointing users to the README for post-install authentication setup:

Insert after the paragraph about `ait setup` (around line 61, before the `---`):

```markdown
After setup completes, see [Authentication with Your Git Remote](../README.md#authentication-with-your-git-remote) to configure GitHub access for task locking, sync, and issue integration.
```

### 3. Permissions prompt issue — NO ACTION

The task mentions the install script "failing at the question install claude code permissions." The code at `aiscripts/aitask_setup.sh:602-644` correctly handles both interactive and non-interactive cases. No bug found; likely a transient environment issue.

## Verification

- Read both modified files to confirm correct markdown formatting

## Final Implementation Notes
- **Actual work done:** Both planned changes implemented exactly as specified. Inline Windows/WSL note added to README Quick Install section, and cross-reference to authentication docs added to `docs/installing-windows.md`.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Most items from the original t106 task were already addressed by t133 and t134. The permissions prompt bug was investigated and found to be working correctly in code — no fix needed.

## Step 9 (Post-Implementation)

Archive task and plan files per the standard workflow.
