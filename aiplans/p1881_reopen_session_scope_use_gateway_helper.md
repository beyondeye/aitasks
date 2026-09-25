---
Task: t1881_reopen_session_scope_use_gateway_helper.md
Base branch: main
Output branch: main
---

# t1881 — agent_reopen: use the gateway's session-scope helper

## Context

t1874 added `tmux_exec.session_scope_target()` (wrapped by
`agent_launch_utils.tmux_session_scope_target()`), which emits `=<s>:`, and
documented the rule in `aidocs/framework/tmux_gateway.md` ("Target
formatting"). t1847 shipped `.aitask-scripts/lib/agent_reopen.py` with a private
`_session_scope(session)` returning `tmux_window_target(session, "")`. The value
is the same (`=<s>:`), but the rule is defined twice. This task removes the
second definition.

## Steps

1. **`.aitask-scripts/lib/agent_reopen.py`**
   - Import `tmux_session_scope_target` from `agent_launch_utils` (the existing
     import block, line ~108). Keep `tmux_window_target` because it is still used
     by the `new-window` call sites (~449, ~544). Those targets are window-typed
     destinations, so they are out of scope.
   - Delete `_session_scope()` (~276-285). Keep its rationale as a pointer only:
     add a one-line comment in `_lookup`'s `list-panes -s` call, e.g.
     `# =<s>: not =<s> — see "Target formatting" in aidocs/framework/tmux_gateway.md`.
     This puts the pointer where the hazard is without restating the rule.
   - `list-panes -s` (~313): `_session_scope(session)` →
     `tmux_session_scope_target(session)`.
   - `list-windows` (~376): **use the scope helper here as well.** This is a
     deliberate choice and the commit body will say so. `list-windows` is
     session-typed, so `=<s>:` resolves to the session exactly as `=<s>` would.
     One helper then covers every session-scoped read in the module.
     `tests/test_agent_reopen.py::test_session_scoped_reads_use_an_unambiguous_target`
     and its fake tmux already pin `=S:` for both verbs. Switching to
     `session_target` would mean loosening that contract with no benefit.
   - Confirm with the word-bounded grep under Verification that no calls to the old `_session_scope(` are left.

2. **`tests/test_frozen_reopen_live.sh`: keep the collision demo and add the
   safe form next to it.** The raw `list-panes -s -t "=C"` (line 204) and `"=B"`
   (line 225) are deliberate **preconditions**. They prove the bare form
   resolves to A's panes ("the t1874 shape"), which keeps c2/c3 non-vacuous, so
   they stay as they are. The task's request is met by adding, right after each
   one, an assertion that the safe form selects the intended session from the
   same client in A (sessions B and C exist, lines 111-112):
   ```bash
   seen="$(in_a "$REAL_TMUX" list-panes -s -t "=C:" -F '#{session_name}' | sort -u)"
   assert_eq "c2: from A, the scoped =C: lists C's panes" "C" "$seen"
   ```
   and the same for `=B:` → `B` in c3. Together, each pair shows the hazard and
   the fix in the same environment.

## Verification

- `python3 -m pytest tests/test_agent_reopen.py -q` (or run the file directly
  under unittest).
- `bash tests/test_frozen_reopen_live.sh`
- `grep -nE '(^|[^a-z_])_session_scope\(' .aitask-scripts/lib/agent_reopen.py` → no hits (word-bounded: `_session_scope` is a substring of `tmux_session_scope_target`).
- The new live assertions pass, and the existing bare-form preconditions still
  read `A`.

Commit: `refactor: Use the gateway session-scope helper in agent_reopen (t1881)`.
Then Step 9 (Post-Implementation): archive the task and push via `./ait git`.

## Risk

### Code-health risk: low
None identified. The change swaps one helper for another that emits the same value, in one module, and the unit test pins the emitted target.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Removed `_session_scope()` from `.aitask-scripts/lib/agent_reopen.py`. Both session-scoped reads (`list-panes -s` in `_find_by_window_name`, `list-windows` in `_final_name`) now call `agent_launch_utils.tmux_session_scope_target()`, with a one-line pointer comment to `tmux_gateway.md` "Target formatting" at the `list-panes -s` call. In `tests/test_frozen_reopen_live.sh`, the bare-form preconditions in c2/c3 were kept, and a new assertion follows each one proving that `=C:` / `=B:` from the same client in A selects C / B.
- **Deviations from plan:** None. The line numbers had shifted by about 25 because t1875 (18f2e98b1) landed on `main` mid-session; the call sites themselves were unchanged.
- **Issues encountered:** None. `test_agent_reopen.py` passed 52/52 and `test_frozen_reopen_live.sh` passed 148/148.
- **Key decisions:** `list-windows` uses the scope helper instead of `tmux_session_target`. That gives one helper for every session-scoped read in the module, and the unit test's fake tmux already pins `=S:` for both verbs. The task's request to "switch the live test's `=C` to `=C:`" was met by adding the safe form next to the bare form, because the bare-form query is a deliberate precondition that shows the hazard is real.
- **Upstream defects identified:** None
