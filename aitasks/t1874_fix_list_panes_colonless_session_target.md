---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [framework, skills, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1869
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-09-24 09:29
updated_at: 2026-09-24 15:29
---

## Origin

Spawned from t1869 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_launch_utils.py:1300 — list-panes -s -t =<session> (colon-less, the default pane_target of _collect_live_roots) resolves as a WINDOW on tmux 3.7c and falls back to the most recent session, so discover_aitasks_sessions() maps every live session to the same project root when several sessions run; same colon-less target at agent_launch_utils.py:1385,1895, agent_freeze.py:954, monitor/monitor_core.py:2564,2586,2616,2637`

(Line numbers as of commit acbee2da3.)

## Diagnostic context

While building the status-bearing tmux discovery for cross-repository notes
(t1869), a resolver test with a private tmux server started two sessions —
`alpha` with cwd `projects/beta` and `other` with cwd `projects/alpha` — and
`discover_aitasks_sessions()` reported BOTH sessions rooted at `projects/alpha`.
Measured with the raw command on tmux 3.7c, same server:

    tmux list-panes -s -t '=alpha'  -F '#{session_name} #{pane_current_path}'
      -> other .../projects/alpha        (WRONG: the other session's panes)
    tmux list-panes -s -t '=alpha:' -F '#{session_name} #{pane_current_path}'
      -> alpha .../projects/beta         (correct)

Related measurement: `list-panes -s -t '=gone'` (no such session) reports
`can't find window: gone`, i.e. the colon-less `=<s>` is parsed as a window
target, while `=gone:` reports `can't find session: gone`.

**Not yet characterized:** an earlier trial with sessions at `/tmp` and `/home`
returned the correct panes for `=alpha`, and on the live `ait` server
(3 sessions) the default and the colon-form discovery agree. So the fallback is
conditional — the first job is to pin down when tmux resolves `=<s>` to a
different session (window-name matching? most-recent-session fallback? tmux
version?) with a deterministic reproduction.

t1869 did NOT change the default: `discover_aitasks_sessions()` keeps the
colon-less form byte-for-byte (its four parity tests pin that). Only the new
`discover_aitasks_sessions_checked()` passes `pane_target=lambda s:
window_target(s, "")` (the `=<s>:` form), and `tests/test_project_resolve.sh`
test 14 exercises the two-session case through it.

## Suggested fix

Characterize the trigger first (a deterministic test under a private
TMUX_TMPDIR, following tests/test_project_resolve.sh test 14). Then switch
every `list-panes -s -t tmux_session_target(...)` call site to the `=<s>:` form
(`window_target(session, "")` from lib/tmux_exec.py), or give the gateway a
dedicated session-scope target helper. Re-run the discovery parity tests and
`ait monitor`/minimonitor checks. `ait monitor` builds a
{session: project_root} map from this discovery, so a wrong mapping shows the
wrong project for a session.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1847** id=2026-09-24T08:41:12Z.d207b0e614942d63ce3c6f4d from=t1847 from_verified=yes at=2026-09-24T08:41:12Z base=d05ef72419e724ee25ade02ef07443e3e063f042 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1847 (code commit d05ef7241), for your bare `=<session>` sweep:
> | 
> | - ALREADY FIXED at one of your listed sites: `agent_launch_utils.resolve_pane_id_by_pid` now lists panes with `tmux_window_target(session, "")` (`=<s>:`). Drop it from the sweep list; its callers (shadow spawn, monitor, syncer, restore) were re-tested.
> | - DETERMINISTIC TRIGGER (measured on tmux 3.7c, private server): run the command from a client whose CURRENT session holds a WINDOW named like the target session. With sessions A and B, and a window `B` inside A, `list-panes -s -t =B` from a client in A lists A's panes; `=B:` lists B's. From outside tmux (no current session) both forms agreed in the same trial — which is probably why earlier trials looked conditional.
> | - A ready-made regression fixture: `tests/test_frozen_reopen_live.sh` cases c2 and c3 build exactly that layout (isolated class, `in_a` wrapper sets TMUX/TMUX_PANE to a pane in A) and assert a precondition that the bare target reads A.
> | - New code that already uses the colon form, in case you want one helper: `agent_reopen._session_scope()` and `agent_restore._named_session_for_root()` (explicit-session authorization goes through `discover_aitasks_sessions_checked()`). `agent_freeze._enumerate_session` (reconcile) is still bare and still yours.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-24T12:29:47Z status=pass attempt=1 type=human
