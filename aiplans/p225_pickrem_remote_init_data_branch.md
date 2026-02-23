---
Task: t225_pickrem_remote_init_data_branch.md
Branch: (current branch)
---

# Plan: Lightweight data branch initialization script (t225)

## Context

In Claude Code Web (aitask-pickrem), `ait setup` is not run before picking tasks. When the repo uses aitask-data branch mode (task/plan data on a separate orphan branch), the `.aitask-data/` worktree and `aitasks`/`aiplans` symlinks must exist before any task operations work. Currently this logic is embedded in the full `setup_data_branch()` function in `aitask_setup.sh` (lines 773-985), which also handles migration, interactive prompts, .gitignore updates, and CLAUDE.md updates — none appropriate for a lightweight startup check.

## Changes

### 1. Create `aiscripts/aitask_init_data.sh` (~70 lines)

Lightweight, idempotent, non-interactive script that ensures the aitask-data worktree and symlinks are ready.

**Logic flow:**
1. If `.aitask-data/.git` exists → verify symlinks exist (create if missing) → output `ALREADY_INIT`, exit 0
2. If `aitasks/` is a real directory (not symlink) → output `LEGACY_MODE`, exit 0
3. Check if `aitask-data` branch exists locally (`git show-ref`) or on remote (`git ls-remote`). If remote-only, `git fetch origin aitask-data`
4. If branch not found anywhere → output `NO_DATA_BRANCH`, exit 0
5. `git worktree prune` (clean stale entries) then `git worktree add .aitask-data aitask-data`
6. Remove broken symlinks if present, create fresh: `ln -sf .aitask-data/aitasks aitasks` and `ln -sf .aitask-data/aiplans aiplans`
7. Output `INITIALIZED`

**Conventions:** `#!/usr/bin/env bash`, `set -euo pipefail`, sources `terminal_compat.sh`. Structured output on stdout, human messages via `info()`/`warn()` to stderr. `--help` flag supported.

### 2. Update `.claude/skills/aitask-pickrem/SKILL.md`

Insert a new **Step 0: Initialize Data Branch** before Step 1, calling `./aiscripts/aitask_init_data.sh`.

### 3. Create `tests/test_init_data.sh`

8 test cases following `tests/test_task_git.sh` pattern.

## Verification

1. `shellcheck aiscripts/aitask_init_data.sh`
2. `bash tests/test_init_data.sh` — all tests pass
3. Manual: `./aiscripts/aitask_init_data.sh` in this repo

## Final Implementation Notes
- **Actual work done:** Created `aitask_init_data.sh` (~100 lines including help), updated pickrem SKILL.md with Step 0, wrote comprehensive test suite (9 tests, 30 assertions). Script is internal-only (not registered in `ait` dispatcher per user request).
- **Deviations from plan:** Script ended up ~100 lines rather than ~70 (help section is thorough). Added `git worktree prune` before worktree creation to handle stale entries. Used `>/dev/null 2>&1` on `git worktree add` to prevent stdout noise from mixing with structured output. Test suite has 9 test cases (added help flag test) rather than 8.
- **Issues encountered:** `git worktree add` outputs "HEAD is now at..." to stdout, which mixed with our structured output. Fixed by redirecting both stdout and stderr from that command.
- **Key decisions:** Structured output goes to stdout, human-readable messages to stderr (via `info()`/`warn()` with `>&2`). This keeps the output clean for programmatic parsing by pickrem.

## Post-implementation: Step 9 (archive)
