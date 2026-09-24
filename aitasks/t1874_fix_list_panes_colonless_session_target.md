---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [framework, skills, documentation]
gates: [risk_evaluated]
anchor: 1869
followup_kind: upstream_defect
created_at: 2026-09-24 09:29
updated_at: 2026-09-24 09:29
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
