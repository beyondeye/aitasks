---
priority: medium
effort: medium
depends: [t1159_5]
issue_type: feature
status: Ready
labels: [shadow, aitask_monitormini]
anchor: 1159
created_at: 2026-08-12 17:14
updated_at: 2026-08-12 17:14
---

Add an always-shown concern status line to minimonitor: a persistent line showing (1) the shadow's current concern round and its review date/time, and (2) a glyph reflecting the concern staleness state (stale vs fresh). Requested by the user during t1159_2 plan review (2026-08-12); routed to a dedicated sibling so t1159_2 stays focused on the auto-recheck loop.

## Context

- Data is already in hand each minimonitor tick — no new tmux traffic needed:
  - Round + review time: `parse_block_meta(text)` (`.aitask-scripts/monitor/concern_parser.py:485`, landed by t1159_1) over the tick's shadow capture (`capture_shadow_text` result in `_maybe_offer_concerns`). `BlockMeta(round, reviewed_at)`; `None` for absent/invalid header — the line must render a "no round yet" state for that.
  - Staleness glyph: `self._shadow_feedback_stale` (tri-state `bool | None`, cached in `_maybe_offer_concerns`; `None` = indeterminate — render as its own state, never as fresh or stale; see the derived-state and tri-state discipline in `aidocs/framework/shadow_agent.md` "Feedback freshness").
- Minimonitor today has only *transient* banners: `#mini-shadow-stale` (stale warning, `$error`, empty ⇒ 0 rows) and — after t1159_2 — `#mini-loop-status` (auto-recheck loop state, `$warning`). The always-on status line is a **separate, third widget** (t1159_2's coordination note pins that its banner design does not foreclose this one). Decide at planning time whether the always-on line subsumes the transient stale banner or coexists with it.
- Follow the existing banner pattern: recorded-attribute DOM-free test seam (`_set_shadow_stale_banner` stores `_shadow_stale_banner_text` before `query_one().update()`), CSS `height: auto`, mounted in `compose`.
- Glyph conventions: checkbox-style glyphs preferred for marks; render-level verification required for TUI changes (composited strips, narrow widths — minimonitor targets ~40 columns).

## Key files

- `.aitask-scripts/monitor/minimonitor_app.py` — new always-on Static + per-tick update from `_maybe_offer_concerns` (the one place that already holds capture text and staleness), CSS block, compose mount.
- `tests/test_minimonitor_concern_action.py` — status-line seam tests (round shown, no-round state, stale/fresh/indeterminate glyph states).

## Cross-references

- **t1448** (shadow concern badge currency, depends: [1159, 1420]) keys the full monitor's `!` badge freshness off the same `(round, reviewed_at)` pair — coordinate the two so their notions of "current" agree; do not duplicate its badge logic. t1448 records minimonitor's lack of a `!` badge as a deliberate asymmetry; this status line is the minimonitor-side surface instead.
- **t1159_2** (auto-recheck loop) adds `#mini-loop-status`; this line is a separate widget beside it.
- **t1493** (recheck rounds leave stale concerns in picker): its consumer-side block-age freshness check may share display logic with this line's staleness glyph.
