---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [agentcrew, testing]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-26 13:00
updated_at: 2026-04-26 14:06
completed_at: 2026-04-26 14:06
boardidx: 20
---

## Symptom

`bash tests/test_crew_runner.sh` hangs at "Test 2: dry-run shows correct ready agents" on an unmodified `main` (verified via `git stash` while implementing t647). Test 1 (Python syntax check) passes; Test 2 onward never returns. The hang is independent of t647's fix — it pre-dates that work.

## Reproduce

```bash
git stash    # ensure unrelated work doesn't interfere
timeout 30 bash tests/test_crew_runner.sh
# → outputs "Test 1" PASS, "Test 2: dry-run shows correct ready agents", then nothing
```

With `bash -x` the trace ends inside `setup_crew_with_agents`, on the line:

```
+ bash .aitask-scripts/aitask_crew_init.sh --id testcrew --batch --add-type impl:claudecode/opus4_6
```

## Likely root cause

`tests/test_crew_runner.sh:setup_test_repo()` (lines 93-125) builds a minimal isolated repo by copying a hand-picked subset of files into a tmpdir:

```
cp .aitask-scripts/lib/terminal_compat.sh    .aitask-scripts/lib/
cp .aitask-scripts/lib/agentcrew_utils.sh    .aitask-scripts/lib/
cp .aitask-scripts/lib/agent_launch_utils.py .aitask-scripts/lib/
cp .aitask-scripts/aitask_crew_init.sh       .aitask-scripts/
cp .aitask-scripts/aitask_crew_addwork.sh    .aitask-scripts/
cp .aitask-scripts/aitask_crew_command.sh    .aitask-scripts/
cp .aitask-scripts/agentcrew/__init__.py     .aitask-scripts/agentcrew/
cp .aitask-scripts/agentcrew/agentcrew_utils.py   .aitask-scripts/agentcrew/
cp .aitask-scripts/agentcrew/agentcrew_status.py  .aitask-scripts/agentcrew/
cp .aitask-scripts/agentcrew/agentcrew_runner.py  .aitask-scripts/agentcrew/
```

Two known dependencies are NOT copied:

1. **`.aitask-scripts/lib/launch_modes_sh.sh`** — sourced by `aitask_crew_init.sh:20`. A direct repro inside the test fixture errors with: `aitask_crew_init.sh: line 20: lib/launch_modes_sh.sh: No such file or directory`. The script has `set -euo pipefail` so this would normally exit non-zero, not hang — but the test invokes it inside a subshell with stderr discarded (`>/dev/null 2>&1`), so the failure is silent. After the helper appears to "succeed", the test proceeds to invoke the runner directly:

   ```
   PYTHONPATH=".aitask-scripts" python3 .aitask-scripts/agentcrew/agentcrew_runner.py \
     --crew testcrew --once --dry-run --batch
   ```

   The crew worktree was never created (because `aitask_crew_init.sh` aborted), so the runner either crashes before producing output or stalls waiting on `read_yaml` against missing files.

2. **`.aitask-scripts/lib/tui_registry.py`** — required by `lib/agent_launch_utils.py:23` (`from tui_registry import TUI_NAMES`). After t647's fix, `agentcrew_runner.py` adds `lib/` to `sys.path` and the import will be attempted; the import will then fail in the test fixture because `tui_registry.py` is not copied. Pre-t647 the import was never reached because the runner crashed earlier.

There may be more transitive deps (e.g., other `.sh` libs sourced by the helpers, or other Python modules pulled in by `agentcrew_utils`). A clean implementation should not enumerate them by hand.

## Suggested approach

Two viable fixes — pick one:

**A. Copy the whole `.aitask-scripts/` tree.**

Replace the per-file `cp` enumeration with a single `cp -r "$PROJECT_DIR/.aitask-scripts" .` (or `rsync -a`). The fixture is in a tmpdir per test — disk cost is negligible — and this guarantees no further drift bugs as new files are added under `.aitask-scripts/`. Risk: tests pick up unrelated files (e.g., `__pycache__`, board TUI). Mitigate with `--exclude '__pycache__'` if using rsync, or accept the noise.

**B. Bind-mount / symlink instead of copy.**

`ln -s "$PROJECT_DIR/.aitask-scripts" .aitask-scripts` inside the tmpdir. Same robustness as A with zero disk usage. The current copy approach was likely chosen so tests can mutate the scripts; check whether any test does so before symlinking. A grep for `chmod` or `>` redirects writing into `.aitask-scripts/*` inside the test will tell us.

I lean toward **A** with `cp -r --exclude '__pycache__'` as the safer of the two, but the implementer should validate by running the full suite end-to-end after the fix.

## Out of scope

- Refactoring the test to use a shared fixture builder for crew runner / brainstorm / status tests (potentially a `tests/lib/setup_crew_repo.sh` helper). That would be a separate task once the immediate hang is fixed.

## Verification

```bash
bash tests/test_crew_runner.sh           # must complete (no hang) and either all-pass or surface real failures
shellcheck tests/test_crew_runner.sh
```

The strengthened `tests/test_agentcrew_pythonpath.sh` (12 assertions, added in t647) must continue to pass.

## Discovered during

t647 (`fix_silent_crew_runner_crash_missing_lib_sys_path`) — the test was listed in t647's verification plan but found broken on `main` independent of the fix.
