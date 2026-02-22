---
Task: t210_shellcheck_as_dev_dependency.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t210 requests adding ShellCheck as a documented development dependency in the website documentation. The "Testing Changes" section already references `shellcheck` usage but doesn't explain how to install it. Developers need platform-specific install instructions.

## Plan

### 1. Add "Development Dependencies" section to `website/content/docs/development/_index.md`

Insert a new section **before** the "Modifying Scripts" section (before line 103). This section will document ShellCheck as a development dependency with install instructions for:

- **macOS (Homebrew):** `brew install shellcheck`
- **Arch Linux:** `sudo pacman -S shellcheck`
- **Ubuntu/Debian:** `sudo apt install shellcheck`

Also add the `shellcheck` linting command to the "Testing Changes" section since it's currently missing from that list.

### File to modify

- `website/content/docs/development/_index.md` — Add "Development Dependencies" section and update "Testing Changes"

### Verification

1. Run `cd website && hugo build --gc --minify` to confirm the site builds without errors

## Final Implementation Notes
- **Actual work done:** Added "Development Dependencies" section to `website/content/docs/development/_index.md` with two subsections: ShellCheck (with platform install commands for macOS, Ubuntu/Debian, Arch Linux) and Hugo (with platform install commands and links to `website/README.md` for full setup/troubleshooting). Also added `shellcheck` linting command to the "Testing Changes" code block.
- **Deviations from plan:** User requested adding Hugo as a development dependency as well, with links to the existing `website/README.md` install instructions. This was not in the original plan but was a natural extension.
- **Issues encountered:** Hugo not installed locally, so could not verify site build. Markdown structure is standard and should render correctly.
- **Key decisions:** Linked to `website/README.md` for Hugo setup rather than duplicating install instructions (Ubuntu requires manual `.deb` download which is better explained in the README).
