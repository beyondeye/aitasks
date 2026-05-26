---
Task: t832_7_cross_repo_task_update.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_7_cross_repo_task_update
Branch: aitask/t832_7_cross_repo_task_update
Base branch: main
---

# Plan: cross-repo task update (Scope 1c)

See parent plan §t832_7. Depends on t832_1 (re-exec pattern + resolver
conventions + fake-project test harness).

## Goal

Add `--project <name>` to `aitask_update.sh`, mirroring
`aitask_create.sh --project`. Required by t832_5 for bidirectional
cross-edge wiring.

## Implementation steps

1. **Mirror `aitask_create.sh:1693-1753`** in `aitask_update.sh main()`:
   - Parse `--project <name>` out of argv before subcommand dispatch.
   - Enforce `--batch` (mirror create's restriction).
   - **Status-transition allowlist:** parse `--status` from forwarded
     argv. Refuse `Implementing` and `Done` cross-repo with hint:
     "cross-repo status transition to `<X>` must go through the
     cross-repo project's own `/aitask-pick` workflow".
   - Resolve via `aitask_project_resolve.sh`; die-with-hint on
     STALE / NOT_FOUND.
   - `cd "$root"; exec "$root/.aitask-scripts/aitask_update.sh" "${forwarded[@]}"`.

2. **Lock-check step** (must run inside the re-exec'd target before the
   actual update). Add at the top of `aitask_update.sh`'s batch-mode
   entry:
   - `aitask_lock.sh --check <task_num>` and parse output (`hostname:`
     and `owner:` lines).
   - Compare against local hostname (`hostname` command) and the user's
     resolved email.
   - If a different host/owner holds the lock, die with:
     "cross-repo task t<N> is locked by <owner>@<hostname>; cannot
      update from this host".
   - Skip the check if the lock is held by the local user on the local
     host (administrative updates while picking are fine).
   - Skip the check if no lock at all (single-user / no-remote mode).

3. **Document the allowlist explicitly** in `show_help()`:
   ```
   --project NAME    Cross-repo update target (requires --batch).
                     Only administrative fields can be updated cross-repo:
                     --xdeps, --xdeprepo, --labels, --add-label,
                     --remove-label, --priority, --effort, --deps,
                     --status (Ready|Editing|Postponed only),
                     --assigned-to, --boardcol, --boardidx.
                     Refused: --status Implementing|Done (use the
                     cross-repo project's own /aitask-pick instead).
   ```

## Tests

`tests/test_update_cross_repo.sh`:
- Two fake projects A and B with registered registry.
- **Success:**
  - `aitask_update.sh --batch --project b 1 --priority high` → succeeds.
  - `aitask_update.sh --batch --project b 1 --xdeps "1,2" --xdeprepo a` → succeeds.
  - `aitask_update.sh --batch --project b 1 --status Postponed` → succeeds.
  - `aitask_update.sh --batch --project b 1 --add-label foo` → succeeds.
- **Refused:**
  - `--project b 1 --priority high` (no `--batch`) → die.
  - `--project b 1 --status Implementing` → die with pick hint.
  - `--project b 1 --status Done` → die with pick hint.
  - `--project not_registered 1 ...` → die with `cd && ait projects add` hint.
  - B's t1 locked by different host → die with locked-by message.

## Verification

- `bash tests/test_update_cross_repo.sh` passes.
- `shellcheck .aitask-scripts/aitask_update.sh` clean.
- Manual: from `aitasks`,
  `./.aitask-scripts/aitask_update.sh --batch --project aitasks_mobile <id> --add-label test`
  succeeds without affecting local PWD.

## Notes for sibling tasks

- The lock-check pattern can be lifted to a `lib/cross_repo_lock_guard.sh`
  helper if future cross-repo helpers (e.g., cross-repo fold) ever land.
  Defer the extraction until a second consumer materializes.
- The status-transition allowlist is **the** policy boundary — any new
  status added to the framework must be classified here as administrative
  (allow) or workflow (refuse). Document this in `show_help()` so future
  maintainers see the convention.

## Out of scope

- **Cross-repo archive** — split-brain risk.
- **Cross-repo `--fold`** — folding semantics unsettled; defer until
  t832_6 reveals real need.

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
