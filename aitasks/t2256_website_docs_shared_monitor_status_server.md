---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [monitor, minimonitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: docs_gap
implemented_with: claudecode/opus5_5
created_at: 2026-11-09 11:33
updated_at: 2026-11-09 15:32
---

## Context

The shared monitor status server (t2037; restart verbs from t2246) has almost
no user-facing website coverage. The only mentions are on
`website/content/docs/tuis/monitor/reference.md`:
- the options-table rows for `--server-status` / `--restart-server`;
- two paragraphs under the options table;
- the `AITASKS_MONITOR_SERVER` and `AIT_MONITOR_RESTART` env rows.

Almost all of that was added by t2246. A user who sees stale or odd behaviour
in a monitor or minimonitor has no page explaining why.

## Gaps to fill

1. **Monitor page (`_index.md` / `how-to.md`): what the shared server is**, in
   user terms.
   - Monitor, minimonitor and applink share one background scanner per tmux
     server and framework version.
   - It starts on demand and exits after about 30 s with nobody connected.
   - When it cannot be reached, each TUI scans by itself (`AITASKS_MONITOR_SERVER=0`
     forces that).
   - Passing `--interval` / `--lines` makes that monitor instance scan on its
     own.
2. **How-to / troubleshooting entry.** Typical symptoms: the monitor or
   minimonitor shows behaviour that a recent framework change should have
   fixed, e.g. a pane it should hide, or an outdated status. The cause: the
   server still runs the code it started with. The fix:
   `ait monitor --server-status` (look at the start time), then
   `ait monitor --restart-server`. Also: what a `RETIRE_FAILED … still_running`
   line means, and how to end that pid by hand.
3. **Minimonitor docs** (`website/content/docs/tuis/minimonitor/`): one
   sentence plus a link explaining that minimonitor reads from the same shared
   server, and that `ait monitor --restart-server` refreshes it too. Today
   neither page mentions the server at all.
4. **`website/content/docs/commands/setup-install.md`** (the `ait upgrade`
   section): `ait upgrade` stops the status servers started from the upgraded
   project, open monitors reconnect automatically, and
   `AIT_MONITOR_RESTART=0` opts out. `ait setup` does not restart them.

## Constraints

- Current-state only, no version history in the page bodies
  (`aidocs/framework/documentation_conventions.md`).
- Do not promise reconnect timing: the client retries with backoff of up to
  30 s. Say "automatically".
- Source of truth for behaviour: `aidocs/framework/monitor_status_protocol.md`
  ("Lifecycle and socket path", "Restart", "Python client").
- Use `{{< relref >}}` for internal links. Run
  `cd website && python3 check_links.py --build`, and offer
  `check_link_relevance.py`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-09T13:32:49Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T13:44:06Z status=pass attempt=1 type=human
