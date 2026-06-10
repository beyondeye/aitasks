---
Task: t672_revisit_brainstorm_status_distrust_after_t671.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: t672 — Revisit brainstorm status-distrust after t671

## Context

t671 made `<agent>_status.yaml: status` a trustworthy, agent-self-reported
terminal lifecycle: the runner no longer flips Running → MissedHeartbeat →
Error on stale heartbeats. With `status` now trustworthy, the brainstorm
initializer flow carries a workaround that no longer earns its keep.

When the initializer agent reports **Error/Aborted**, `_poll_initializer`
currently *distrusts* that terminal status: instead of stopping, it swaps the
fast 2 s poll timer for a slower **30 s "slow-watcher"** that keeps re-polling
in case the agent writes a late `initializer_bootstrap_output.md`. Post-t671 an
Error/Aborted status genuinely means the agent has terminated and will not
resume, so the indefinite 30 s watcher is dead weight (a forever-running timer
on a terminal state).

The blocker that paused this task in the 2026-05-20 planning session — t741's
live WIP in both files — has cleared: **t741 is committed and archived**
(`0a1c98f1e`, `86c9e9319`) and both target files are clean in the working tree.

This task carries two candidates. **Candidate 1 is implemented; Candidate 2 is
kept as-is** (see "Decision on Candidate 2" below).

## Candidate 1 — Drop the slow-watcher (IMPLEMENT)

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`, `_poll_initializer`,
the `elif status in ("Error", "Aborted"):` branch (currently ~lines 8543–8557).

**Current behaviour:**
```python
elif status in ("Error", "Aborted"):
    # Don't permanently stop — the agent may still write _output.md
    # later. Stop the fast 2 s timer; install a slower 30 s watcher
    # so a late-arriving output is still applied.
    if self._initializer_timer is not None:
        self._initializer_timer.stop()
    self._initializer_timer = self.set_interval(30, self._poll_initializer)
    self.notify(
        f"Initializer agent {status.lower()}. "
        f"Watching for output; press ctrl+r or run "
        f"`ait brainstorm apply-initializer {self.task_num}` to retry.",
        severity="error",
    )
    self._load_existing_session()
    self._try_apply_initializer_if_needed()
```

**New behaviour** — treat Error/Aborted as the genuine terminal state it now
is. Stop polling for good (no 30 s reinstall), mark the initializer done, and
keep exactly one best-effort apply attempt plus the manual ctrl+r retry:
```python
elif status in ("Error", "Aborted"):
    # Post-t671, Error/Aborted is the agent's own trustworthy terminal
    # status — it will not resume, so there is no late output to wait
    # for. Stop polling permanently. Make one best-effort apply attempt
    # in case the agent emitted a complete output before failing
    # (n000_needs_apply gates on the four delimiters); ctrl+r still
    # forces a manual retry afterwards.
    self._initializer_done = True
    if self._initializer_timer is not None:
        self._initializer_timer.stop()
    try:
        self.query_one(
            "#initializer_polling_indicator", PollingIndicator
        ).stop()
    except Exception:
        pass
    self.notify(
        f"Initializer agent {status.lower()}. "
        f"Press ctrl+r or run "
        f"`ait brainstorm apply-initializer {self.task_num}` to retry.",
        severity="error",
    )
    self._load_existing_session()
    self._try_apply_initializer_if_needed()
```

Key points:
- **`self._initializer_done = True`** — guards the function so any in-flight
  timer tick is a no-op; matches the `Completed` branch's terminal semantics.
- **No `set_interval(30, …)`** — the watcher is gone; the timer is stopped and
  not reinstalled.
- **Stop `#initializer_polling_indicator`** — the `Completed` branch already
  does this; the old Error branch left it flashing because it kept watching.
  Now that the branch is terminal, stop it too (wrapped in try/except like the
  Completed branch).
- **Keep `_load_existing_session()` + `_try_apply_initializer_if_needed()`** —
  the one-shot belt-and-suspenders: if the agent wrote a complete delimited
  output before erroring, `n000_needs_apply` returns True and the apply still
  lands.
- **ctrl+r manual retry preserved automatically** — it is `action_retry_initializer_apply`
  (brainstorm_app.py ~4810) → `_try_apply_initializer_if_needed(force=True)`,
  untouched by this change. The notify wording drops the now-false "Watching
  for output;" clause but keeps the ctrl+r / CLI retry guidance.

## Decision on Candidate 2 — Keep `n000_needs_apply` as-is (NO CHANGE)

**File:** `.aitask-scripts/brainstorm/brainstorm_session.py`, `n000_needs_apply`
(~line 408).

The four-delimiter gate (`NODE_YAML_START/END`, `PROPOSAL_START/END`) is **not**
a status-distrust workaround — it is a genuine *content-completeness* guard. Its
docstring already documents the real reasons it exists, with no t653_1/t670
distrust framing to clean up:
- it rejects the placeholder `initializer_bootstrap_output.md` that
  `aitask_crew_addwork.sh` writes at agent-registration time (before the agent
  runs), and
- it rejects mid-stream partial writes where only some delimiters exist yet.

A `status == "Completed"` gate would **not** catch a Completed-but-malformed or
Completed-but-placeholder output, so switching to it would be a regression, not
a simplification. The function is also covered by 7 tests from t670
(`tests/test_brainstorm_session.py`). **Leave it untouched.**

A grep confirms the only distrust-framing comment in either file is the
slow-watcher comment being rewritten in Candidate 1; `n000_needs_apply` needs no
comment edit. So the task's step 3 ("drop t653_1/t670 distrust framing") is
fully satisfied by the Candidate 1 comment rewrite alone.

## Files Modified

- `.aitask-scripts/brainstorm/brainstorm_app.py` — rewrite the Error/Aborted
  branch of `_poll_initializer` (only change).

No other files change. No test changes: no existing test asserts the 30 s
slow-watcher reinstall, and the kept `n000_needs_apply` tests stay green.

## Verification

1. **Targeted regression suites (must stay green):**
   ```bash
   python3 tests/test_brainstorm_session.py          # 7 n000_needs_apply tests
   bash   tests/test_apply_initializer_output.sh
   bash   tests/test_apply_initializer_tolerant.sh
   ```
2. **Lint / syntax:**
   ```bash
   python3 -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py
   ```
3. **Static confirmation the watcher is gone:**
   ```bash
   grep -n "set_interval(30, self._poll_initializer)" \
     .aitask-scripts/brainstorm/brainstorm_app.py   # expect: no matches
   ```
4. **Manual (optional — TUI, hard to automate):** Launch a brainstorm session
   whose initializer agent fails; confirm the polling indicator stops, the
   error toast no longer says "Watching for output", and ctrl+r still forces an
   apply retry. (Noted as manual because the Textual timer interaction is not
   unit-testable without a live crew worktree.)

## Step 9 (Post-Implementation)

Single-file, single-branch change on `main`. After approval + review: commit
with `refactor: <desc> (t672)`, update/consolidate the plan, then archive via
`./.aitask-scripts/aitask_archive.sh 672` and push.

## Risk

Assessed on two dimensions independently.

- **Code-health risk: Low.** The change is confined to one branch of one
  method; it *removes* state (an indefinitely-running timer) rather than adding
  any. It aligns the Error/Aborted branch with the existing `Completed` branch's
  terminal pattern (`_initializer_done = True`, stop timer, stop indicator). No
  new abstractions, no API changes, no dependency on the kept Candidate 2 code.
- **Goal-achievement risk: Low.** The decision was already reached and
  documented in the task's 2026-05-20 planning session and re-confirmed by this
  exploration. The one-shot apply attempt + ctrl+r retry preserve the only
  realistic recovery path (agent wrote complete output before failing), so the
  removed 30 s loop has no behavioural value to lose post-t671.

### Planned mitigations

None. Both dimensions are Low; the kept one-shot apply + manual ctrl+r retry are
themselves the defensive fallback, and no before/after mitigation task is
warranted.
