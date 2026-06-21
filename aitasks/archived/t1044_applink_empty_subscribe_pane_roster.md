---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [applink]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-21 17:39
updated_at: 2026-06-21 18:19
completed_at: 2026-06-21 18:19
---

The applink data plane never streams anything to the mobile client because
the client subscribes with an empty `panes` list and the server treats that
as "subscribe to nothing". Result on the phone: a permanent
"Connected / No panes / Waiting for first pane…".

## Empirical proof (live server, 2026-06-21)

A PC client (resume with a real bearer, then subscribe) against the running
server showed:
- `subscribe {panes: []}` → resp `{ok:true, panes:[]}`, then **0 pushes,
  0 binary frames**.
- `subscribe {panes: ["%2","%5"]}` → resp `{ok:true, panes:[%2,%5]}`, then
  **`pane_status` JSON pushes + binary `0x01` keyframes (18–23 KB of real
  pane content)**.

So the data plane works perfectly when the client names panes. The mobile
app (aitasks_mobile, MonitorSessionMediator) sends `subscribe {panes: []}`
intending "all panes", and:
- `content.py` `Subscription.apply_subscribe` (~L475) takes the list
  literally → `self.panes = {}` (empty).
- `pusher.py` `_run_once` (~L111) early-returns `if not sub.panes:` →
  emits nothing (no `pane_status` roster, no content).
- There is no roster/discovery push, and the `snapshot` discovery verb is
  deferred/unimplemented (`router.py` ~L62).

## Root cause: empty-`panes` contract mismatch

The mobile client means "empty = all panes"; the server means
"empty = no panes". Neither side implements a pane-discovery handshake, so
the client can never learn pane ids to subscribe to.

## Recommended fix (server-side, minimal)

In `router.py`'s `subscribe` handler (~L261), when the `panes` list is empty
(or absent), expand it to all currently-discovered panes via
`self._monitor.discover_panes()` (pane-id form `%N`, see monitor_core) before
calling `apply_subscribe`. This makes an empty subscribe mean "all panes",
yielding the `pane_status` roster + binary content with **no mobile-app
change required**.

Consider whether content for all panes (vs. only the focused pane) is too
heavy; if so, push `pane_status` for all discovered panes (roster) but stream
binary content only for the focused/explicitly-subscribed pane. Decide the
contract and document it in aidocs/applink/protocol.md (§Subscription) and
content_transport.md.

## Acceptance

- With the unmodified mobile client, opening a paired connection shows the
  pane list populated and the focused pane's content rendered.
- Empty/absent `panes` documented as "all discovered panes".
- Verify end-to-end on the physical Android device (the mobile fix for
  ws://→wss:// is aitasks_mobile t18; this is the next blocker).

## Related

- aitasks_mobile MonitorSessionMediator / ControlFrames (`subscribe`,
  `pane_status`), PaneListPanel.
- Server: `.aitask-scripts/applink/router.py`, `content.py`, `pusher.py`;
  `.aitask-scripts/monitor/monitor_core.py` (`discover_panes`).
