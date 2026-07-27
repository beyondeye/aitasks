---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: codex/gpt5_6_sol
created_at: 2026-07-27 09:15
updated_at: 2026-07-27 12:54
---

## Problem

A `manual_verification` task whose `## Verification Checklist` section is
authored with plain `- ` bullets (rather than `- [ ]` checkbox items) parses as
`TOTAL:0`, and the workflow's only offered recovery cannot run.

- `aitask_verification_parse.py:33` — `ITEM_RE` requires `- [<marker>] text`, so
  plain bullets yield zero items.
- `aitask_verification_parse.py:32` — `SECTION_RE` **does** match the heading
  (case-insensitively), so `cmd_seed` hard-fails with
  `verification checklist section already exists`.
- `manual-verification.md` §1 — the `TOTAL:0` branch offers only
  "Seed from plan" or "Abort". Seeding is impossible per the above, so the task
  is stuck unless the bullets are hand-converted.

Hit live at the start of the t635_27 verification run: t635_27 authored its
6-item checklist with plain bullets and had to be converted by hand before the
runner could track state.

## Fix direction

Either:
1. Let `seed` rewrite/convert an existing section (e.g. `--force` / `--convert`,
   preserving bullet text verbatim), or
2. Add a "Convert existing bullets to checklist items" option to the `TOTAL:0`
   branch in `manual-verification.md`, backed by a helper verb.

Option 2 is preferable — the items are already authored and correct; only the
syntax is wrong, so re-deriving them from the plan would lose task-authored text.

## Also worth considering

`ait create --verifies` / the manual-verification task templates should emit
`- [ ]` items so newly created verification tasks cannot land in this state.

## Verification

Test: a task file with a `## Verification checklist` of plain bullets is
converted to trackable items with text preserved verbatim, and `summary` then
reports the right `TOTAL`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-27T09:54:21Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-07-27T09:54:21Z status=pass attempt=1 type=machine
