---
Task: t327_move_terminal_setup_workflow_to_install_pages.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Move terminal-setup and authentication to installation sub-pages

## Context

The `workflows/terminal-setup.md` page covers terminal emulator recommendations and monitoring tips. This content fits better in the Installation section. The "Authentication with Your Git Remote" section of `installation/_index.md` was also extracted to keep the main installation page focused on the install process itself.

## Steps

1. Create `website/content/docs/installation/terminal-setup.md` — move content from `workflows/terminal-setup.md`, update relative links (`../../` → `../`), weight 30
2. Create `website/content/docs/installation/git-remotes.md` — extract auth section from `installation/_index.md`, title "Git Remotes", weight 40
3. Edit `installation/_index.md` — remove auth section, keep "Next: Getting Started" footer
4. Delete `website/content/docs/workflows/terminal-setup.md`

## Post-Review Changes

### Change Request 1 (2026-03-07)
- **Requested by user:** Add link to tmux wiki; rename authentication sub-page to "Git Remotes"
- **Changes made:** Added `[**tmux**](https://github.com/tmux/tmux/wiki)` link in terminal-setup.md; renamed `authentication.md` → `git-remotes.md` with title/linkTitle "Git Remotes"
- **Files affected:** `website/content/docs/installation/terminal-setup.md`, `website/content/docs/installation/git-remotes.md`

### Change Request 2 (2026-03-07)
- **Requested by user:** Mention lazygit in the Git diff viewer tab
- **Changes made:** Updated Tab 4 description to include lazygit and delta links; updated "Review progress" bullet to mention lazygit
- **Files affected:** `website/content/docs/installation/terminal-setup.md`

### Change Request 3 (2026-03-07)
- **Requested by user:** Add Codex CLI and OpenCode optional install sections to main installation page
- **Changes made:** Added "Optional: Codex CLI support" and "Optional: OpenCode support" subsections to "What Gets Installed" in `installation/_index.md`
- **Files affected:** `website/content/docs/installation/_index.md`

### Change Request 4 (2026-03-07)
- **Requested by user:** Add WezTerm to terminal emulators list; rename "Recommended terminal emulators" to "Some good terminal emulators:"
- **Changes made:** Added WezTerm entry with link to wezfurlong.org/wezterm/; renamed heading text
- **Files affected:** `website/content/docs/installation/terminal-setup.md`

## Final Implementation Notes

- **Actual work done:** Moved terminal-setup content to `installation/terminal-setup.md` (weight 30), extracted auth section to `installation/git-remotes.md` (weight 40), cleaned up `_index.md`, deleted old `workflows/terminal-setup.md`, added optional Codex CLI and OpenCode install info to main page
- **Deviations from plan:** None; post-review rounds added several user-requested refinements
- **Issues encountered:** None; hugo build passed cleanly (98 pages) after each change
- **Key decisions:** Used `git-remotes.md` filename matching user's "Git Remotes" title request; pulled Codex/OpenCode install details from `aiscripts/aitask_setup.sh`
