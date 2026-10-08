---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini, tui, opencode]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1892
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 12:27
updated_at: 2026-10-08 16:49
---

## Origin

Spawned from t1908 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/concern_parser.py:_scan_items` — body continuation
  rows are always space-joined (`" ".join(parts)`).
  - A renderer that hard-wraps with literal newlines *inside a token*
    corrupts the body. Measured: OpenCode 1.18.34 breaks after `history.`
    and after `follow-`, giving `history. csv`.
  - When the break lands in the terminal trailer
    (`Disposition: follow-` / `up.` → `follow- up`), `_TRAILER_SPAN` fails to
    match. Disposition, improves, worsens and effort are all lost: the
    concern shows an unspecified disposition and no impact vector (the safe
    direction, but the pricing signal is gone).
  - Codex hard-wraps with literal newlines too.
  - `_join_sep`'s `-`/`/` intra-token rule is applied only inside split
    markers, never to body continuations.

## Diagnostic context

t1908 ran a live production OpenCode shadow (`>pc` on a deliberately flawed
plan), captured with `aitask_shadow_capture.sh --deep`, and compared each
concern field-by-field against the raw `opencode export` source.

- All markers recovered: 4/4 items, with exact priority, region and round.
- **Items 1–2:** bodies differed only by `history. csv` vs `history.csv`.
- **Item 4:** `Disposition: follow- up.` lost the whole trailer.

OpenCode draws every row itself, so `tmux capture-pane -J` cannot rejoin
these rows. The same holds for any renderer that emits literal newlines. The
evidence is recorded in the t1908 plan's Final Implementation Notes and in
`concern-format.md` ("Measured renderers → OpenCode → Residual").

## Suggested fix

Two candidate directions:

- Apply `_join_sep`'s rule to body continuation joins, so a row ending in `-`
  or `/` joins with no space.
- Alternatively, or as well, let the trailer grammar tolerate the wrap:
  accept `follow-\s*up` and whitespace inside impact entries.

The `history.` / `csv` break is genuinely ambiguous with a sentence end. Leave
it cosmetic unless a measured rule disambiguates it. Measure the change
against a real OpenCode and a real Codex capture before shipping.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-08T13:49:08Z status=pass attempt=1 type=human
