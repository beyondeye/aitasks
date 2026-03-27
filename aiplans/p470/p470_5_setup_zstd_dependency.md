---
Task: t470_5_setup_zstd_dependency.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_1_*.md, aitasks/t470/t470_4_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_5: ait setup Dependency Installation

## Overview
Add `zstd` to the tool installation flow in `aitask_setup.sh` for all supported platforms.

## Step 1: Read aitask_setup.sh tool installation sections

Identify the package lists for each OS case (macOS/brew, Debian/Ubuntu/WSL/apt, Fedora/dnf, Arch/pacman).

## Step 2: Add zstd to each OS package list

The package name `zstd` is consistent across all package managers:
- `brew install zstd`
- `apt-get install zstd`
- `dnf install zstd`
- `pacman -S zstd`

Add `zstd` alongside existing tools (fzf, jq, git).

## Step 3: Add zstd to tool verification check

If there's a post-install check that verifies tools are available, add `zstd` to it.

## Step 4: Verify

```bash
shellcheck .aitask-scripts/aitask_setup.sh
which zstd  # verify available on current system
```

## Step 9 Reference
Post-implementation: user review, commit, archive task, push.
