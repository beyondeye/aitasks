---
priority: medium
effort: low
depends: [t214_3]
issue_type: documentation
status: Ready
labels: [portability, shell]
created_at: 2026-02-25 12:13
updated_at: 2026-02-25 12:13
---

## Context

This is child task 4 of t214 (Multi-platform reviewguide import and setup dedup). The `aitask_setup.sh` script has an inline `_detect_git_platform()` function that duplicates `detect_platform()` from `task_utils.sh`, and uses GitHub API URLs to download the `bkt` (Bitbucket CLI) tool. Both are intentional design decisions that should be documented with comments.

## Key Files to Modify

- `aiscripts/aitask_setup.sh` — Add documentation comments only (no logic changes)

## Reference Files for Patterns

- `aiscripts/lib/task_utils.sh:85-97` — The `detect_platform()` function being duplicated
- `aiscripts/lib/terminal_compat.sh` — Has conflicting `die()`/`info()`/`warn()` definitions (reason for duplication)

## Implementation Plan

### Change 1: Expand inline detection comment (line 71)

Current:
```bash
# --- Git platform detection (inline — task_utils.sh not available during setup) ---
```

Replace with:
```bash
# --- Git platform detection (inline — duplicates detect_platform() from task_utils.sh) ---
# This is intentionally inlined rather than sourced because:
# 1. setup.sh defines its own die/info/warn/success helpers with "[ait]" prefix formatting
#    that would conflict with terminal_compat.sh's definitions (task_utils.sh depends on it)
# 2. setup.sh must be self-contained — it runs before the framework is fully initialized
```

### Change 2: Add comments above bkt GitHub API URLs

There are 3 occurrences (one per OS section: Arch ~line 143, Debian/Ubuntu ~line 206, Fedora ~line 239). Before each `bkt_ver=$(curl -s "https://api.github.com/...)` line, add:

```bash
# NOTE: bkt (bitbucket-cli) is hosted on GitHub — these api.github.com URLs are intentional
```

## Verification Steps

1. `shellcheck aiscripts/aitask_setup.sh` — no regressions from comment changes
2. Visual review of the added comments for accuracy
