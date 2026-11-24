---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [sitrep, frozen_agents]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2337
created_at: 2026-11-23 02:28
updated_at: 2026-11-24 18:01
---

# Sitrep TUI: say when a triage item's source agent is still frozen

Deferred part 3 of t2337. That task made each frozen agent's sitrep state
visible in `ait monitor` / `ait minimonitor` (the `drop ok` badge). This is the
reverse direction: show it from the sitrep TUI side.

## Goal

On a wrap-up triage item (or a review case) in the sitrep TUI whose source
frozen record still exists, show a details line / How text such as:
"source agent still frozen: drop it with `h` in the monitor". Display only:
never drop, kill or type into a pane from the sitrep TUI.

## Context (from t2337)

- The link from a frozen record to its items is recorded by the harvest in the
  record's receipt `<capture.txt>.harvested`: after the three certification
  lines come `links=1`, then `triage=c<N>` (one per wrap-up triage question the
  harvest added or matched) and `review=c<N>` (lib/sitrep_harvest.py
  `receipt_text`; lib/frozen_sitrep.py `parse_links`).
- The reverse lookup (item -> frozen records) therefore needs a scan of the
  frozen records' receipts: `agent_sessions.SessionsView(...).frozen()`, then
  each record's receipt. Reuse `frozen_sitrep.parse_links` and
  `agent_sessions.receipt_certifies`. Never use title or text matching.
- Fail closed and off the event loop, as `frozen_sitrep.FrozenSitrepTracker`
  does: version-keyed cache, nothing shown when anything is unreadable.
- Records frozen before t2337 carry no link lines until the maintenance pass
  (`harvest all --backfill-links`) records them; show nothing for those.

## Files

- `.aitask-scripts/sitrep_tui/` (details / How text for an item)
- `.aitask-scripts/lib/frozen_sitrep.py` (a reverse-map helper, if shared)
- docs: `website/content/docs/tuis/sitrep/`, `aidocs/framework/sitrep.md`
