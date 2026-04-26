---
Task: t651_fix_test_crew_runner_hang_missing_test_fixtures.md
Base branch: main
plan_verified: []
---

# Plan: Fix `tests/test_crew_runner.sh` hang from missing fixture deps (t651)

## Context

`bash tests/test_crew_runner.sh` hangs indefinitely at "Test 2: dry-run shows
correct ready agents" on a clean `main`. The hang predates t647 — it was
discovered while verifying that fix and is filed independently.

**Root cause** (already nailed down in the task description):
`tests/test_crew_runner.sh:setup_test_repo()` (lines 93-125) builds an isolated
fixture repo by `cp`-ing a hand-picked subset of files from `.aitask-scripts/`.
Two transitive deps are not in the list:

1. `lib/launch_modes_sh.sh` — sourced from `aitask_crew_init.sh:20`. The crew-
   init script aborts with `set -euo pipefail`, but the test invokes it with
   `>/dev/null 2>&1`, so the abort is silent. The runner then runs against a
   missing crew worktree and stalls.
2. `lib/tui_registry.py` — imported by `lib/agent_launch_utils.py:23`. After
   t647's fix, the runner adds `lib/` to `sys.path` and the import will be
   attempted, then fail in the fixture.

There may be more transitive deps (other `lib/*.sh` sources, more Python
modules pulled in by `agentcrew_utils`). Enumerating them by hand is the bug
that produced the current hang — the fix should not perpetuate that pattern.

## Approach

Take **option A** from the task description: replace the hand-curated `cp`
list with a single recursive copy of the entire `.aitask-scripts/` tree. The
fixture lives in a tmpdir per test — disk cost is negligible (~few MB) — and
this guarantees no further drift bugs as new files are added under
`.aitask-scripts/`.

Reasons over option B (symlink): symlinking `.aitask-scripts` to the project
dir would let the runner's Python import machinery write
`__pycache__/*.pyc` files into the real source tree, polluting the working
copy. A real copy keeps the fixture isolated.

A grep of the test confirmed the only mutation done to the copied scripts is
`chmod +x` on three already-executable files (lines 115-116) — no content
mutation, so a copy preserves test semantics exactly.

## Critical file

- `tests/test_crew_runner.sh` — only file modified.

## Implementation

In `setup_test_repo()` (lines 93-125):

1. Stop pre-creating `.aitask-scripts/` and its subdirs. Keep only
   `mkdir -p aitasks/metadata` (still needed for the `userconfig.yaml` write
   at line 118).

2. Replace the per-file `cp` enumeration (lines 105-114) with a single
   recursive copy:
   ```bash
   cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
   ```

3. After the copy, strip Python bytecode caches so the fixture stays clean
   and Python regenerates them per-test:
   ```bash
   find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
   ```
   (`find … -prune -exec rm -rf {} +` is the portable form; `-prune` stops
   `find` from descending into the dir before `rm` deletes it. Works on both
   GNU and BSD `find`.)

4. Keep the existing `chmod +x` lines (115-116) as-is. They are no-ops on
   the copied files (the source is already +x), but harmless and serve as a
   belt-and-suspenders for any platform where `cp -R` might drop the bit.

Concrete diff target — replace lines 103-114:

```bash
# BEFORE
mkdir -p .aitask-scripts/lib .aitask-scripts/agentcrew aitasks/metadata

cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/agent_launch_utils.py" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_command.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/__init__.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_utils.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_runner.py" .aitask-scripts/agentcrew/

# AFTER
mkdir -p aitasks/metadata

# Copy the full .aitask-scripts/ tree so the fixture mirrors the real repo
# layout. Avoids the drift bug where new transitive deps (e.g. lib/launch_modes_sh.sh,
# lib/tui_registry.py) cause silent crew_init failures and runner hangs.
cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
```

The trailing `chmod` lines and the `userconfig.yaml` write are unchanged.

## Verification

Run from the project root:

1. The hang is gone and the suite either fully passes or surfaces real
   assertion failures (no more silent stall):
   ```bash
   timeout 120 bash tests/test_crew_runner.sh
   ```
   Expected: completes within timeout, prints
   `=== Results: <N> passed, <M> failed, <T> total ===`.

2. Lint stays clean:
   ```bash
   shellcheck tests/test_crew_runner.sh
   ```

3. The strengthened `tests/test_agentcrew_pythonpath.sh` (12 assertions added
   in t647) must continue to pass:
   ```bash
   bash tests/test_agentcrew_pythonpath.sh
   ```

4. Spot-check the fixture is clean (no `__pycache__` left behind in the
   copied tree). Manual inline check inside `setup_test_repo` is sufficient
   — done implicitly by the `find … -prune -exec rm -rf` step.

## Out of scope (per task description)

- Refactoring to a shared `tests/lib/setup_crew_repo.sh` fixture builder
  reusable across `test_crew_runner.sh` / `test_brainstorm.sh` /
  `test_agentcrew_status.sh`. That is a follow-up once the immediate hang is
  fixed.

## Step 9 (Post-Implementation)

After the user approves and the implementation passes verification, follow
the standard task-workflow Step 9 cleanup: commit changes, archive task
t651, push.

## Final Implementation Notes

- **Actual work done:** Replaced the per-file `cp` enumeration in
  `tests/test_crew_runner.sh:setup_test_repo()` with a single
  `cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts`, followed by a
  portable `find … -type d -name __pycache__ -prune -exec rm -rf {} +` to
  keep the fixture clean. Dropped the now-redundant
  `mkdir -p .aitask-scripts/lib .aitask-scripts/agentcrew` (`cp -R` creates
  the destination tree). Kept `mkdir -p aitasks/metadata` (still needed for
  the `userconfig.yaml` write) and the trailing `chmod +x` lines (no-op
  belt-and-suspenders).
- **Deviations from plan:** None. Implemented exactly as planned (option A).
- **Issues encountered:** None.
- **Key decisions:** Confirmed before implementing that no test mutates
  `.aitask-scripts/*` content (only `chmod +x` on already-executable files),
  so a copy preserves test semantics exactly. Used `find -prune -exec rm -rf`
  rather than `cp --exclude` because `--exclude` is not BSD-portable.
- **Verification result:**
  - `timeout 180 bash tests/test_crew_runner.sh` → 31/31 assertions pass
    (was hanging indefinitely before this fix). Suite completes in ~30s.
  - `shellcheck tests/test_crew_runner.sh` → exit 0.
  - `bash tests/test_agentcrew_pythonpath.sh` (t647 regression) → 12/12 pass.
