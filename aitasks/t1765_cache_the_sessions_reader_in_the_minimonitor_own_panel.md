---
priority: low
effort: low
depends: []
issue_type: performance
status: Ready
labels: [monitor, frozen]
anchor: 1705
followup_kind: review_finding
created_at: 2026-09-09 15:31
updated_at: 2026-09-09 15:31
---

`MiniMonitorApp._own_frozen_at` constructs a fresh `agent_sessions.SessionsView()`
on every frozen own-panel refresh, so the reader's unchanged-store cache never
gets a chance to work: a probe showed two refreshes against an identical store
stamp producing two full `load_safe` calls — a full JSON read and parse each
time.

The panel refreshes on the ordinary monitor tick, and the store is unchanged
between almost all of them, so this is a repeated read of a file whose stamp
already says nothing happened. `SessionsView` exists precisely to make that case
cost a stat.

Fix: hold one `SessionsView` on the app (beside `_marks_view`, which already
follows this pattern) and let `_own_frozen_at` invalidate/read it, so unchanged
frozen state costs a stamp check rather than a re-parse.

Low severity: it costs one small read per tick while the followed agent is
frozen, and nothing is incorrect. Found by review of t1705_7; disposition
there: follow-up, not blocking.
