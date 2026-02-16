---
Task: t134_incorrect_windows_docs.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t134 requires fixing several documentation issues in `docs/installing-windows.md` and moving the authentication section to `README.md` since it applies to all platforms.

## File: `docs/installing-windows.md`

### 1. Fix Prerequisites (line 27)
- Remove "A GitHub account (for issue integration features)"

### 2. Remove GitHub Authentication section (lines 82-93)
- Delete the entire "## GitHub Authentication" section (it moves to README.md)
- Update TOC to remove the link

### 3. Reorder Terminal Options (lines 97-122)
- New order: VS Code with WSL Extension → Default WSL Terminal → Warp Terminal
- Remove "recommended" language from Warp
- Fix Default WSL Terminal: remove claim that `ait board` has display issues — it is fully functional
- Update TOC to reflect new order

### 4. Trim Known Issues (lines 126-131)
- Remove `date -d` compatibility bullet and Bash version bullet
- Keep only the Legacy Console bullet

## File: `README.md`

### 5. Add "Authentication with Your Git Remote" section
- Insert after "What Gets Installed" section (before "## Documentation", around line 117)
- Explain that authentication is needed for full aitasks functionality (task locking, sync, issue integration), not just issue integration
- Add subsections:
  - **### GitHub** — `gh auth login` instructions
  - **### GitLab** — TODO placeholder
  - **### Bitbucket** — TODO placeholder
- Update the Windows doc reference at line 129 to remove "GitHub authentication" from the description

## Verification
- Read both modified files to confirm correctness
- Verify TOC links match section anchors in installing-windows.md
- Ensure no broken markdown formatting

## Final Implementation Notes
- **Actual work done:** All 5 planned changes implemented as specified. Authentication section moved from Windows doc to README.md per user feedback during planning.
- **Deviations from plan:** User requested moving authentication to README.md instead of keeping it in the Windows doc (original plan had it staying in installing-windows.md). Plan was updated before approval.
- **Issues encountered:** None.
- **Key decisions:** Authentication section placed between "What Gets Installed" and "Documentation" sections in README.md, as it's a natural post-install setup step.
