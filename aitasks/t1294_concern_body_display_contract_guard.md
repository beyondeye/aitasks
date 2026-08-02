---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1037
created_at: 2026-07-28 12:56
updated_at: 2026-08-02 09:47
boardidx: 410
---

## Origin

Risk-mitigation ("after") follow-up for t1274, created at Step 8d after
implementation landed.

## Risk addressed

Code-health — canonical body vs display body is easy to misuse:

> Adding fields to the `Concern` NamedTuple and a `display_body()` split between
> "canonical body" and "shown body" introduces an easy-to-misuse distinction — a
> future caller reaching for `.body` on a display surface (or `display_body()`
> on the clipboard path) reintroduces the bug silently · severity: low

## Goal

t1274 split one field into two readings of the same text, with an
**asymmetric** rule that is currently enforced only by prose:

- `Concern.body` is **canonical** — exactly what the producer emitted, trailer
  included. `build_clipboard_payload()` re-renders it verbatim, so the followed
  agent receives the `Disposition:` / `Verified:` metadata intact. The clipboard
  path MUST use `body`.
- `Concern.display_body()` strips the terminal trailer span. Row rendering MUST
  use it, so the picker shows prose rather than metadata.

Both mistakes are silent. Using `display_body()` on the clipboard path deletes
the disposition from what the agent receives — the exact loss t1274 avoided by
not stripping at parse time. Using `.body` in a row re-inserts the trailer into
the picker, undoing the readability half of the feature. Neither breaks a test
today: the existing round-trip test pins the payload and the row test pins the
row, but nothing stops a *new* surface from picking the wrong one.

Write a guard that makes the rule structural rather than remembered. Options to
weigh at planning time (pick one, or a better one):

- A source-level guard test that enumerates the display surfaces
  (`_ConcernRow.render` in `.aitask-scripts/monitor/monitor_shared.py`) and the
  forward surfaces (`build_clipboard_payload` in
  `.aitask-scripts/monitor/concern_parser.py`), asserting each reads only its
  permitted accessor — with a **negative control** proving the guard fails when
  a surface is switched, per the repo's guard-test convention.
- A behavioural guard: drive every surface with a trailer-bearing `Concern` and
  assert the trailer is absent from every rendered row and present in every
  forwarded payload, so a new surface added to either list is covered
  automatically.

Prefer whichever keeps working when t1216_3 lands the **full monitor's** copy of
the picker — that second consumer is exactly the scenario this guard exists for.

## Verification

- The guard passes on the current tree.
- The guard **fails** when `_ConcernRow.render` is switched to `.body`, and when
  `build_clipboard_payload` is switched to `display_body()` — both demonstrated,
  not assumed.
