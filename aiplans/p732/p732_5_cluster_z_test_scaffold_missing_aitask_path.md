---
Task: t732_5_cluster_z_test_scaffold_missing_aitask_path.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---

# p732_5 — Cluster Z: Test scaffolds missing aitask_path.sh

## Goal

Resolve the **single root cause** behind 4 of the 13 failing tests. Recommended approach: extract a shared `tests/lib/test_scaffold.sh` helper (Strategy 2 — see child task body) and converge all 55 affected tests onto it.

## Single root cause (confirmed)

`lib/aitask_path.sh` was added by t695_3 (Apr 28) and is now sourced unconditionally on `./ait` line 7 and from many helpers. 55 tests scaffold a fake `.aitask-scripts/lib/` without copying `aitask_path.sh`. The 4 below crash because they invoke `./ait` or scripts that source it; the other 51 are time bombs.

Inventory query:
```bash
for t in tests/test_*.sh; do
  if grep -q ".aitask-scripts/lib/" "$t" && ! grep -q "aitask_path" "$t"; then
    echo "$t"
  fi
done
```

## Confirmed failures (today)

All 4 share the error pattern `… line N: <scratch>/.aitask-scripts/lib/aitask_path.sh: No such file or directory`:
- `tests/test_task_push.sh` (./ait git ...)
- `tests/test_brainstorm_cli.sh` (aitask_brainstorm_init.sh line 15)
- `tests/test_explain_context.sh` (aitask_explain_context.sh line 11)
- `tests/test_migrate_archives.sh` (./ait migrate-archives)

## Steps

1. Read `aitasks/t732/t732_5_cluster_z_test_scaffold_missing_aitask_path.md` for full context including both implementation strategies.
2. Choose strategy:
   - **Recommended (Strategy 2)**: extract `tests/lib/test_scaffold.sh` with `setup_fake_aitask_repo()`. Converge all 55 affected tests.
   - **Fallback (Strategy 1)**: mechanical — add `cp aitask_path.sh ...` to each of the 4 failing tests only.
3. If Strategy 2:
   a. Write `tests/lib/test_scaffold.sh` with `setup_fake_aitask_repo()` that always copies `aitask_path.sh` + `terminal_compat.sh`.
   b. Convert the 4 failing tests first; verify they pass.
   c. Convert the remaining 51 tests; verify no regressions.
   d. **Do NOT punt the 51-port to a follow-up.** Per CLAUDE.md "Plan split: in-scope children, not deferred follow-ups", this is in-scope work for t732_5. If the diff is genuinely too large for one task, split into t732_5_1 (helper + 4 fixes) and t732_5_2 (port remaining 51) with `aitask_create.sh --parent 732_5`.
4. Run regression check (verification below).

## Verification

- Originally-failing 4 tests pass:
  ```bash
  for t in tests/test_task_push.sh tests/test_brainstorm_cli.sh tests/test_explain_context.sh tests/test_migrate_archives.sh; do bash "$t" || break; done
  ```
- All 55 affected tests pass:
  ```bash
  for t in $(grep -l ".aitask-scripts/lib/" tests/test_*.sh); do
    bash "$t" >/dev/null 2>&1 || echo "REGRESSION: $t"
  done
  ```
- No `REGRESSION:` lines printed.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_5`.
