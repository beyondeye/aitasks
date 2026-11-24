---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [monitor, minimonitor, frozen_agents, sitrep, performance]
file_references: [.aitask-scripts/lib/frozen_sitrep.py, .aitask-scripts/monitor/monitor_shared.py:446-480, .aitask-scripts/monitor/monitor_shared.py:907-970, .aitask-scripts/monitor/monitor_core.py, .aitask-scripts/monitor/status_server.py, .aitask-scripts/monitor/status_protocol.py, aidocs/framework/monitor_status_protocol.md, aidocs/framework/sitrep.md]
premise_baseline: 72bdd15db100fcb8a344f167ac12e23363e47589 @ 2026-11-24 12:36
created_at: 2026-11-24 12:36
updated_at: 2026-11-24 12:36
---

Move the frozen-agent sitrep badge derivation (t2337) out of each TUI process and into
the shared monitor status producer, so it is derived once per tmux server and shipped
to every client as part of the pane record.

## Today

Each running `ait monitor` / `ait minimonitor` process derives the badge itself:
`AgentMarksMixin._kick_frozen_sitrep` -> `_frozen_sitrep_pass` (in
`.aitask-scripts/monitor/monitor_shared.py`, around lines 907-970) runs a
`frozen_sitrep.FrozenSitrepTracker` per app instance, in a coalesced background worker,
and binds each verdict to the frozen instance `(record id, pane id, stand-in pid)`
in `_frozen_sitrep_state`. N TUIs means N trackers, N caches and N reads of the same
capture / receipt / `todo.md`. The shared status server (`status_server.py`, spec
`aidocs/framework/monitor_status_protocol.md`) already publishes `frozen` and
`frozen_record_id` per pane but no badge, so applink and the Go monitor have no badge
at all unless they reimplement `lib/frozen_sitrep.py`.

## Goal

- One derivation per producer, published as a new optional member of the pane record
  (e.g. `frozen_sitrep`), consumed by monitor, minimonitor and any other client.
- The TUI mixin keeps only rendering (`FROZEN_SITREP_BADGES`,
  `format_frozen_sitrep_badge`) and reads the state from the snapshot.

## Constraints (from the design discussion)

1. **Producer layer, not server-only.** Clients still scan in-process when the server is
   unavailable, with `--interval` / `--lines`, or with `AITASKS_MONITOR_SERVER=0`. Put
   the derivation where both the server and the in-process `TmuxMonitor` path use it
   (around `monitor_core`), so there is one implementation, not two.
2. **Off the tick path.** Server ticks run under one producer lock that serialises
   captures, `refresh`, compare-mode changes and pins. The tracker does file I/O
   (capture hash, receipt fstat, `todo.md`), so run it as its own coalesced task
   (`asyncio.to_thread`), publishing into a later generation; never extend a tick or
   hold the producer lock. A slow `todo.md` must not delay any client's scan.
3. **Open string on the wire.** Add the member additively (no `proto` bump) as an open
   string. Today `format_frozen_sitrep_badge` raises on an unknown state; a wire value
   from a newer producer must instead render as `sitrep ?` (never as safe). Absent
   member / no verdict renders nothing, as today. Update the spec's record tables and
   the pinned schema tables in `status_protocol.py` together
   (`tests/test_monitor_status_protocol.py` pins them).
4. **Keep every t2337 safety rule.** Single-snapshot publish gate with the post-read
   version check, `unknown` never cached, settled-record requirement, safety only from
   `agent_sessions.receipt_certifies`, and binding to the frozen instance (the server
   holds pane id and stand-in pid, so it can bind before publishing). Move the existing
   tracker / badge tests to the new seam rather than dropping them.
5. **Per-VERSION servers.** One server per framework `VERSION`; two versions sharing a
   tmux server each derive once. Acceptable, note it in the spec.

## Docs

Update `aidocs/framework/monitor_status_protocol.md` (record member, what the server
owns) and the "Frozen-agent badge (t2337)" section of `aidocs/framework/sitrep.md`
(who derives it). User-facing behaviour does not change.

## Open question for planning

Confirm how much a minimonitor's snapshot set covers (own session vs. every project's
frozen agents) to size the current duplication, and whether applink / the Go monitor
should render the badge in this task or a follow-up.
