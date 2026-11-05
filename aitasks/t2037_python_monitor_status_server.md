---
priority: medium
effort: high
depends: [t2034_3]
issue_type: feature
status: Ready
labels: [monitor, minimonitor, tmux, applink]
children_to_implement: [t2037_2, t2037_3, t2037_4]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-11-05 08:28
---

Build the shared monitor status server in Python, reusing `monitor_core`
unchanged as the producer, plus a Python client. Then switch monitor,
minimonitor and applink to subscribe. Background and overall shape: aitasks#2034;
protocol: t2034_3; producer settings semantics: t2034_2. Split out of t2034
because the server, the client and the two consumer migrations are separate
pieces of work.

## Children

1. Server process and lifecycle.
2. `MonitorClient` (fallback, replay mode).
3. Monitor + minimonitor subscribe.
4. applink subscribes.

## Cross-repo

The replay mode (child 2) feeds the Textual twin of the Go monitor parity demo
(aitasks_go#16_5). The Go server (t2038) reimplements this server behind the same protocol.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2034_1** id=2026-11-03T15:02:17Z.a3de44be6053a23500435583 from=t2034_1 from_verified=yes at=2026-11-03T15:02:17Z base=6930f54e25e74a1e92e01e7fab1a8c1cbbcf2914 base_branch=main dirty=yes host=omg16
>
> | t2034_1 measurements relevant to the Python status server (2026-11-03, omg16;
> | details in aiplans/p2034/p2034_1_measure_monitor_scan_cost.md, task-data commit
> | db064ad60, archived with t2034_1). Advisory; one host, one moment.
> | 
> | - Payoff is dominated by tmux-server dedup: live tmux server 65–73 % of a core,
> |   almost all scanning (isolated N=12: K=0 0.02 %, K=1 0.77 %, K=4 2.68 %).
> |   ≈42 scanners × 35 capture-pane / 3 s ≈ 490 capture-pane/s at that moment.
> |   One shared scanner removes ≈(K−1)/K of it.
> | - The producer's own CPU (warm, app config, 38 agent windows): ≈21 ms/tick
> |   (p95 27 ms), ≈0.7 % of a core at 3 s — one Python server is cheap.
> | - Inside the producer, the cost is the control-mode stream parse
> |   (TmuxControlClient._reader_loop / tmux-control-loop thread, ≈11 % of a
> |   minimonitor's GIL samples, ≈31 % of a monitor's) — not strip_ansi (2–10 %) or
> |   classification (<1 %).
> | - Clients keep ≈80 % of their CPU after subscribing (Textual render), and that
> |   grows with agent count. A protocol that pushes per-pane deltas would let clients
> |   skip re-rendering unchanged cards; there is a separate follow-up task for
> |   the render side.
> | - Profiling note: py-spy 0.4.3 on CPython 3.14 needs --gil; default mode counts
> |   threads blocked in select/Condition.wait as active (58 % of samples).

> **✉ note:t2034_1** id=2026-11-03T15:15:56Z.81d7f5d2f868284b4611c175 from=t2034_1 at=2026-11-03T15:15:56Z base=6930f54e25e74a1e92e01e7fab1a8c1cbbcf2914 base_branch=main dirty=yes host=omg16
>
> | Cross-repo dependents of this task (aitasks_go, as of 2026-11-03), checked by
> | reading their xdeps:
> | - aitasks_go#47 go_monitor_status_server and #47_1 monitord_skeleton_protocol_lifecycle,
> |   both with xdeps [2037, t2034_3]. #47 is the Go re-implementation of this server
> |   (re-homed from aitasks t2038).
> | 
> | What reaches them automatically: only this task's Done status (aitasks_go `ait ls`
> | reads it live through the project registry). Content does NOT: aitasks_go planning
> | reads sibling context from its own repo only, and nothing reads this repo's
> | archived plans.
> | 
> | Suggested handoff at completion (Step 8e, when the last child archives this
> | parent): one cross-repo note to aitasks_go#47 carrying what a Go port must match:
> | the server lifecycle decisions (socket path, file lock, grace period, %exit
> | handling), the per-(tmux socket, VERSION) keying, the fallback rules, and the paths
> | of the protocol tests/fixtures it must pass, plus the commit that holds them, e.g.
> |   ./ait note 47 --project aitasks_go --from 2037 --with-live --file - <<'EOF' ... EOF
> | Re-check the dependent list first (grep xdeps in aitasks_go).

> **✉ note:t2034_2** id=2026-11-03T20:44:23Z.78dba770e9f11556809934e0 from=t2034_2 from_verified=yes at=2026-11-03T20:44:23Z base=14dc117dc1e9d2884c06666050f45fada75a321d base_branch=main dirty=yes host=omg16
>
> | t2034_2 is done (code commit 14dc117dc): TmuxMonitor is now a client-agnostic producer.
> | Advisory context for the Python server and client. The wire shape is t2034_3's call;
> | t2034_3 got a matching note.
> | 
> | What the server can reuse unchanged (all in monitor_core unless noted):
> | - The producer: construct TmuxMonitor with defaults (all_sessions=True). It reads no
> |   $TMUX_PANE and excludes no pane.
> | - Parked: the global set comes from
> |   agent_marks.parked_session_windows(MarksView.parked_windows(), session->root).
> |   Each subscriber contributes a capture-pin set (a minimonitor pins its followed agent,
> |   or CAPTURE_PIN_ALL while its identity is unconfirmed). The server should publish
> |   parked_capture_skip(global, [pins of every subscriber]) via set_parked_agents BEFORE
> |   each capture (the existing publish-before-capture rule). Today each app does this for
> |   one client in AgentMarksMixin._parked_agent_pairs.
> | - Clients must apply client_view_snapshots(snaps, own_pane=..., home_session=...,
> |   multi_session=..., parked_pairs=global, pins=own_pins) to EVERY snapshot they store,
> |   bulk and single-pane alike. In-process this is AgentMarksMixin._project_snapshots.
> |   Without it, another subscriber's pin leaks live data into a parked row.
> | - Compare-mode override: one shared per-pane setting on the producer.
> |   set_compare_mode/cycle_compare_mode from any client affect all clients.
> | - applink: the router/pusher take own_pane and treat it as a producer-cache miss on
> |   every cache-backed route (kill via kill_agent_pane_smart(cache_miss=True)). Keep that
> |   rule when applink becomes a subscriber.
> | 
> | Pinned by tests/test_monitor_client_agnostic.py, including a two-client
> | shared-producer simulation that drives a second client's real _fast_preview_refresh.

> **✉ note:t2034_3** id=2026-11-04T10:41:12Z.944636c21b9fda495d8a10c5 from=t2034_3 from_verified=yes at=2026-11-04T10:41:12Z base=6ed79b10b4c3bb52722cdf05cc921db98a9f05fd base_branch=main dirty=yes host=omg16
>
> | Advisory handoff from t2034_3. The protocol your server and client speak landed in commit 7b99d8584. Paths are as of that commit; nothing here binds your design.
> | 
> | - Spec: aidocs/framework/monitor_status_protocol.md. Its "Lifecycle and socket path" section is a placeholder for t2037_1 to fill in; it restates the parent's shape. The Go twin (aitasks_go#47_1) mirrors whatever you write there.
> | - Reuse from .aitask-scripts/monitor/status_protocol.py:
> |   - **For the server (t2037_1):**
> |     - `StreamEncoder`: one per server, encoding full content.
> |     - `filter_message(msg, content=…, include_shadows=…)`: projects each subscriber's view.
> |     - `monitor_pane_record(monitor, snap)`: maps compare mode, override and last change from the producer.
> |     - `sessions_member` / `discovery_member`: build those members from the producer's shapes.
> |     - `read_line(reader)`: open the reader with `limit=MAX_CLIENT_LINE_BYTES`. A `FramingError` is terminal: send error too_long, then close.
> |     - `decode` / `encode` with `direction=CLIENT` / `SERVER`.
> |   - **For the client (t2037_2):** `StreamState`. `Applied.changed` tells a renderer which cards changed.
> | - Server duties, per the spec:
> |   - one delta per commit, even when empty;
> |   - one ordered outbound queue per connection, and a lock held across "read state + enqueue". `_ReplayConnection` in .aitask-scripts/monitor/status_recording.py is a working model of this;
> |   - compute `completed` (the clients' `_compute_completed_panes` rule);
> |   - compute the global `parked` set (`agent_marks.parked_session_windows`) and the skip set (`parked_capture_skip` over all subscribers' pins);
> |   - keep compare-mode overrides shared;
> |   - a pane whose capture failed is absent from that generation (encoded as `removed`).
> | - Replay mode (t2037_2): run `ReplayServer` (status_recording.py) on a temporary socket and connect normally. It validates the recording first and echoes the client's version. Fixture: tests/fixtures/monitor_status/basic.jsonl (synthetic).
> | - Known limit, recorded in the spec: the delta/patch semantics are proven encoder-to-state and against the replayer, not yet against the real producer's tick-to-tick behaviour. If you hit a producer behaviour that needs a clarification, the spec is the place to record it.
