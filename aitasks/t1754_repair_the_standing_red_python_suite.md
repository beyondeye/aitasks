---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing]
followup_kind: upstream_defect
created_at: 2026-09-09 09:14
updated_at: 2026-09-09 09:15
---

## Context

The Python suite is **red on a clean checkout**, independently of any in-flight
work. Found while running the full suite for t1705_6; every failure was
reproduced in a pristine `git worktree` at HEAD, so none of them is caused by
that task.

`tests/run_all_python_tests.sh` therefore cannot currently be used as a
pass/fail gate: a contributor who runs it sees a red banner and has no way to
tell their own breakage from this standing set. That is the real cost — the
suite's verdict is what several workflow steps and CI depend on.

**No pending task tracks any of these.** Checked at creation time: `t1460`
concerns `TestProducerShortRegionRule` (a different rule class, and about
producer *discovery* being self-fulfilling); `t1522` asks for a **new** codex
update-prompt pattern rather than repairing an existing one; `t1116`
(Postponed) cites this module as passing "all 7 tests" and is stale (it has 22);
`t1398` / `t702` mention `test_desync_state.py` only for its fixture copy-list.

## The failures

1. **`tests/test_concern_parser.py`** —
   `TestProducerPlainWordsRule.test_production_assertion_fails_on_a_real_offender`
   (reported twice; the subtest carries `producer='leak.md'`). The negative
   control does not raise: `assertRaises(AssertionError)` sees nothing, i.e. the
   production rule no longer flags a deliberately planted offender. A guard that
   has stopped guarding — the failure mode where a green run means least.
   The paired symptom in the same module:
   `_example_prose_only_offences(text)` returns
   `['In plain words: inside the block.']` where `[]` is expected.

2. **`tests/test_desync_state.py`** —
   `DesyncStateTests.test_changelog_warns_for_data_desync_and_ignores_bad_helper_output`.

3. **`tests/test_prompt_detection.py`** — `ScriptChecksTest.test_all_checks_pass`,
   reporting `2/22` internal checks failing:
   - `_check_characterization_pattern_command_matrix`:
     `codex_yes_proceed on current_command='node': expected kind
     'codex_yes_proceed', got ''`
   - `_check_scoping_provenance_is_reported`:
     `an unresolved pane must NOT report itself as scoped`

   **Not a regression from the recent prompt-pattern work.** Bisected: the same
   two checks fail at `4166f92f1~1` and `66069bf4c~1` (2/21 there), i.e. before
   both t1557's whole-line anchor and t1540's tool-permission anchor. It is
   older than either.

## Approach

Treat each as its own diagnosis — they are unrelated areas that happen to be red
at once. For each: establish when it started failing (`git bisect` or a spot
check at a few commits), decide whether the **production** rule or the **test's
expectation** is wrong, and fix the one that is. Two of the three are guards
whose negative control has stopped firing, so "make the test pass" is the wrong
instinct: confirm the production behaviour is what the guard was written to
protect before touching the assertion.

## Verification

```bash
bash tests/run_all_python_tests.sh    # read the LAST line; expect PASSED
```

Each fix should also be checked with its own pre-fix control — revert the fix
and watch the specific assertion fail — so the repair is evidenced, not assumed.
