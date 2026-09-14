---
Task: t1763_fix_three_pre_existing_python_suite_failures.md
Base branch: main
Output branch: main
---

# t1763 — Fix the standing-red Python suite failures

## Context

`bash tests/run_all_python_tests.sh` has been red on `main` independently of any
in-flight work, so its verdict line — the signal the task workflow reads before
archival — carries no information. t1763 lists three failing modules; t1754
(folded into this task, commit `9a8167069`) describes the same three with extra
bisect data. Diagnosed on this box (macOS, CPython 3.13.13, `runner=unittest` —
no pytest dev tier installed) at HEAD `734609846`.

## Findings (one root cause per module)

1. **`tests/test_desync_state.py` — already fixed, no change.** The missing
   `stale_lock.sh` in the fixture copy-list was repaired by `13e5b3d78` (t1745),
   which derives the startup-source closure instead of hand-listing it. Verified
   here: 10 tests, OK.

2. **`tests/test_prompt_detection.py` — host-dependent fixture.** `make_pane()`
   hard-codes `pane_pid=1`. For a command that does not name an agent (`node`,
   `python`), `agent_key_from_pane()` (`.aitask-scripts/lib/agent_keys.py:139`)
   falls to its second rung and scans the **children of PID 1** — `launchd` on
   macOS, i.e. much of the machine. When exactly one distinct agent is running as
   a direct launchd child at that moment, the synthetic pane resolves to it: a
   `node` pane is scoped to `claude` (so `codex_yes_proceed` yields `''`) and a
   `python` pane reports `scoped=True`. The positive result is then cached for the
   process lifetime (`_PANE_KEY_CACHE`), so in a suite run the first resolution
   sticks. That is why it passes standalone today yet failed in t1773's full run
   on this same host.
   **Proven deterministically:** faking one `claude` child of PID 1 reproduces
   *both* recorded messages verbatim; the same fake with `pane_pid=0` passes.
   A falsy pid is the designed "no second rung" value (`monitor_core.py` ~L629,
   t1509), so `0` is the correct fixture value, not a workaround.

3. **`tests/test_concern_parser.py` — runner-dependent negative control.**
   `TestProducerPlainWordsRule.test_production_assertion_fails_on_a_real_offender`
   wraps `test_no_producer_example_block_carries_a_prose_only_line()` in
   `assertRaises(AssertionError)`, but that method asserts inside
   `self.subTest(...)`. Under unittest the subTest context *records* the failure
   against the enclosing test instead of raising it, so `assertRaises` sees
   nothing and the control fails (twice: once as the leaked subTest, once as
   "AssertionError not raised"). pytest propagates, which is why the two runners
   disagree on the same commit (t1745/t1771 notes). The production rule itself is
   fine. Audit: of the 7 negative controls in `tests/` that call a production
   `test_*` method under `assertRaises`, this is the **only** target using
   `subTest` — nothing else to file.

## Implementation steps

1. **`tests/test_prompt_detection.py` — `make_pane()`** (~L55): change
   `pane_pid=1` to `pane_pid=0`, with a comment: a real pid sends unresolved
   commands to `agent_key_from_pane`'s second rung, which scans that pid's
   children on the host; `0` is the documented "no pid" value (t1509), so fixture
   panes resolve from `current_command` alone.

2. **`tests/test_prompt_detection.py` — new regression check**
   `_check_fixture_is_isolated_from_host_process_table()`, registered in
   `main()`'s `tests` list right after `_check_scoping_provenance_is_reported`:
   - add `agent_key_from_pane` to the existing `from monitor.prompt_patterns
     import (...)`; resolve the module to patch as
     `sys.modules[agent_key_from_pane.__module__]` (it imports top-level as
     `agent_keys`; verified to be the same object `monitor_core` uses);
   - clear `_PANE_KEY_CACHE` and `_PANE_MISS_CACHE` (a cached miss returns `""`
     without consulting `_child_commands`, which would make the check pass
     vacuously), replace `_child_commands` with `lambda pid: ["claude"]`, run
     `_check_characterization_pattern_command_matrix()` and
     `_check_scoping_provenance_is_reported()`, and in `finally` restore
     `_child_commands` and clear both caches again;
   - docstring: simulates the host state under which the suite went red (a lone
     agent process as a child of the fixture's pid) and pins that fixture panes
     are immune to it.

3. **`tests/test_concern_parser.py` —
   `test_no_producer_example_block_carries_a_prose_only_line`** (~L2211): drop the
   per-producer `subTest` and collect offenders the way the sibling
   `test_every_producer_states_the_plain_words_rule` already does:
   ```python
   offenders = [
       f"{name}: {offence}"
       for name, text in self._producers().items()
       for offence in _example_prose_only_offences(text)
   ]
   self.assertEqual(offenders, [], "an example concern-block fence carries a "
                    "prose-only phrase — the example contradicts the prose-only "
                    "rule stated beside it")
   ```
   plus a short comment: no `subTest` here, because the negative control calls
   this method under `assertRaises`, and under unittest a subTest records a
   failure instead of raising it (t1763). The control's `assertIn("leak.md", …)`
   still holds — the offender strings carry the producer name.
   (Dry-run in memory: fix → both tests pass under unittest; fix + neutered
   `_example_prose_only_offences` → the control fails again, so it still guards.)

4. **No change** to `tests/test_desync_state.py` (fixed by t1745),
   `tests/test_idle_compare_modes.py` (`pane_pid=1`, but its command `codex`
   resolves at rung 1, so rung 2 is never reached) or
   `tests/test_agent_freeze.py:1152` (`lib/agent_freeze.py` never resolves agent
   keys).

## Verification

```bash
python3 tests/test_prompt_detection.py; echo "exit=$?"     # 23/23, exit 0
python3 -m unittest tests.test_prompt_detection            # OK
python3 -m unittest tests.test_concern_parser              # OK, 184 tests
python3 tests/test_desync_state.py                         # OK, 10 tests
bash tests/run_all_python_tests.sh; echo "exit=$?"         # read ONLY the last line
```

Pre-fix controls (each must be watched failing, then restored):
- Temporarily set `make_pane`'s `pane_pid` back to `1` → the new isolation check
  FAILS with `codex_yes_proceed on current_command='node': expected kind
  'codex_yes_proceed', got ''` (the two original checks may still pass on this
  host — that is exactly the gap the new check closes). Restore to `0`.
- `test_concern_parser`: the pre-fix state already fails (`failures=2`, observed).
  Post-fix mutation control via a one-off in-memory snippet: patch
  `_example_prose_only_offences` to return `[]` → the negative control must fail.

**Completion gate — the suite verdict must read PASSED.** The task's goal is a
suite verdict that carries information again, so the final
`bash tests/run_all_python_tests.sh` (run after all changes, exit status checked
without a pipe) must end in `PYTHON SUITE: PASSED`. If it does **not**:
- **stop before Step 9 archival** — the task stays `Implementing`; documenting a
  remaining failure or filing a follow-up does **not** satisfy the gate;
- report every remaining failing test concretely (module, test id, assertion
  message), each compared against the pre-change baseline in the session
  scratchpad (`suite_baseline.log`) to show whether it predates this task;
- hand the user a deliberate re-scope decision (extend this task to fix it, or
  explicitly re-scope t1763's goal) — never re-scope implicitly.
The Step 8 code review/commit may still happen (the three fixes are independently
correct); only archival is gated. If anything changes after the gating run, re-run
the suite before archiving.

The pytest lane cannot be exercised here (no dev tier); the concern_parser fix
removes the runner-dependent construct by construction, so both lanes execute
the same assertion path.

## Post-implementation

Step 8: commit as `bug: Fix host-dependent prompt fixture and runner-dependent plain-words control (t1763)`
(code files only), then the plan commit.
Step 9: archival (which deletes folded t1754) and push — **only once the
completion gate above has read `PYTHON SUITE: PASSED`**. Otherwise stop before
archival and report for a re-scope decision.

## Risk

### Code-health risk: low
- Replacing the per-producer `subTest` with an aggregated offender list loses
  per-producer subTest reporting granularity · severity: low · → mitigation: none
  (each offender string names its producer, matching the sibling rule test)

### Goal-achievement risk: low
- The full-suite verdict may still be red for reasons outside these three modules
  · severity: low (the pre-change baseline, read through the `test_concern_*`
  modules so far, shows only the known concern_parser failure) · → mitigation:
  none spawned — the Verification **completion gate** blocks archival unless the
  final run reads `PYTHON SUITE: PASSED`, so an out-of-scope red stalls the task
  for an explicit re-scope decision instead of being archived as done
- The pytest lane cannot be run on this box (no dev tier) · severity: low ·
  → mitigation: none (the concern_parser fix removes the runner-dependent
  construct by construction; both lanes execute the same assertion path)
