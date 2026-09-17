---
Task: t1767_share_the_freezeall_eligibility_rule_between_listing_and_mut.md
Base branch: main
Output branch: main
---

# t1767 — Share the Freeze-All eligibility rule between listing and mutation

## Context

`agent_freeze.freeze_all_eligible()` (`.aitask-scripts/lib/agent_freeze.py:696`)
says it is THE eligibility rule, used by both the `--dry-run` listing and the
mutation. But `freeze_all()` (`:727`) never calls it: it has its own copy of the
session-discovery loop and both filters (`category == AGENT`,
`not pane.frozen_record`). The two copies agree today. The risk is that a later
edit changes one and not the other. Then the confirmation count `Z` shown in both
monitor TUIs (taken from the helper) would no longer match what the freeze
actually does.

Constraint: the two functions must keep handling a session that vanishes
mid-scan differently. `freeze_all()` **reports** it as
`FREEZE_FAILED:resolve|<session>|<exc>`. `freeze_all_eligible()` **skips** it.
Share the *selection* and keep that difference.

Constraint I'm adding: keep `freeze_all()`'s current per-session order. It
scans a session and freezes that session's panes before it scans the next one.
Its selection therefore stays lazy, not a list built up front.

## Implementation

### 1. `.aitask-scripts/lib/agent_freeze.py` — one shared per-session selector

Add a generator above `freeze_all_eligible()` (import `Iterator` from
`collections.abc`):

```python
def _eligible_by_session() -> Iterator[tuple[str, list | None, Exception | None]]:
    """THE Freeze-All eligibility rule: ``(session, eligible_panes, error)`` per session.

    Yields lazily, one session at a time, so `freeze_all` still freezes a
    session's panes before scanning the next. A session that vanished mid-scan
    yields ``(session, None, exc)``; what to do with that is the CALLER's
    policy — a listing skips it, a mutation reports it.
    """
    for session in discover_aitasks_sessions():
        try:
            panes = _agent_panes_for(session.session)
        except Exception as exc:   # a session that vanished mid-scan
            yield session.session, None, exc
            continue
        yield session.session, [
            pane for pane in panes
            if pane.category == PaneCategory.AGENT
            and not pane.frozen_record          # already a stand-in
        ], None
```

- `freeze_all_eligible()`: keep its docstring. Reword it so it points to the
  shared generator as where the rule lives, and note that it skips vanished
  sessions. Body:
  ```python
  eligible = []
  for _session, panes, error in _eligible_by_session():
      if error is None:
          eligible.extend(panes)
  return eligible
  ```
- `freeze_all()`: keep its docstring, which already explains the reporting
  difference. Body:
  ```python
  results = []
  for session, panes, error in _eligible_by_session():
      if error is not None:
          results.append(FreezeResult("", False, "resolve",
                         f"FREEZE_FAILED:resolve|{session}|{error}"))
          continue
      for pane in panes:
          results.append(freeze_pane(pane.pane_id))
  return results
  ```
- Leave the `main()` dry-run comment ("Reuses `freeze_all`'s OWN eligibility
  rule") as it is. It is now accurate.

### 2. `tests/test_freeze_argument_grammar.py` — pin the mutation to the shared rule

Existing test `test_the_listing_reuses_freeze_alls_own_eligibility_rule` only
checks the listing side. `_GrammarCase.setUp` patches `freeze_all` with a spy, so
capture the real function at import time: `_REAL_FREEZE_ALL = agent_freeze.freeze_all`.
Add a class `SharedSelectionTests(_GrammarCase)`:

1. **`test_freeze_all_acts_on_exactly_the_eligible_listing`**: call
   `_REAL_FREEZE_ALL()` against the fake two-session fixture. The frozen pane ids
   must equal `[p.pane_id for p in freeze_all_eligible()]` (`["%1","%2","%9"]`).
2. **`test_both_callers_read_the_one_selector`** (anti-drift pin): patch
   `_eligible_by_session` with a fake that yields a selection the real filters
   would never produce: `("aitasks", [%4 TUI pane], None)` plus
   `("gone", None, OSError("vanished"))`. Then check:
   - `freeze_all_eligible()` returns `["%4"]`
   - `_REAL_FREEZE_ALL()` freezes exactly `["%4"]` and returns a
     `FREEZE_FAILED:resolve|gone|vanished` line
   A mutation that keeps its own copy of the filters fails this test.
3. **`test_freeze_all_still_scans_lazily_per_session`**: wrap `_agent_panes_for`
   to log `("scan", s)` and `freeze_pane` to log `("freeze", id)`. Assert the
   `aitasks` freezes come before `("scan", "otherproj")`.
4. **`test_a_vanished_session_is_reported_by_the_mutation`**: `_agent_panes_for`
   raises for `aitasks`. `_REAL_FREEZE_ALL()` returns a
   `FREEZE_FAILED:resolve|aitasks|…` result and still freezes `%9`. The listing
   case already exists in `DryRunTests`.

**No temporary pre-fix control.** Stashing or reverting `agent_freeze.py` just
to watch test 2 fail would mutate the checkout that concurrent sessions share on
`main`. It could capture unrelated work or restore imprecisely. Test 2 already
states the regression it guards against: its fake selector yields a pane that
the real filters would reject. A mutation with its own copy of the filters would
not freeze that pane, so the test would fail. The durable suite is the
verification.

## Verification

- `python3 tests/test_freeze_argument_grammar.py`
- `python3 tests/test_agent_freeze.py` (includes
  `test_already_frozen_and_non_agent_panes_are_skipped`, which drives `freeze_all()`)
- `python3 tests/test_monitor_frozen_filter.py`
- `bash tests/run_all_python_tests.sh --test-dir tests` is optional. Read only
  the last line for the verdict.

## Step 9 (Post-Implementation)

Current-branch mode (profile fast): commit `refactor: … (t1767)`, then plan
commit, archive via `aitask_archive.sh 1767`, push.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Added `_eligible_by_session()` to `.aitask-scripts/lib/agent_freeze.py`. It is a lazy generator that yields `(session, eligible_panes, error)` for each aitasks session and holds the discovery loop plus both filters. `freeze_all_eligible()` now flattens it and skips errored sessions. `freeze_all()` iterates it, reports errored sessions as `FREEZE_FAILED:resolve|<session>|<exc>` and freezes each eligible pane. Added `SharedSelectionTests` (4 tests) to `tests/test_freeze_argument_grammar.py`:
  - the mutation acts on exactly the listed panes
  - both callers read the one selector (a fake selector yields a TUI pane that the real filters would reject)
  - per-session laziness is preserved
  - the mutation still reports a vanished session
- **Deviations from plan:** None. At plan review the temporary pre-fix control was removed, so the checkout shared on `main` is never mutated.
- **Issues encountered:** None. The grammar, agent_freeze and monitor_frozen_filter suites all pass (15 / 99 / 71 tests).
- **Key decisions:** A generator instead of a precomputed list, so `freeze_all` keeps its interleaved scan-then-freeze order per session. The vanished-session policy stays with each caller rather than living in the selector.
- **Upstream defects identified:** None
