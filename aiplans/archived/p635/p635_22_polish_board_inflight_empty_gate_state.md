---
Task: t635_22_polish_board_inflight_empty_gate_state.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_23_port_gate_skills_codex_opencode.md, aitasks/t635/t635_24_remove_legacy_verify_build_path.md, aitasks/t635/t635_25_leaner_gate_check_invocation.md, aitasks/t635/t635_26_stats_gate_outcome_analytics.md
Archived Sibling Plans: aiplans/archived/p635/p635_10_monitor_gate_status_column.md, aiplans/archived/p635/p635_11_orchestrator_verifier_contract.md, aiplans/archived/p635/p635_12_build_test_machine_gates.md, aiplans/archived/p635/p635_13_risk_evaluation_gate_integration.md, aiplans/archived/p635/p635_14_profile_gate_declaration_unification.md, aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_20_stats_multistage_completion.md, aiplans/archived/p635/p635_21_gate_ledger_merge_safety.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md, aiplans/archived/p635/p635_4_gate_guarded_archival.md, aiplans/archived/p635/p635_5_ledger_driven_reentry.md, aiplans/archived/p635/p635_6_aitask_resume_skill.md, aiplans/archived/p635/p635_7_gate_aware_aitask_pick.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md, aiplans/archived/p635/p635_9_board_inflight_action_view.md
Base branch: main
plan_verified: []
---

# t635_22 — Polish board In-Flight empty/gate-state UI

## Context

After t635_9 added the board's In-Flight action view (`ait board` → `i`), a live
tmux inspection surfaced two UI polish defects in
`.aitask-scripts/board/aitask_board.py`:

1. **Operation-hint line is blank.** Each In-Flight card renders an
   operations-hint line built as `"  ".join(f"[{op}]" for op in ops)` →
   `[p pick]  [g resume]`. The `Label` is created with markup parsing on
   (the Textual default), so Rich treats `[p pick]` as a console-markup tag and
   swallows the bracketed text. Verified at render level on current code: the
   ops label's `render().plain` is `''`. Users can't see the available
   operations.
2. **"no gate ledger" copy is too technical.** A task that is `Implementing`
   but has no `## Gate Runs` section is correctly classified into *Agent can
   continue*, but its text reads "no gate ledger" — internal jargon. It should
   read "No gate information yet".

This task makes the operation hints render literally and replaces the technical
copy with clear, non-technical wording.

## Design notes (verified during planning)

- Textual `Static`/`Label` (v8.2.7) accept a `markup` kwarg. Constructing the
  ops `Label` with **`markup=False`** is the direct expression of intent — these
  shortcut hints are literal UI text, not markup — and keeps the helper output
  presentation-neutral (no Rich-escaping baked into returned strings). Proven:
  `Label("[p pick]", markup=False).render().plain == "[p pick]"`, whereas the
  default `markup=True` yields `""` (swallowed).
- A mounted `InFlightTaskCard` is queryable by class
  (`card.query_one(".inflight-ops", Label)`), and `label.render().plain`
  exposes the post-markup text — enabling a true render-level assertion that
  exercises `compose()` + `Label`, not just a helper string.

## Changes — all in `.aitask-scripts/board/aitask_board.py`

### 1. Render operation hints literally (bug 1)

In `InFlightTaskCard.compose` (currently lines ~1293–1299), extract the ops
assembly into a small staticmethod that returns **plain literal text** (no
escaping), and construct the Label with **`markup=False`**:

```python
@staticmethod
def _ops_hint(item: "InFlightItem") -> str:
    ops = ["p pick"]
    if item.has_ledger:
        ops.append("g resume")
    if item.human_gates:
        ops.append("s sign-off")
        ops.append("f fail")
    return "  ".join(f"[{op}]" for op in ops)
```

`compose` then yields:

```python
yield Label(self._ops_hint(self.item), classes="task-info inflight-ops", markup=False)
```

(The inline `ops = [...]` block in `compose` is replaced by the call.) Only the
ops Label needs `markup=False`; the other Labels in the card (title, action,
gate_summary, blockers) carry no markup tags and are left unchanged.

### 2. Friendlier no-gate copy (bug 2)

- `_inflight_item_for` (line ~761): change
  `next_action = "no gate ledger — pick/resume"` →
  `next_action = "No gate information yet — pick/resume"`.
- `_gate_summary` (line ~707–708): the `not result.has_ledger` branch currently
  returns `"no gate ledger"`. Return `""` instead. Rationale: the
  `next_action` line already carries the friendly "No gate information yet"
  message, and `InFlightTaskCard.compose` only renders `gate_summary` when it is
  non-empty (`if self.item.gate_summary:`). Returning `""` removes the awkward
  duplicate line on no-ledger cards (polish), while leaving the other branches
  (`"gate state unavailable"`, `"no recorded gates"`, the per-run summary)
  untouched. `_gate_summary` is board-internal and only consumed at the single
  `_inflight_item_for` call site, so this has no other blast radius.

## Tests — `tests/test_board_inflight_view.py`

Split cleanly between one model-level assertion and render-level assertions
(avoid re-checking the same model path twice):

- **Model level — update** `test_implementing_without_ledger_is_included`
  (line ~72): replace `assertIn("no gate ledger", ...)` with
  `assertIn("No gate information yet", items[0].next_action)` and add
  `self.assertEqual(items[0].gate_summary, "")`. This is the single model-level
  check for the friendly `next_action` + empty `gate_summary`. (Remove the
  separate redundant no-ledger model test — do not add one.)

- **Render level — new** tests that mount a real `InFlightTaskCard` and read
  `render().plain` (pattern proven during planning; uses a minimal host
  `App` whose `compose` yields the card, `app.run_test()`, then
  `card.query_one(".inflight-ops"/".inflight-action", Label)`):

  - `test_inflight_card_renders_literal_ops_and_friendly_copy` — no-ledger
    Implementing task: ops label `render().plain` contains `"[p pick]"` and
    **not** `"[g resume]"`; action label `render().plain` contains
    `"No gate information yet"` and **not** `"ledger"` (case-insensitive). This
    fails on current code (ops renders empty / action says "no gate ledger"),
    so it is a genuine negative control for both defects.
  - `test_inflight_card_renders_all_ops_for_pending_human` — Implementing task
    with `gates: [review_approved]` + `LEDGER_PENDING_HUMAN` (has_ledger=True,
    human_gates set): ops label `render().plain` contains all of `"[p pick]"`,
    `"[g resume]"`, `"[s sign-off]"`, `"[f fail]"`.

  Place these in a new `unittest.TestCase` (e.g. `InFlightCardRenderTests`)
  reusing the existing `_manager` / `_task` / `_body` / `LEDGER_PENDING_HUMAN`
  helpers; run the card inside an `asyncio.run` pilot like `InFlightPilotTests`.

## Risk

### Code-health risk: low
- Confined to In-Flight render strings, one `markup=False` Label flag, and a
  tiny staticmethod extraction in a TUI-only path; no behavioral/classification
  logic changes. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Acceptance criteria are crisp, both defect sites are located exactly, and the
  fix + render-level test approach were empirically verified against Textual
  8.2.7 during planning. · severity: low · → mitigation: TBD

## Verification

```bash
# Targeted unit/render tests for the In-Flight view
python tests/test_board_inflight_view.py

# Compile check
python -m py_compile .aitask-scripts/board/aitask_board.py tests/test_board_inflight_view.py

# Broader board/python suite stays green (AC: existing view/filter tests)
bash tests/run_all_python_tests.sh
```

Manual (optional): `ait board` → press `i`; confirm In-Flight cards show literal
`[p pick]` / `[g resume]` hints, and a no-ledger Implementing task reads
"No gate information yet — pick/resume" with no duplicate line.

## Post-implementation
Follow shared workflow Step 8 (review) → Step 9 (merge approval, gate
verification, archival) per `task-workflow-fast-/SKILL.md`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned in
  `.aitask-scripts/board/aitask_board.py`:
  1. `InFlightTaskCard.compose` now yields the ops-hint `Label` with
     `markup=False` and delegates assembly to a new `_ops_hint(item)`
     staticmethod that returns plain literal text (`[p pick]  [g resume]` …).
     This stops Rich from parsing the brackets as console-markup tags and
     swallowing them.
  2. `_inflight_item_for` no-ledger branch `next_action` → `"No gate
     information yet — pick/resume"`.
  3. `_gate_summary` no-ledger branch returns `""` (was `"no gate ledger"`),
     suppressing the now-redundant duplicate summary line (the action line
     carries the friendly copy).
  Tests in `tests/test_board_inflight_view.py`: updated
  `test_implementing_without_ledger_is_included` (friendly `next_action` +
  empty `gate_summary`) and added a new `InFlightCardRenderTests` class with two
  render-level tests that mount a real `InFlightTaskCard` and assert
  `Label.render().plain` (literal `[p pick]`/`[g resume]`/`[s sign-off]`/`[f
  fail]` hints, friendly action copy, no "ledger" jargon).
- **Deviations from plan:** None. (Plan was revised pre-approval per review
  concerns: chose `markup=False` over Rich-escaping, and a render-level test
  over a helper-only `Text.from_markup` test.)
- **Issues encountered:** None. The chosen fix and test approach were
  empirically validated against Textual 8.2.7 during planning (default
  `markup=True` renders the ops line as `''`; `markup=False` preserves
  `[p pick]`).
- **Key decisions:** Used Textual's `markup=False` Label flag (the direct
  expression of "literal UI text") rather than `rich.markup.escape()`, keeping
  `_ops_hint` presentation-neutral. Render-level tests via
  `card.query_one(".inflight-ops", Label).render().plain` exercise
  `compose()` + `Label` (catch helper-not-wired and markup regressions), unlike
  a helper-string test.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The render-level test pattern — mount a single
  card in a minimal `App` whose `compose` yields it, `app.run_test()`, then read
  `widget.render().plain` — is reusable for asserting any In-Flight/board card's
  *displayed* text (post-markup), and is more robust than asserting model
  fields. Two pre-existing, unrelated full-suite failures
  (`test_gate_orchestrator_registry` import-time `sys.exit`, and
  `test_tui_switcher_agent_launch` cross-import `isinstance` mismatch) are
  ordering/module-identity artifacts of `run_all_python_tests.sh`; both pass in
  isolation and are not caused by board changes.
