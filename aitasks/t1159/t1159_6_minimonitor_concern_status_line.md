---
priority: medium
effort: medium
depends: [t1159_5]
issue_type: feature
status: Ready
labels: [shadow, aitask_monitormini]
anchor: 1159
created_at: 2026-08-12 17:14
updated_at: 2026-08-16 12:00
---

Add an always-shown concern status line to minimonitor: a persistent line showing (1) the shadow's current concern round and its review date/time, (2) a glyph reflecting the concern staleness state (stale vs fresh), and (3) the auto-recheck loop's armed/disarmed state (see "Scope addition" below). Requested by the user during t1159_2 plan review (2026-08-12); routed to a dedicated sibling so t1159_2 stays focused on the auto-recheck loop.

## Context

- Data is already in hand each minimonitor tick — no new tmux traffic needed:
  - Round + review time: `parse_block_meta(text)` (`.aitask-scripts/monitor/concern_parser.py:485`, landed by t1159_1) over the tick's shadow capture (`capture_shadow_text` result in `_maybe_offer_concerns`). `BlockMeta(round, reviewed_at)`; `None` for absent/invalid header — the line must render a "no round yet" state for that.
  - Staleness glyph: `self._shadow_feedback_stale` (tri-state `bool | None`, cached in `_maybe_offer_concerns`; `None` = indeterminate — render as its own state, never as fresh or stale; see the derived-state and tri-state discipline in `aidocs/framework/shadow_agent.md` "Feedback freshness").
- Minimonitor today has only *transient* banners: `#mini-shadow-stale` (stale warning, `$error`, empty ⇒ 0 rows) and — after t1159_2 — `#mini-loop-status` (auto-recheck loop state, `$warning`). The always-on status line is a **separate, third widget** (t1159_2's coordination note pins that its banner design does not foreclose this one). Decide at planning time whether the always-on line subsumes the transient stale banner or coexists with it.
- Follow the existing banner pattern: recorded-attribute DOM-free test seam (`_set_shadow_stale_banner` stores `_shadow_stale_banner_text` before `query_one().update()`), CSS `height: auto`, mounted in `compose`.
- Glyph conventions: checkbox-style glyphs preferred for marks; render-level verification required for TUI changes (composited strips, narrow widths — minimonitor targets ~40 columns).

## Scope addition — the auto-recheck loop's armed state must be visible (2026-08-16)

Requested by the user after running the loop live: **minimonitor never says
whether the auto-recheck loop is on.** Verified on `main`:

- `#mini-loop-status` (t1159_2) is written only from the two loop paths —
  `_arm` (`minimonitor_app.py:2581`) and `_service_review_loop`
  (`:2782-2790`, which returns immediately when `not ctrl.armed`, `:2597`).
  Every disarm path sets it to `""` (`:2427`, `:2502`, `:2744`, `:2764`), and
  the CSS is `height: auto` on an empty Static ⇒ **0 rows**. So DISARMED and
  "loop widget not mounted / never used" are pixel-identical: the absence of a
  banner is the only signal, which is no signal at all.
- The sole standing hint that the feature exists is `L:auto-recheck loop` in
  `KEY_HINTS_TEXT` (`:282`), which says nothing about the current state.
- Consequence in practice: the user cannot tell an armed-and-quiet loop from a
  loop that was never armed, or from one that auto-disarmed while the toast
  (`_loop_auto_disarm`, `:2428`) was missed — and auto-disarm is a real,
  reachable outcome (verified absence of agent/shadow, or a mid-loop shadow
  swap to an agent with no readiness detector).

Requirement: this always-on line must carry the loop state as **a field on the
line** — the same treatment t1503 pins for its non-convergence indicator, not a
fourth widget. Both polarities must be pinned by tests:
DISARMED must render a *positive* mark, not an empty string, and the
ARMED/DELIVERING/FIRED/
"holding for shadow" distinctions t1159_2's banner already draws must not be
lost when this line subsumes or coexists with `#mini-loop-status`.

Whichever way the subsume-vs-coexist decision goes, record it here — t1503
inherits it, and it now governs three widgets (`#mini-shadow-stale`,
`#mini-loop-status`, this line) rather than two. If the line subsumes
`#mini-loop-status`, its transient states must survive the move; if the two
coexist, this line's loop field is the *always-on* half and `#mini-loop-status`
stays the transient detail.

Width note: minimonitor targets ~40 columns and the line already has to fit the
round, the reviewed-at time and the staleness glyph. Budget the loop field as a
compact glyph/short token (render-level verification at narrow widths, per the
TUI conventions), not prose.

**Not in scope here:** the Codex `Enter`-swallow delivery bug — the loop
believes it fired while the prompt sits unsubmitted in the shadow composer.
That is **t1525** (`aitasks/t1525_fix_failed_verification_t1523_item4.md`,
live-measured: 0s inter-key delay ⇒ not submitted, 0.25s/1.0s ⇒ submitted).
This task must not paper over it with a status field: t1525 owns making the
delivery *verify* submission. Note the two touch the same method — t1525 refers
to it as `_deliver_recheck`, but on `main` it is `_fire_shadow_recheck`
(`minimonitor_app.py:2792`).

## Key files

- `.aitask-scripts/monitor/minimonitor_app.py` — new always-on Static + per-tick update from `_maybe_offer_concerns` (the one place that already holds capture text and staleness), CSS block, compose mount.
- `tests/test_minimonitor_concern_action.py` — status-line seam tests (round shown, no-round state, stale/fresh/indeterminate glyph states).

## Cross-references

- **t1448** (shadow concern badge currency, depends: [1159, 1420]) keys the full monitor's `!` badge freshness off the same `(round, reviewed_at)` pair — coordinate the two so their notions of "current" agree; do not duplicate its badge logic. t1448 records minimonitor's lack of a `!` badge as a deliberate asymmetry; this status line is the minimonitor-side surface instead.
- **t1159_2** (auto-recheck loop) adds `#mini-loop-status`; this line is a separate widget beside it.
- **t1525** (Codex shadow never submits the injected recheck) shares
  `_fire_shadow_recheck` with the state this line displays, and is the reason
  the "loop is armed but nothing is happening" case is currently
  indistinguishable from "loop is off". Land t1525's delivery fix independently;
  this line only has to report the state honestly, never compensate for it.
- **t1493** (recheck rounds leave stale concerns in picker): its consumer-side block-age freshness check may share display logic with this line's staleness glyph.
- **t1503** (surface review-loop non-convergence, `depends: [t1159_6, t1159_7]`)
  plans its non-convergence indicator as a **field on this status line**, not a
  fourth widget. Keep the line's update seam extensible with an extra field, and
  record whichever subsume-vs-coexist decision you take against
  `#mini-shadow-stale` / `#mini-loop-status` so t1503 inherits it.
