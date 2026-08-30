---
Task: t1603_4_expanded_gate_surface_in_task_detail.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_1_*.md, aitasks/t1603/t1603_2_*.md, aitasks/t1603/t1603_3_*.md, aitasks/t1603/t1603_5_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1603_4 — Expanded gate surface

## Context

The in-flight card carries only a **compact** progress summary because a card is
a narrow surface. This child provides the full passed / current / pending gate
list on an expanded surface. Consumes t1603_2's model and adds **no new
derivation**. Depends on t1603_3.

## Design decision: reuse the detail screen, invent nothing

A new `Gates (<n>)` collapsible section in the existing `TaskDetailScreen`,
built by `_build_gate_fields(meta)` alongside the four existing builders
(`_build_risk_fields` / `_build_relations_fields` / `_build_tracking_fields` /
`_build_lockfiles_fields`, `aitask_board.py:6492-6640`) and mounted in `compose`
beside them (`:6700-6726`). **After Risk, before Dependencies & hierarchy.**
Collapsed by default.

This settles four otherwise-open questions at zero cost:

- **Invocation / binding:** none added. `enter` on a focused card already routes
  through `KanbanApp.open_task_detail` (`:10526`), and an `InFlightTaskCard` is
  a `TaskCard` with no `trail_entry`, so it takes that path today.
- **Focus return:** already handled — `open_task_detail` receives
  `source_card=focused` and `_queue_refocus` restores focus on close.
- **Section omission:** the `if fields:` guard every section uses means a task
  with nothing to report grows no empty section.
- **Arrow-nav order:** a new section shifts field navigation, so
  `tests/test_board_detail_arrow_nav.py` and
  `tests/test_board_detail_collapsible.py` are updated in the same commit.

## State semantics — "passed" means EFFECTIVE, not historical

Iterate `state.active_gates`, classifying from the **same** effective view
t1603_2 uses, so the expanded list and the compact chip can never disagree:

| Rendered | Condition |
|---|---|
| `✓ <gate>` passed | `current[g].status == "pass"` and `g not in stale_signed` |
| `⚠ <gate>` pass, signature stale — needs re-sign | `g in stale_signed` |
| `⊘ <gate>` skipped (not applicable) | `current[g].status == "skip"` |
| `✗ <gate>` failed | `status in ("fail", "error")` |
| `◈ <gate>` pending — needs attended agent | pending and registry `kind: procedure` |
| `· <gate>` pending | in `archive_pending`, otherwise |

The stale row shows **both facts, never one without the other** — the ledger
really says `pass`, AND the signature no longer binds the code
(`gate_ledger.py:167-174`). Showing only one is the disagreement this surface
exists to remove.

`skip` is terminal-satisfied but stays **visually distinct from pass**, as it is
in the ledger.

Gates in `state.filtered_gates` are listed **last under an explicit
"filtered by profile (audit only)" label** and excluded from every count — the
`TaskGateState` contract is that a historical run of a filtered gate must never
drive a classification.

## Degraded and error rendering (shared with the card)

- `result.error` non-empty → one row `Gate state unavailable: <error>`. No list,
  no counts.
- `has_ledger` false → `No gate ledger — <phase> (<provenance>)` from t1603_2,
  not an empty list and not a fabricated `0/0`.

Render gate names with `markup=False` / explicit `Text` — a gate name is
free-form and Rich markup would eat bracketed content.

## Verification

`tests/test_board_detail_gates_section.py`:

- one test per row of the classification table, driven from **real task
  fixtures** rather than hand-built `TaskGateState` objects;
- the filtered-gates audit block is present but uncounted;
- error and no-ledger renderings asserted as text;
- section omission asserted by **widget absence**, not a blank widget;
- **cross-surface parity**: the section's satisfied count equals the card chip's
  numerator for the same task — this is what makes "the expanded list and the
  compact chip can never disagree" executable rather than aspirational;
- the arrow-nav and collapsible sibling guards still pass.

`bash tests/run_all_python_tests.sh --test-dir tests` — read only the last line.

## Risk

### Code-health risk: low
- One new section builder following an established four-way pattern, plus two
  sibling-guard updates. No new screen, binding or focus lifecycle.
  · severity: low · → mitigation: none (accepted residual)

### Goal-achievement risk: low
- The classification table is fully specified and each row maps to a test; the
  only judgement left is glyph choice. · severity: low · → mitigation: none
  (accepted residual)

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header, archive the task and plan.
