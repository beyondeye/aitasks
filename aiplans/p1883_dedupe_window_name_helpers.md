---
Task: t1883_dedupe_window_name_helpers.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1883 — Dedupe the window-name tmux helpers of restore and reopen

## Context

t1875 gave `lib/agent_restore.py` local twins of three tmux primitives that
already live in `lib/agent_reopen.py`, because `agent_reopen` imports
`agent_restore` (so restore cannot import reopen). The twins are:

| restore (t1875)                                 | reopen                   |
|-------------------------------------------------|--------------------------|
| `_find_attempt_pane`                            | `_find_by_window_name`   |
| `_kill_window_if` / `_kill_if_named`            | `_kill_if_named`         |
| `_rename_if_stamped`                            | `_rename` (its dispatch + re-read) |
| `_attempt_facts` (4 fields: pane_id, window, frozen, mark) | `_facts` (6 fields: pane_id, pane_pid, session, window, window_id, frozen) |

The fix moves the tmux logic into `lib/agent_frozen_ops.py`, which both
coordinators already import as `frozen_ops`. Each coordinator keeps its own
seam checks (`AITASKS_RESTORE_FAIL_AT` / `AITASKS_REOPEN_FAIL_AT`) in thin
wrappers. Behaviour stays the same, and the existing tests pass unchanged.

## Findings that shape the design

- Both test fakes (`tests/test_agent_reopen.py`, and the rendering fake used by
  the gone-pane tests in `tests/test_agent_restore.py`) render any `#{…}` key
  from a pane dict. A missing key renders as `""`, so a 7-field unified read
  parses in both. The arity-scripted `_ScriptedTmux` never scripts arity 4 or 6,
  so it never reaches these reads. No other test module scripts them (checked:
  `test_agent_freeze.py`, `test_agent_frozen_ops.py`, `test_frozen_restore_verdict.py`).
  `PANE_FACT_FORMAT` / `PROBE_PANE_FORMAT` stay as they are.
- `tmux_exec.session_scope_target(session)` already returns `=<session>:`,
  the same string as `tmux_window_target(session, "")` and reopen's
  `_session_scope`. It is a pure function, so frozen_ops can import it by name.
- The two named-kills differ only in how they label a failed kill. Reopen
  returns `name-mismatch` when the window survived under another name.
  Restore always returns `kill-failed`. That label ends up in restore's
  `RESTORE_FAILED` cleanup suffix, so it is observable behaviour. Each
  coordinator keeps its own label; only the tmux dispatch and reads are shared.
  Today no test asserts either label, so step 4b adds a pin for each.
- The two renames differ. Reopen checks first that the stamp matches and skips
  the rename when the window already has the final name, and it has a `rename`
  seam. Restore always dispatches. The shared primitive is the part they have
  in common: the guarded dispatch plus a verifying re-read. Reopen's pre-check
  stays in its wrapper, so restore's call sequence does not change.
- Restore's `_survivor_refusal` calls `_kill_window_if(..., seam=False)` with a
  `pane_dead && claim` condition. That becomes a direct call to the shared
  `kill_window_if`, which needs no seam flag.

## Implementation steps

1. **`agent_frozen_ops.py`: add a "window-name primitives" section** after the
   restore-attempt/survivor helpers (near `clear_stamp_if`), with a short
   comment saying restore and reopen both use it (t1883):
   - Import `session_scope_target` from `tmux_exec`, next to `TmuxClient`.
   - `WINDOW_FACT_FORMAT` / `WINDOW_FACT_KEYS` hold the union of both reads:
     `("pane_id", "pane_pid", "session", "window", "window_id", "frozen", "mark")`,
     using `#{pane_id}`, `#{pane_pid}`, `#{session_name}`, `#{window_name}`,
     `#{window_id}`, `#{@aitask_frozen…}` (FROZEN_OPTION) and
     `#{RESTORE_ATTEMPT_OPTION}`.
   - `window_facts(pane_id) -> dict | None` has the same body as reopen's
     `_facts`: `None` when tmux is unreachable, `{}` when the pane is gone or the
     row is malformed.
   - `find_pane_by_window_name(session, name) -> (verdict, pane_id, pane_pid)`
     has the same body as reopen's `_find_by_window_name`, minus the seam, using
     `session_scope_target(session)`. It returns `found` / `none` / `unknown`, and
     returns `unknown` for more than one hit.
   - `window_name_condition(name) -> str` returns `#{==:#{window_name},<name>}`.
     Both coordinators use it, so the condition string is written in one place.
   - `kill_window_read(pane_id, condition) -> (verdict, reason, after)` carries
     the tmux work that both kills share: a before-read, one `if-shell -F`
     dispatch, then an after-read. It returns `gone/pane-gone`, `gone/""`,
     `unknown/tmux unreachable`, or `present/kill-failed`. For a present window
     it also returns the after-read facts, so a caller can label the failure
     without another tmux call.
   - `kill_window_if(pane_id, condition) -> (verdict, reason)` is
     `kill_window_read` without the facts. Its labels are exactly those of
     restore's current `_kill_window_if`: a present window is always
     `kill-failed`.
   - **The reason label stays with each caller, not in the shared code.** The
     name-mismatch refinement is reopen behaviour, so it stays in reopen's
     wrapper (step 3). Restore's wrapper uses `kill_window_if`, so it keeps
     `kill-failed` in the rename race. The tmux call sequence stays exactly as
     it is now for both callers.
   - `rename_window_if_stamped(pane_id, record_id, final, *, dispatch=True) -> bool`
     is the guarded `if-shell` on `FROZEN_OPTION == record_id` →
     `rename-window -t <pane> <tmux_quote(final)>`, skipped when not `dispatch`,
     then a verifying `window_facts` re-read (`after.window == final`).
   - Every helper calls `run(...)` / `window_facts(...)` as module globals, so
     the `_TMUX` swap in the tests still reaches them.
   - In the module docstring, add one line to the constants list saying
     `WINDOW_FACT_FORMAT` / `WINDOW_FACT_KEYS` can also be imported by name.

2. **`agent_restore.py`:**
   - Delete `_ATTEMPT_FACTS_FORMAT`, `_ATTEMPT_FACTS_KEYS`, `_attempt_facts` and
     `_kill_window_if`.
   - `_find_attempt_pane` keeps only its `lookup` seam check, then returns
     `frozen_ops.find_pane_by_window_name(session, name)`.
   - `_kill_if_named` keeps only its `cleanup` seam check, then returns
     `frozen_ops.kill_window_if(pane_id, frozen_ops.window_name_condition(name))`.
     A surviving window is labelled `kill-failed` even if it was renamed,
     exactly as today.
   - Delete `_rename_if_stamped`, and call
     `frozen_ops.rename_window_if_stamped(pane_id, record_id, final)` in
     `_launch_into_new_window`. Restore has no rename seam, so there is no wrapper.
   - In `_launch_into_new_window`, the step-3 read becomes
     `frozen_ops.window_facts(pane_id)`.
   - In `_survivor_refusal`, call `frozen_ops.kill_window_if(hit["pane_id"], …)`
     (it never had a seam).
   - Rewrite the "three tmux primitives below are twins…" comment: they are
     now shared in `agent_frozen_ops`, and only the seams stay local.

3. **`agent_reopen.py`:**
   - Delete `_FACTS_FORMAT`, `_FACTS_KEYS` and `_facts`. Every `_facts(`
     call (in `_final_name`, `_commit`, `_fresh`, `_adopt`, `_rename`) becomes
     `frozen_ops.window_facts(`.
   - `_find_by_window_name` becomes its `lookup` seam check plus the shared call.
   - `_kill_if_named` keeps its `cleanup` seam check, then calls
     `verdict, reason, after = frozen_ops.kill_window_read(pane_id, frozen_ops.window_name_condition(name))`.
     When the verdict is `present`, it returns
     `"kill-failed" if after["window"] == name else "name-mismatch"`, which is
     reopen's current label. Otherwise it returns `(verdict, reason)` unchanged.
   - `_rename` keeps its stamp and already-named pre-check, then returns
     `frozen_ops.rename_window_if_stamped(pane_id, record_id, final, dispatch=not _seam("rename"))`.
   - `_session_scope` stays unchanged, because `_final_name` still uses it.
     Its docstring's reason is the t1874 note, which is still accurate.

4. **`tests/test_agent_frozen_ops.py`: add direct unit tests for the new
   primitives** with a small rendering fake (a pane dict per `%N`, as in
   `test_agent_reopen.py`):
   - `window_facts`: unreachable → `None`; a gone pane (rc 1, or rc 0 with an
     empty row) → `{}`; a present pane → all 7 keys.
   - `find_pane_by_window_name`: found / none / unknown (unreachable, two hits,
     non-int pid). Assert the `-t` argument is `=<s>:`.
   - `kill_window_read` / `kill_window_if`: gone before → `gone/pane-gone`;
     the condition fires → `gone`; the kill does not take →
     `present/kill-failed`; the window is renamed between the before-read and
     the dispatch → `present/kill-failed`, with `after["window"]` holding the
     new name; unreachable → `unknown`.

4b. **Pin each coordinator's label in the rename race** by adding one test to
   each existing suite. The existing tests are not edited.
   - `tests/test_agent_restore.py`: a gone-pane launch under
     `AITASKS_RESTORE_FAIL_AT=stamp`. The fake's `after` hook renames the
     attempt window right after the cleanup kill's before-read, so the
     name-guarded `if-shell` does not fire. Assert that the error ends with
     `stamp|cleanup:present:kill-failed|pane:<id>`, which is the pre-refactor
     label.
   - `tests/test_agent_reopen.py`: the same race in `_fresh`'s cleanup kill,
     using the `stamp` seam and a rename in the same slot. Assert
     `cleanup:present:name-mismatch`.
   - Before the refactor, run both new tests against the current code, so they
     are shown to pin today's behaviour rather than the new code's.
   - `rename_window_if_stamped`: stamped → renamed and True; unstamped →
     False; `dispatch=False` → no `if-shell` issued.

5. **Step 9 (Post-Implementation)**: archival, per the shared workflow.

## Verification

- `python3 tests/test_agent_frozen_ops.py` (new tests, plus the existing
  seam-rule test that forbids an import-aliased `store` / `_TMUX`)
- `python3 tests/test_agent_reopen.py` and `python3 tests/test_agent_restore.py`,
  unchanged, must pass
- `bash tests/test_frozen_reopen_live.sh` (real tmux; covers both the reopen
  and the restore gone-pane flows)
- As a spot check, `python3 tests/test_agent_freeze.py` and
  `python3 tests/test_frozen_restore_verdict.py` (both import frozen_ops)
- `grep -n "_attempt_facts\|_FACTS_FORMAT\|_kill_window_if" .aitask-scripts/lib/agent_re*.py`
  must print nothing

## Risk

### Code-health risk: low
- If the shared kill decided the label, each coordinator's reason in the
  rename race would drift, and restore's label reaches its `RESTORE_FAILED`
  output. The design keeps the label in each coordinator's wrapper, and step 4b
  pins both labels, proving each against the pre-refactor code. · severity:
  low (residual) · → mitigation: none needed beyond steps 3–4b
- The unified 7-field `display-message` read changes the argv that restore's
  attempt reads send. I checked every test fake that could see it: they either
  render by key or never script that arity. · severity: low · → mitigation:
  none (verified during planning; the unchanged test suites pin it)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Added a "window-name primitives (t1883)" section to `lib/agent_frozen_ops.py`: `WINDOW_FACT_FORMAT`/`WINDOW_FACT_KEYS` (7 fields, the union of reopen's `_facts` and restore's `_attempt_facts`), `window_facts`, `find_pane_by_window_name`, `window_name_condition`, `kill_window_read` (returns the after-read facts of a surviving window), `kill_window_if`, and `rename_window_if_stamped(..., dispatch=)`. `agent_restore.py` lost `_ATTEMPT_FACTS_*`, `_attempt_facts`, `_kill_window_if`, `_rename_if_stamped`; `_find_attempt_pane` / `_kill_if_named` are seam-only wrappers, `_survivor_refusal` calls `frozen_ops.kill_window_if` directly. `agent_reopen.py` lost `_FACTS_*` / `_facts`; `_find_by_window_name` is a seam wrapper, `_kill_if_named` applies its own `kill-failed` / `name-mismatch` label from `kill_window_read`'s after-read, `_rename` keeps its stamp/already-named pre-check and delegates the dispatch + verify.
- **Deviations from plan:** Step 3's note about keeping `_session_scope` became moot — t1881 (landed on main mid-session) had already replaced it with `tmux_session_scope_target`; the refactor was applied on top of that version. The t1881 "Target formatting" gateway-doc pointer was carried into the shared lookup.
- **Issues encountered:** One scripted `_facts(` → `frozen_ops.window_facts(` replacement double-prefixed the line inside the new `_rename`; caught by review of the diff and fixed before tests ran. `tests/test_restore_flows_live.sh` refuses to run on a box with a live tmux server (needs `AIT_LIVE_TMUX_TEST_FORCE=1` on a dedicated box) and was not run.
- **Key decisions:** Per the plan review, the reason label of a surviving window is owned by each coordinator, not the shared kill: restore stays `kill-failed` in the rename race (it reaches `RESTORE_FAILED`), reopen stays `name-mismatch`. Both are pinned by new tests (`test_a_kill_raced_by_a_rename_is_labelled_kill_failed` / `..._name_mismatch`), each proven green against the pre-refactor code first. The new primitives are also listed in `test_agent_frozen_ops.py`'s promised-surface contract and have direct unit tests (`WindowNamePrimitiveTests`).
- **Upstream defects identified:** None
