---
Task: t470_5_setup_zstd_dependency.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_6_*.md, aitasks/t470/t470_7_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_5: ait setup Dependency Installation + Website Docs

## Overview
Add `zstd` to the tool installation flow in `aitask_setup.sh` for all supported platforms, and update website documentation to list it as a required dependency.

## Step 1: Add zstd to aitask_setup.sh tools array [DONE]

File: `.aitask-scripts/aitask_setup.sh` line 112
Change: `local tools=(fzf jq git)` → `local tools=(fzf jq git zstd)`

The existing OS case branches handle generic tools via `*) pkgs+=("$tool")` fallthrough.

## Step 2: Update website installation docs [DONE]

File: `website/content/docs/installation/_index.md` line 90
Added `zstd` to CLI tools list.

## Step 3: Update website setup-install docs [DONE]

File: `website/content/docs/commands/setup-install.md` line 23
Added `zstd` to CLI tools description.

## Step 4: Verify [DONE]

- shellcheck: passes (only pre-existing SC2015 info notes)
- `which zstd`: `/usr/bin/zstd` available

## Final Implementation Notes
- **Actual work done:** Added `zstd` to the tools array in `aitask_setup.sh` and updated two website documentation pages to list it as a required dependency. Exactly as planned.
- **Deviations from plan:** Original plan only covered the setup script. User feedback during planning added website docs update (not covered by any sibling task).
- **Issues encountered:** None. The existing code structure made the change trivial — all OS case branches have generic tool fallthrough.
- **Key decisions:** No separate tool verification check needed since the existing `command -v` loop covers all tools in the array.
- **Notes for sibling tasks:** The `zstd` CLI tool is now installed by `ait setup`. t470_6 (migration script) and t470_7 (run migration) can assume `zstd` is available after setup.
