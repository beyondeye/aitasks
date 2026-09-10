---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing, test_infrastructure]
anchor: 1705
followup_kind: review_finding
created_at: 2026-09-09 13:14
updated_at: 2026-09-09 13:14
---

## Context

Found while verifying t1705_7: `bash tests/run_all_python_tests.sh` does not
pass on `main`. Three modules fail, and all three were confirmed **pre-existing**
by re-running them in a detached worktree at t1705_7's merge-base — they are not
caused by that task.

They matter because the suite's last line is the verdict the task workflow reads
before archival. While it says `FAILED`, that signal carries no information: a
real regression is indistinguishable from this standing noise, and the honest
response to a red suite ("find out what you broke") costs a re-verification
every time.

Observed on macOS 15.6 / CPython 3.13.13, `runner=unittest` (the pytest dev tier
is not installed on that box, so the parallel lane was not in play — this is not
a test-isolation artifact of `--dist loadfile`).

## The three failures

1. **`tests/test_desync_state.py`** — `test_changelog_warns_for_data_desync_and_
   ignores_bad_helper_output`. A fixture-completeness bug: the synthetic project
   it builds does not include `.aitask-scripts/lib/stale_lock.sh`, so
   `task_utils.sh:31` fails to source it and `aitask_changelog.sh --gather`
   exits non-zero:
   `lib/task_utils.sh: line 31: .../lib/stale_lock.sh: No such file or directory`
   Likely the fixture's copy-list drifted when `stale_lock.sh` was added.

2. **`tests/test_prompt_detection.py`** — 2 of 22 checks, deterministic:
   - `_check_characterization_pattern_command_matrix`: "codex_yes_proceed on
     current_command='node': expected kind 'codex_yes_proceed', got ''"
   - `_check_scoping_provenance_is_reported`: "an unresolved pane must NOT
     report itself as scoped"
   Both look like real assertions about `monitor/prompt_patterns.py` scoping
   rather than fixture rot — worth reading before "fixing" the test.
   **Note the output shape:** this file prints TWO summaries, and the passing
   one is last, so `… | tail -2` shows `PASS: all 22 tests passed` while the
   process exits 1. Read the exit status, not the tail.

3. **`tests/test_concern_parser.py`** — `TestProducerPlainWordsRule.
   test_production_assertion_fails_on_a_real_offender` (bare and with
   `producer='leak.md'`). The negative control for the producer plain-words
   rule: it asserts the production check FIRES on a planted offender, and it is
   not firing.

## What to do

Triage each one on its merits — at least (1) is fixture rot, but (2) and (3) are
assertions about production behaviour and may be reporting something real.
Do not blanket-skip them: a skipped negative control (3) is worse than a failing
one, because it stops testing the thing it exists to test.

## Verification

```bash
python3 tests/test_desync_state.py
python3 tests/test_prompt_detection.py; echo "exit=$?"   # exit status, not tail
python3 tests/test_concern_parser.py
bash tests/run_all_python_tests.sh                       # read ONLY the last line
```

Baseline to reproduce the "pre-existing" claim:
`git worktree add --detach <dir> <merge-base of t1705_7 and origin/main>` and run
the three modules there.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1766** id=2026-09-10T09:02:52Z.98a77edae8c374ed4de6cf95 from=t1766 from_verified=yes at=2026-09-10T09:02:52Z base=80d5ea53221cf89bcf0fbf4bd14e1ae23f9297b0 base_branch=main dirty=yes host=Darios-Mac-mini.local
>
> | Suite re-run from t1766 (2026-09-10, macOS 15.6 / CPython 3.13.13,
> | runner=unittest, full `bash tests/run_all_python_tests.sh`, 7307 tests):
> | **failure (1) of the three you list no longer reproduces.**
> | 
> | - `tests/test_desync_state.py` — 10 tests, `OK` standalone, and absent from the
> |   full run's FAIL lines. The `stale_lock.sh` fixture gap appears to have been
> |   repaired since this task was written. Verify before spending triage on it.
> | - `tests/test_prompt_detection.py` — still failing, same two checks verbatim:
> |   `_check_characterization_pattern_command_matrix` (codex_yes_proceed on
> |   current_command='node') and `_check_scoping_provenance_is_reported`.
> | - `tests/test_concern_parser.py` — still failing, same negative control
> |   (`TestProducerPlainWordsRule.test_production_assertion_fails_on_a_real_offender`,
> |   bare and with `producer='leak.md'`).
> | 
> | So the standing red is 3 unittest-level failures across **2** modules, not 3.
> | Confirmed unrelated to t1766: both modules fail identically with t1766's two
> | changed files stashed.
> | 
> | This is a tree-relative reading — the working tree carried only t1766's two
> | modified files (plus an untracked `website/content/docs/tuis/frozenagent/` from a
> | concurrent session) at the time.
