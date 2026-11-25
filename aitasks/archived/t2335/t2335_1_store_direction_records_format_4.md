---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [sitrep]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/fable5_2
created_at: 2026-11-19 05:12
updated_at: 2026-11-25 11:40
completed_at: 2026-11-25 11:40
---

## Context

First child of the sitrep work-directions task; read the parent for the confirmed decisions. A direction is the existing `theme` promoted to a first-class record. Today `todo.md` Part 1 holds `#### <theme>` blocks of free situation text (`store.situations`, the `situation` verb) and each context entry may name a `theme` (`lib/sitrep_todo.py`).

## Scope

- **Format 4** of `todo.md`: each theme block gains a fixed, strictly rendered header of direction fields before its situation text:
  - `title` (one line), `rank` (positive integer, unique among ranked directions; absent = unranked),
  - `trails` (0+ `art:trail-…` handles), `next` (0-1 task ref or item id, advisory),
  - `summary` (bounded one-paragraph text; the situation text stays the long form),
  - `digest`, `freshness` (`current|stale|unknown`), `checked_at`, `drift` (0+ `code|detail` reasons) — written only by the refresh verb below.
  Design the exact grammar in the plan; `render(parse(x)) == x` must hold, formats 1-3 are still read and upgraded by the first changing write, and a file using format-4 fields under an older `format=` is refused (the existing rule).
- **Membership is not stored twice**: a direction's members are the items whose context names its theme. Provide a read (`directions` list verb) that prints, per direction, the header fields and the member item ids with their state, plus the count and ids of open items naming no theme.
- **Writer verbs** (wire lines and exit codes in the wrapper header, like the existing verbs):
  - `direction-set <direction>`: create or update title / trails / next / summary, with `--expect-rev`. Directions need a rev: either one store-wide rev per direction or a documented reuse of the store rev; `STALE:` on mismatch.
  - `direction-rank`: set the whole order atomically from one ordered list (a per-direction rank write could leave duplicates or gaps); themes not named become unranked.
  - `direction-freshness --batch`: the refresh-only path writing digest / freshness / checked_at / drift, rev-checked, never touching agent-written fields.
  - removing a theme's situation (the existing delete path) must define what happens to its direction header and to members still naming the theme.
- Decide and document how the virtual `crashed-agents` theme relates to directions (parent, "Design constraints").
- The existing `situation` verb and `>w` keep working unchanged on a format-4 store.
- **Rename** (parent decision 5): format 4 writes the context key `direction:` instead of `theme:` and the verbs, flags, result lines and error texts say "direction"; formats 1-3 are read with `theme:`. List every surface that prints the old word (writer, `sitrep_cli.py`, harvest, refresh, TUI model, skill template, tests, docs) in the plan and say which child renames each one.

## Fixtures and tests

- `tests/fixtures/sitrep/`: the writer-produced fixture moves to format 4; keep a `store_v3/` read fixture beside `store_v1/` and `store_v2/`.
- `tests/test_sitrep_todo.sh`, `tests/test_sitrep_todo_format.py`: grammar round trip, upgrade on first changing write, no-op stays byte-identical, refused newer fields, atomic rank (duplicates, gaps, unknown theme), stale rev, freshness batch cannot change agent fields, theme deletion.
- Every consumer of `store.situations` and of the theme block grammar (TUI model, `sitrep_cli.py`, harvest, refresh, corpus `DryStore`) is audited and listed in the plan; the TUI must still read a format-4 store after this child even though the Directions tab lands later.

## Docs

`aidocs/framework/sitrep.md` ("The store", a new "Directions" section holding the record contract later children build on).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-25T07:50:21Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-25T09:36:10Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-25T09:40:43Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:b86fe6525d2f262e

> **✅ gate:risk_evaluated** run=2026-11-25T09:40:43Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2335_1/risk_evaluated_2026-11-25T09:40:43Z-risk_evaluated-a1.log`
