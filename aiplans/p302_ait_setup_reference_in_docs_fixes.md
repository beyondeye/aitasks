---
Task: t302_ait_setup_reference_in_docs_fixes.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t302 — ait setup project directory documentation and script fixes

## Context

Users may not realize that `ait setup` and the `curl` one-liner installer must be run from the **root of a git repository** (the project directory containing `.git/`). The current documentation says "in your project directory" but doesn't explain why. The scripts check for git but don't explain the tight integration or confirm the directory is correct. This task improves both documentation and scripts to make the requirement clear, and creates a separate task to explore global installation.

---

## Part A: Documentation improvements

### A1. `website/content/docs/installation/_index.md`
- Add a callout block before "Install into your project directory:" explaining the git root requirement
- Change "Install into your project directory:" → "Install into your project directory (the git repository root):"
- In the "Already have the global ait shim?" section, add a comment to the `cd` line and a follow-up sentence

### A2. `website/content/docs/getting-started.md`
- Change "In your project directory:" → "In your project directory (the root of the git repository, where `.git/` lives):"
- Add a callout after the curl command explaining why the project root matters

### A3. `website/content/docs/commands/setup-install.md`
- Add a callout after the opening description (before the `ait setup` code block)
- Update step 4 description to be more detailed about the git check

---

## Part B: Script improvements

### B1. `install.sh` — `confirm_install()` (lines 101–113)
- Add git-root detection: if inside a git repo but not at root, warn with default-No prompt
- If no git repo found, display informational message about the git dependency
- Preserve existing behavior for piped stdin (`curl | bash`)

### B2. `aiscripts/aitask_setup.sh` — `ensure_git_repo()` (lines 624–655)
- Add subdirectory detection: warn if aitasks is installed inside a git repo but not at root
- Expand the "no git repo" messaging to list specific git-dependent features (task IDs, locking, sync, versioned files)
- Add a two-stage confirmation: first "Is this the correct project directory?", then "Initialize a git repository?"
- Better abort messaging telling user what to do next

### B3. `aiscripts/aitask_setup.sh` — Global shim bootstrap (lines 551–556)
- Expand the messaging when the shim detects no aitasks project to explain the git root requirement

---

## Part C: New task for global install exploration

Create a new task using `aitask_create.sh --batch` to explore the feasibility of global/partial-global aitasks installation, covering: skill path requirements, version management across projects, dispatcher discovery, and trade-offs vs per-project installation.

---

## Implementation order

1. B1 — `install.sh` `confirm_install()`
2. B2 — `aitask_setup.sh` `ensure_git_repo()`
3. B3 — `aitask_setup.sh` global shim bootstrap
4. A1, A2, A3 — documentation files
5. C — create new task
6. Verify: `shellcheck install.sh aiscripts/aitask_setup.sh`

## Verification
- `shellcheck install.sh aiscripts/aitask_setup.sh` — no lint errors
- `cd website && hugo build --gc --minify` — docs build cleanly

## Post-implementation
- Step 9: archive task, push changes

## Final Implementation Notes
- **Actual work done:** All planned changes implemented as designed — no deviations. Enhanced `install.sh` confirm_install(), `aitask_setup.sh` ensure_git_repo() and global shim bootstrap, plus 3 documentation pages. Created task t304 for global install exploration.
- **Deviations from plan:** None.
- **Issues encountered:** None. Shellcheck passed (only pre-existing info-level warnings). Hugo build succeeded.
- **Key decisions:** Used default-No (`[y/N]`) prompts for the subdirectory-detection warnings (where continuing is risky) and kept default-Yes (`[Y/n]`) for normal "install here?" prompts.
