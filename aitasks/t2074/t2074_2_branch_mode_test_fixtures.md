---
priority: high
effort: high
depends: [t2074_1]
issue_type: test
status: Ready
labels: [test_infrastructure, tests, git]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:31
updated_at: 2026-10-20 12:34
---

## Context

This is part of t2074, which removes legacy repository mode. About 125 test
files run on legacy fixtures, almost all of them implicitly: `git init`, a real
`aitasks/`, a plain commit, and then task writers that go through `task_git`
(plain git in legacy mode). This child builds the shared fixture tooling, and
measures exactly which tests the enforcement flip will break. The conversion
batches (t2074_4 to t2074_8) depend on it.

The binding contract is the "Probe definition" and C1 in
`aiplans/p2074_remove_legacy_repository_mode_support.md`. Read them first.
This task depends on t2074_1 (the classifiers) because the probe uses them.

## Deliverables

1. **Helpers** in `tests/lib/data_branch_fixture.sh`:
   - `ait_fixture_to_branch_mode <repo> [--remote <bare>]` converts a fixture
     that has a real `aitasks/`/`aiplans/` (committed or not) into a
     **registered** orphan `aitask-data` worktree at `.aitask-data`. It uses
     production `ait_ensure_data_symlinks` (`lib/data_symlinks.sh`), the
     `.gitignore` entries, and removal from main's index with a commit. When a
     remote exists, it pushes the data branch. The fixture data must be
     preserved.
   - `fixture_data_git` is the assertion wrapper for `git -C .aitask-data`.

   Python: `convert_to_branch_mode(root)` in `tests/lib/branch_mode_repo.py`.
2. **Convert the clone-style builders to registered worktrees**, keeping their
   signatures. These builders create `.aitask-data` as a standalone repo, which
   the C1a `foreign_repo` check rejects:
   - `tests/lib/board_fixture.py` (`_layout`/`build_tree` `branch_mode=True`,
     lines 494-650)
   - `tests/lib/metadata_update_fixture.sh:188`
   - the legacy builders at `metadata_update_fixture.sh:124` and `:146`

   Read every builder before reusing it. Helpers hardcode conventional paths;
   see the memory "trace fixture helper before reusing it".
   `tests/test_task_push.sh:158` is out of scope: t2074_8 handles it.
   `make_legacy_repo` (`branch_mode_repo.py:268`) stays as-is for refusal
   tests.
3. **Self-test** in `tests/test_data_branch_fixture.sh`: the helper's layout
   gives C1a `branch` / C1b `ready`, exactly like a real `setup_data_branch`
   layout, and the fixture's task data is preserved.
4. Add a fixture-layout section to `aidocs/framework/testing_conventions.md`.
5. **Pre-phase `measure_flip_breakage`**, the authoritative measurement.
   - In an isolated `git worktree`, apply the probe as a throwaway patch:
     rung 4 dies, rungs 1-3 accept only C1a=`branch`, and the writer guards
     require C1b=`ready`. **Never commit it.**
   - Run every `tests/test_*.sh` and the Python suite. Record per file the exit
     status, the summary line and `TOTAL`, and per test case the failures
     (Python: test ids).
   - Also record the **pre-conversion baseline** on the unpatched tree: the
     summary/`TOTAL` per bash file and the collected ids per Python module.
   - Assign each failing file to a batch (t2074_4 to t2074_8, using the parent
     plan's grouping). Identify the retired cases (parent plan "Retired-behaviour
     cases", plus any case that depends solely on legacy behaviour). Fix the
     **quarantine file list** (`tests/test_legacy_retired_<area>.sh|.py`) and
     which batch owns each retired case.
   - Write all of this into this child's plan, which is committed. Send each
     wave-2 child its slice with `./ait note <id> --from 2074_2`.

## Verification

- `bash tests/test_data_branch_fixture.sh`
- every test that uses the converted builders still passes: board tests via
  `bash tests/run_all_python_tests.sh`, plus `test_usage_update.sh`,
  `test_verified_update.sh` and `test_verified_update_flags.sh`
- the measurement artifacts exist in the plan and the notes landed
  (`NOTE_APPENDED:`)
