---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: [t1603_3]
issue_type: feature
status: Implementing
labels: [board, gates, ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1595
implemented_with: claudecode/opus5
created_at: 2026-08-30 13:29
updated_at: 2026-09-01 15:33
---

## Context

Part of t1603. The in-flight card carries only a **compact** gate progress
summary (t1603_3) because a card is a narrow surface. This child provides the
full passed / current / pending gate list on an expanded surface, so the detail
is reachable without overcrowding the card.

Consumes t1603_2's model and adds **no new derivation**.

Depends on t1603_3.

## Design decision: reuse the detail screen, invent nothing

The surface is a new `Gates (<n>)` **collapsible section in the existing
`TaskDetailScreen`**, built by a `_build_gate_fields(meta)` helper alongside the
four that already exist (`_build_risk_fields` / `_build_relations_fields` /
`_build_tracking_fields` / `_build_lockfiles_fields`, ~lines 6492-6640) and
mounted in `compose` beside them (~lines 6700-6726). Placed **after Risk, before
Dependencies & hierarchy**. Collapsed by default, like every other section.

This settles four otherwise-open questions at zero cost:

- **Invocation / binding:** none is added. `enter` on a focused card already
  routes through `KanbanApp.open_task_detail` (~line 10526), and an
  `InFlightTaskCard` is a `TaskCard` with no `trail_entry`, so it takes that
  path today.
- **Focus return:** already handled — `open_task_detail` receives
  `source_card=focused` and the board's `_queue_refocus` restores focus on
  close. No new lifecycle.
- **Section omission:** the `if fields:` guard every existing section uses means
  a task with nothing to report grows no empty section.
- **Arrow-nav order:** a new section shifts field navigation, so
  `tests/test_board_detail_arrow_nav.py` and
  `tests/test_board_detail_collapsible.py` are the sibling guards to update in
  the same commit.

## State semantics — "passed" means EFFECTIVE, not historical

This is the crux. Iterate `state.active_gates` and classify each from the
**same** effective view t1603_2 uses, so the expanded list and the compact chip
can never disagree:

| Rendered as | Condition |
|---|---|
| `✓ <gate>` passed | `current[g].status == "pass"` and `g not in stale_signed` |
| `⚠ <gate>` pass, signature stale — needs re-sign | `g in stale_signed` |
| `⊘ <gate>` skipped (not applicable) | `current[g].status == "skip"` |
| `✗ <gate>` failed | `status in ("fail", "error")` |
| `◈ <gate>` pending — needs attended agent | pending and registry `kind: procedure` |
| `· <gate>` pending | in `archive_pending`, otherwise |

The stale row must show **both facts, never one without the other** — the ledger
really does say `pass`, AND the signature no longer binds the current code. This
is spelled out in `gate_ledger.py:167-174`; showing only one is the exact
disagreement this surface exists to remove.

`skip` is terminal-satisfied but stays **distinct from pass** in the display, as
it is in the ledger.

Gates in `state.filtered_gates` are listed **last, under an explicit
"filtered by profile (audit only)" label**, and are excluded from every count —
the `TaskGateState` contract is that a historical run of a filtered gate must
never drive a classification.

## Degraded and error rendering

Shared with the card (specified once here):

- `result.error` non-empty → a single row `Gate state unavailable: <error>`.
  No list, no counts.
- `has_ledger` false → `No gate ledger — <phase> (<provenance>)`, using
  t1603_2's provenance, rather than an empty list or a fabricated `0/0`.

## Key Files to Modify

- `.aitask-scripts/board/aitask_board.py` — `_build_gate_fields`, and its mount
  in `TaskDetailScreen.compose`.
- `tests/test_board_detail_gates_section.py` — new.
- `tests/test_board_detail_arrow_nav.py`, `tests/test_board_detail_collapsible.py`
  — update in the same commit.

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py:6492` `_build_risk_fields` — the
  shortest read-only section builder; copy its shape.
- `.aitask-scripts/lib/gate_ledger.py:156-190` — `TaskGateState` and the
  docstring stating the active-set and stale-signature rules.
- `tests/test_board_detail_followup_kind.py` — detail-screen test idioms
  (`_settle`, `#meta_editable` placement assertions, app-free render harness).

## Verification

- one test per row of the classification table, driven from **real task
  fixtures** rather than hand-built `TaskGateState` objects — a hand-built state
  can encode a combination the real parser never produces;
- the filtered-gates audit block is present but uncounted;
- the error and no-ledger renderings asserted as text;
- section omission asserted by **widget absence**, not a blank widget;
- a **cross-surface parity test**: the section's satisfied count equals the card
  chip's numerator for the same task. This is what pins "the expanded list and
  the compact chip can never disagree" as executable rather than aspirational;
- the arrow-nav and collapsible sibling guards still pass.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
line.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T12:33:11Z status=pass attempt=1 type=human
