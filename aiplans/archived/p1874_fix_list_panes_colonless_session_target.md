---
Task: t1874_fix_list_panes_colonless_session_target.md
Base branch: main
Output branch: main
---

# t1874 — `list-panes -s -t =<s>` resolves to the wrong session

## Context

`list-panes` takes a **window-typed** `-t`, and `-s` then widens to that
window's session. A bare `=<s>` is therefore looked up as a WINDOW name first,
in the client's current session (or, with no client, the most recently used
session). If that session has a window named `<s>`, tmux lists **that
session's** panes. `=<s>:` makes the session part explicit and cannot match a
window.

**What triggered it (now characterized):** the user's tmux config sets
`automatic-rename-format '#{b:pane_current_path}'`, so windows are named after
their cwd basename. In t1869's test, session `other` (created last, so the
"current" one for a clientless call) had cwd `projects/alpha`, which gave it a
window named `alpha`. `=alpha` matched that window. The `/tmp` + `/home` trial
produced windows `tmp`/`home`, so nothing collided. This is realistic in daily
use: a pane in session `aitasks` that `cd`s into `../aitasks_mobile` creates a
window named `aitasks_mobile`. `ait monitor` then maps session `aitasks_mobile`
to `aitasks`'s panes. Freeze reconcile (`agent_freeze._enumerate_session`) is
the most serious consumer: it would record the wrong session's windows as
observed, and its purge drops live records whose windows were not observed.

The same mechanism is already written up in the uncommitted `agent_reopen.py`
(`_session_scope`, owned by in-flight t1847). That file is not touched here.

Session-typed commands (`has-session`, `list-windows`, `set/show-environment`,
`rename-session`, `kill-session`, `switch-client -t target-session`) never
resolve `=<s>` as a window, so they are out of scope. `aitask_companion_cleanup.sh`
targets `#{session_id}` (`$N`), which cannot parse as a window name, so it is
safe as it is.

## Steps

1. **Gateway helper** — `.aitask-scripts/lib/tmux_exec.py`: add
   `session_scope_target(session) -> f"={session}:"`. Its docstring states the
   rule: use it wherever a window/pane-typed `-t` (notably `list-panes -s`)
   must address a whole session, and explain the window-first lookup. Add the
   `TmuxClient.session_scope_target` static re-export next to the existing
   `session_target` / `window_target` ones. Add one sentence to
   `session_target`'s docstring pointing at the new helper.
   `.aitask-scripts/lib/agent_launch_utils.py`: add a
   `tmux_session_scope_target` wrapper next to `tmux_session_target` /
   `tmux_window_target`, following the existing re-export idiom.

2. **Switch every `list-panes -s -t tmux_session_target(...)` site** to the
   scope target:
   - `agent_launch_utils.py`: `_collect_live_roots` (drop the `pane_target`
     parameter so the default and checked walks share one form; remove the
     lambda in `discover_aitasks_sessions_checked`; rewrite the docstring to the
     current rule without "tracked separately"), `discover_aitasks_sessions_async`
     (~1385), and the pid→pane_id lookup (~1895).
   - `agent_freeze.py` `_enumerate_session` (~954). Import the new name next to
     `tmux_session_target` (line 89).
   - `monitor/monitor_core.py` at ~2564, 2586, 2616 and 2637. Import next to
     line 51.
   The `no_such_session` classifier already accepts both `can't find session:`
   and `can't find window:`, and the other callers branch on rc only, so no
   error handling changes. Re-grep afterwards: no `"list-panes", "-s", "-t",
   tmux_session_target(` may remain.

3. **Update tests that pin the old bytes:**
   - `tests/test_discover_async_parity.py:107,111` (`=pane_sess` → `=pane_sess:`, etc.)
   - `tests/test_monitor_refresh_no_sync_tmux.py:225` (`=sessA` → `=sessA:`)
   - `tests/test_discover_checked.py:85-90`: update the comment to the
     characterized cause (window-name match, not a fallback on no match)
   - `tests/test_tmux_exec.py`: unit asserts for `session_scope_target` and
     `TmuxClient.session_scope_target`
   - Test-side raw calls with the same flaw: `tests/test_freeze_engine_live.sh:505`
     and `tests/test_restore_session_bootstrap_live.sh:134` → colon form. The
     substring asserts at `test_freeze_engine_live.sh:563-565,592` still match
     `=<s>:`. Leave `tests/test_frozen_reopen_live.sh` alone because it belongs
     to t1847 and is uncommitted.
   Then grep `tests/` for any other exact `"=<name>"` list-panes pins that
   turned up through `test_multi_session_*` / `test_monitor_*` and fix them.

4. **New deterministic live test** — `tests/test_list_panes_session_scope_live.sh`,
   self-contained, using a private server with its own `TMUX_TMPDIR` and
   `AITASKS_TMUX_SOCKET` (same scaffold as `tests/test_project_resolve.sh`
   ~100-110 and test 14). Skip if tmux is absent.
   - Fixture: `new-session -d -s alpha -n main -c <projA>` then
     `new-session -d -s other -n alpha -c <projB>`. `other` is created last, so
     it is the "current" session for a clientless call. The explicit `-n`
     disables automatic-rename, so the collision does not depend on anyone's
     tmux.conf. projA/projB are fake aitasks roots, and each must contain
     `aitasks/metadata/project_config.yaml`: without it discovery ignores the
     session and the multi-session checks pass against nothing. Before any fix
     assertion, assert that discovery sees both sessions. The Python heredoc
     runs under `env -u TMUX -u TMUX_PANE` with `AITASKS_TMUX_SOCKET` and
     `TMUX_TMPDIR` pointing at the private server, so the developer's ambient
     server cannot leak in. `TMUX_TMPDIR` must use a short path because of the
     socket-path length limit.
   - **Ground truth** comes from `list-panes -a`, which takes no `-t` and so
     cannot misresolve: it gives the real pane-id set per session. The call is
     made from the Python heredoc through the gateway, with the format built as
     the Python string `"#{session_name}\t#{pane_id}"` so the separator is a
     real tab byte. Bash single quotes would pass a literal backslash-t, and
     tmux formats do not interpret escapes. The helper asserts that every
     record splits into exactly 2 non-empty fields and that both `alpha` and
     `other` have at least one pane. A malformed ground truth then fails as
     itself and never shows up as a false mismatch.
   - **Phase A, collision fixture (the fix runs here, collision intact):**
     1. Negative control (red proof): raw `list-panes -s -t =alpha -F
        '#{session_name}'` → `other`. This pins the tmux behaviour, and a future
        tmux that stops doing it fails the control loudly instead of letting the
        fix tests pass vacuously.
     2. Fix assertions, all against this same live collision:
        raw `=alpha:` → `alpha`. `discover_aitasks_sessions()`,
        `discover_aitasks_sessions_async()` and `discover_aitasks_sessions_checked()`
        each map alpha→projA and other→projB. `agent_freeze._enumerate_session("alpha")`
        returns only alpha's panes. Monitor, covering all four `monitor_core`
        sites: `TmuxMonitor(session="alpha", multi_session=False, exclude_pane="")`
        `.discover_panes()` and `await .discover_panes_with_shadows_async()` return
        exactly alpha's ground-truth pane ids. `TmuxMonitor(session="alpha",
        multi_session=True, exclude_pane="")` `.discover_panes()` and the async
        variant return every pane with `session_name` equal to its ground-truth
        session, and no pane id listed twice.
     3. Collision re-check: repeat control 1 after the fix assertions. It must
        still read `other`, which proves the collision stayed live the whole
        time the fix assertions ran.
   - **Phase B, trigger isolation (after Phase A, in a separate pair of
     sessions `beta` / `other2` where `other2`'s window is named `unrelated`):**
     raw `=beta` → `beta`. Without the name collision the bare form is correct,
     so the collision is the trigger. Phase B never shares state with Phase A.
   - Source guard: grep `.aitask-scripts/` for `list-panes", "-s", "-t", tmux_session_target(`
     / `session_target(` on a `list-panes -s` line, which must find nothing.
   Uses `tests/lib/asserts.sh` with a PASS/FAIL footer.

5. **Note t1847** (Step 8e, after commit) that the gateway now provides
   `session_scope_target` / `tmux_session_scope_target`, so `agent_reopen._session_scope`
   can delegate to it. Hedge that its file was uncommitted when read.

6. Step 9: post-implementation (commit, archive).

## Verification

- `bash tests/test_list_panes_session_scope_live.sh`: the control shows the
  bug, and the fix assertions pass.
- `python3 -m pytest tests/test_tmux_exec.py tests/test_discover_async_parity.py
  tests/test_discover_checked.py tests/test_discover_default_unchanged.py
  tests/test_discover_include_registered.py tests/test_monitor_refresh_no_sync_tmux.py
  tests/test_agent_freeze.py`
- `bash tests/test_project_resolve.sh`, `bash tests/test_multi_session_monitor.sh`,
  `bash tests/test_freeze_engine_live.sh`, `bash tests/test_no_raw_tmux.sh`,
  `bash tests/test_restore_session_bootstrap_live.sh`
- Full `bash tests/run_all_python_tests.sh` (read the last line only; check
  `PIPESTATUS`).
- `shellcheck` on the new test.

## Risk

### Code-health risk: low
- 8 call sites across the monitor, freeze reconcile and discovery change their
  target string. A failure path could behave differently if a caller parsed
  `can't find window:` specifically. The gateway classifier accepts both
  messages and every other caller branches on rc, which Step 2's re-grep
  confirms. · severity: low · → mitigation: covered by plan Step 2/Verification
- Mock-based tests pin exact argv. The ones found are listed in Step 3, and a
  missed one fails loudly in the full suite rather than silently. · severity: low
  · → mitigation: covered by Verification (full suite)

### Goal-achievement risk: low
- The characterization (window-name match in the current session) could be
  incomplete. Step 4 Phase A's control and re-check and Phase B's isolation
  prove both directions deterministically, so the claim rests on a measurement
  rather than inference. · severity: low · → mitigation: covered by plan Step 4
- Fix assertions could pass vacuously if the collision were absent while they
  ran. Phase A runs them between two live-collision checks, and Phase B uses
  separate sessions. · severity: low · → mitigation: covered by plan Step 4
- A monitor site left on the colon-less form would misattribute panes silently.
  Phase A exercises all four `monitor_core` sites (sync/async × single/multi)
  against ground truth. · severity: low · → mitigation: covered by plan Step 4

## Final Implementation Notes

- **Actual work done:** Added `tmux_exec.session_scope_target()` (`=<s>:`) with
  a `TmuxClient` re-export and an `agent_launch_utils.tmux_session_scope_target`
  wrapper, and switched every `list-panes -s` call site to it: discovery
  (`_collect_live_roots`, which lost its `pane_target` parameter so the default
  and checked walks share one form; `discover_aitasks_sessions_async`; the
  pid→pane lookup), freeze reconcile's `_enumerate_session`, and the four
  `monitor_core` discovery sites. Orphaned `tmux_session_target` imports were
  dropped from `agent_freeze.py` and `monitor_core.py`. Added
  `tests/test_list_panes_session_scope_live.sh` (25 checks).
- **Deviations from plan:** The pid→pane lookup (~1914) already used
  `tmux_window_target(session, "")` (t1071_5). It was switched to the named
  helper for consistency, with no behaviour change. One more exact pin turned
  up: `tests/test_agent_freeze.py::test_the_enumeration_pass_is_explicitly_targeted`
  (`=aitasks` → `=aitasks:`), plus a second one in
  `test_monitor_refresh_no_sync_tmux.py:254`. The shell twin
  `ait_tmux_session_target` feeds only session-typed commands (`has-session`,
  `list-windows`, `attach`) or `${session_t}:` forms, so no shell change was
  needed.
- **Issues encountered:** `tests/test_multi_session_monitor.sh` fails
  independently of this change: it reproduces on HEAD code in an isolated copy.
  Its `SimpleNamespace` snapshot lacks the `frozen` attribute that
  `monitor_app._format_agent_card_text` reads since t1705_7.
  `tests/test_freeze_engine_live.sh` refuses to run inside tmux by design, so it
  was not run here. The only change to it is a test-side target string, and its
  substring asserts still match the colon form.
- **Upstream defects identified:**
  - `tests/test_multi_session_monitor.sh:46 — the SimpleNamespace snapshot fixture lacks the `frozen` attribute that monitor_app._format_agent_card_text (monitor_app.py:1756) reads since t1705_7 (fcf144025), so the test crashes with AttributeError on HEAD independent of t1874`
- **Key decisions:** The red proof was taken on an isolated copy of the tree
  with the helper mutated back to `=<s>`, not by stashing or restoring in the
  shared worktree. It produced 14 failures covering every consumer: discovery
  mapped both sessions to `pb`, freeze saw only `other`'s pane, and the monitor
  lost alpha's panes and listed `%2` twice. Controls and ground truth still
  passed.
- **Verification:** new live test 25/25; targeted pytest (7 modules) green;
  `test_project_resolve.sh` 25/25; `test_restore_session_bootstrap_live.sh`
  44/44; `test_no_raw_tmux.sh` 5/5; full `run_all_python_tests.sh` PASSED;
  `shellcheck -x -P SCRIPTDIR` clean.

## Post-Review Changes

### Change Request 1 (2026-09-24 15:51)
- **Requested by user:** `aidocs/framework/tmux_gateway.md` listed only
  `session_target` / `window_target` and told authors to use them for every
  `-t`, which would lead a future author back to the bare form. Update the
  target-formatting section and the checklist.
- **Changes made:** Added `session_scope_target` to the Python surface list.
  Added a "pick the helper by the `-t` type" rule with a three-row table (session
  / whole session on a window-typed `-t` / one window, with the shell idiom
  `ait_tmux_window_target "$s" ""`). Explained the window-first lookup and its
  consequences, noting that `list-panes`'s man page calls the `-s` target a
  session while tmux resolves it as a window. Pointed at the new live test, and
  rewrote checklist item 2 to choose by `-t` type. The table's `-t` types
  were checked against the tmux 3.7c man page, and the shell idiom against
  `tmux_exec.sh` (`=alpha:`).
- **Files affected:** aidocs/framework/tmux_gateway.md

### Change Request 2 (2026-09-24 22:25)
- **Requested by user:** The guide claimed the live test fails for any bare
  `list-panes -s` site, but its source guard only matches same-line Python calls
  using the `session_target` helper names. Narrow the claim.
- **Changes made:** The guide now lists exactly what the live test exercises
  (discovery sync/async/checked, freeze enumeration, monitor single/multi) and
  states the guard's scope. It names what gets past it (multi-line calls, shell
  sites, hand-formatted `=<s>`) and assigns new sites to review.
- **Files affected:** aidocs/framework/tmux_gateway.md
