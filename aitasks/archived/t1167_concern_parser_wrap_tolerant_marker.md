---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [shadow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1158
implemented_with: claudecode/opus4_8
created_at: 2026-07-20 00:13
updated_at: 2026-07-20 09:49
completed_at: 2026-07-20 09:49
---

## Origin

Spawned from t1158 during Step 8b review.

## Upstream defect

`.aitask-scripts/monitor/concern_parser.py:57` — the item regex (`_ITEM`)
requires the complete `[priority | region]` bracket on one captured row;
agent-TUI renderers (observed live: Codex CLI's markdown renderer at ~55
columns) hard-wrap long output rows with **literal newlines** that the
`tmux capture-pane -J` wrap-join cannot rejoin, so a bracket split mid-region
leaves no parseable marker line — the whole item is **silently dropped** and
minimonitor's auto-offer never fires. The user sees "no concerns" instead of
the shadow's review.

## Diagnostic context

Observed during t1158's own Step 8 review: a Codex shadow (gpt-5.6-sol)
reviewing the t1158 implementation emitted a valid concern block whose single
concern used a 48-char full-path region
(`.claude/skills/aitask-shadow/impl-review-angles.md:12`). The renderer wrapped
the marker as `- [medium | .claude/skills/aitask-shadow/impl-review-` /
`angles.md:12] …` — reproduced against the real pane capture:
`has_concern_block: False`, `parse_concerns: 0`. Body-wrap is already handled
by the parser's continuation-join design; only a wrap **inside the bracket** is
fatal. t1158 added a producer-side mitigation (short-region rule ≤ ~30 chars,
`basename.ext:LINE`, in `impl-challenge.md` + `concern-format.md`), but that is
a prompt-level instruction and cannot be enforced — the parser must become
structurally immune.

## Suggested fix

Bounded wrap-tolerant marker matching in `concern_parser.py::_parse_items`:
when a line starts like a marker (`^\s*-\s+\[`) but has no closing `]`, join at
most 2–3 following rows until the bracket closes, then apply the existing
`_ITEM` regex to the joined line. The bound preserves the wrap-collision
hardening (a continuation line never carries `- `, so over-joining is the only
new risk; keep it tight). Add tests: the real Codex-rendered capture as a
fixture (marker split mid-region → 1 concern parsed, auto-offer fires), plus a
negative control that an unbounded-looking garbage `- [` line without any
closing bracket within the bound is still not parsed. Update
`concern-format.md`'s parser-contract notes accordingly (the short-region
producer rule stays — it is still good hygiene).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-20T06:26:23Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-20T06:47:18Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-20T06:49:09Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:86d042e6b95cb9a0

> **✅ gate:risk_evaluated** run=2026-07-20T06:49:09Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1167/risk_evaluated_2026-07-20T06:49:09Z-risk_evaluated-a1.log`
