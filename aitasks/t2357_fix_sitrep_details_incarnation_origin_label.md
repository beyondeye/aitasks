---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [sitrep]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2337
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-24 22:14
updated_at: 2026-11-25 12:21
---

## Origin

Spawned from t2350 during Step 8b review.

## Upstream defect

- `.aitask-scripts/sitrep_tui/sitrep_tui_model.py:800` (`ORIGIN_LABELS`) with `.aitask-scripts/sitrep_tui/sitrep_tui_app.py` `_field`: the writer accepts the origin key `incarnation` (`lib/sitrep_todo.py:148` `ORIGIN_KEYS`), which has no label entry. Its row in an item's details (Context → Origin) renders the label as `"  incarnation"`. That is 13 cells, wider than the 12-cell label pad (`_LABEL_W`), so the value runs straight into the label (`  incarnation<value>`).

## Diagnostic context

t2350 added a `Frozen` details field and found that `_field` pads the label with `ljust(_LABEL_W)` and then appends the value directly. A label of 12 or more cells, indent included, therefore leaves no separator. t2350 avoided it for its own field (label `Frozen`). The Origin sub-rows pass `ORIGIN_LABELS.get(key, key)` with a two-space indent, and `incarnation` is the one accepted key with no label mapping. It falls back to the raw 11-character key, which makes 13 cells with the indent.

## Suggested fix

Add `"incarnation": "Incarnation"` (or a shorter label) to `ORIGIN_LABELS`. Make `_field` always leave at least one space between label and value, for example `label.ljust(_LABEL_W - 1) + " "`, which renders every existing label of 11 cells or fewer byte-identically. Then add a render test that pins the separator for the longest label.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-25T10:21:48Z status=pass attempt=1 type=human
