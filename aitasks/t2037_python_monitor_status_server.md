---
priority: medium
effort: high
depends: [t2034_3]
issue_type: feature
status: Ready
labels: [monitor, minimonitor, tmux, applink]
children_to_implement: [t2037_1, t2037_2, t2037_3, t2037_4]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:12
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
