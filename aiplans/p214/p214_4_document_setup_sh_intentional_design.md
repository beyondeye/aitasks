---
Task: t214_4_document_setup_sh_intentional_design.md
Parent Task: aitasks/t214_multi_platform_reviewguide_import_and_setup_dedup.md
Sibling Tasks: aitasks/t214/t214_1_*.md, aitasks/t214/t214_2_*.md, aitasks/t214/t214_3_*.md
Archived Sibling Plans: aiplans/archived/p214/p214_1_*.md, aiplans/archived/p214/p214_2_*.md, aiplans/archived/p214/p214_3_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan

### Step 1: Expand inline detection comment (line 71)

Replace:
```bash
# --- Git platform detection (inline — task_utils.sh not available during setup) ---
```

With:
```bash
# --- Git platform detection (inline — duplicates detect_platform() from task_utils.sh) ---
# This is intentionally inlined rather than sourced because:
# 1. setup.sh defines its own die/info/warn/success helpers with "[ait]" prefix formatting
#    that would conflict with terminal_compat.sh's definitions (task_utils.sh depends on it)
# 2. setup.sh must be self-contained — it runs before the framework is fully initialized
```

### Step 2: Add bkt download comments

Find the 3 occurrences of `api.github.com/repos/avivsinai/bitbucket-cli` (Arch, Debian, Fedora sections) and add above each:

```bash
# NOTE: bkt (bitbucket-cli) is hosted on GitHub — these api.github.com URLs are intentional
```

### Step 3: Verify

```bash
shellcheck aiscripts/aitask_setup.sh
```

## Post-Implementation (Step 9)
Archive task and plan. Push changes.
