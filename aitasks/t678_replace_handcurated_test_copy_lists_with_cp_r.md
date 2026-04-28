---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [testing, bash_scripts]
created_at: 2026-04-27 17:24
updated_at: 2026-04-27 17:24
boardidx: 10
---

The macOS audit (t658) baseline run revealed three tests failing because their `setup_test_repo` functions hand-curate the list of `.aitask-scripts/*` files to copy into the scratch dir, and that list has gone stale as new transitive deps were added.

## Failures observed

- `tests/test_crew_groups.sh` and `tests/test_crew_report.sh` — fail with `aitask_crew_init.sh: line 20: lib/launch_modes_sh.sh: No such file or directory`. The setup copies `terminal_compat.sh` and `agentcrew_utils.sh` but not the newer `launch_modes_sh.sh` that `aitask_crew_init.sh` now sources.
- `tests/test_data_branch_migration.sh` — fails Test 5 (`aitask_create.sh --batch --commit`) with `aitask_claim_id.sh: line 26: lib/archive_scan.sh: No such file or directory`. The setup copies a hand-picked subset of scripts and libs but not `archive_scan.sh` that `aitask_claim_id.sh` now sources.

## Reference pattern

`tests/test_crew_status.sh` (line 101) already solved this:
```bash
# Mirror the full .aitask-scripts/ tree so transitive deps (e.g.
# lib/launch_modes_sh.sh) are present. Hand-curated copy lists drift
# silently as new sources/imports are added.
cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
```

## Suggested approach

Replace the hand-picked `cp` blocks in the three failing tests with the same `cp -R + prune __pycache__` pattern. Verify each test still runs in a reasonable time (the full tree is ~few MB; `cp -R` is fast).

## Verification

After the fix, all three tests must pass on macOS:
```bash
bash tests/test_crew_groups.sh
bash tests/test_crew_report.sh
bash tests/test_data_branch_migration.sh
```

Linux verification can be skipped — the failure mode is platform-agnostic.
