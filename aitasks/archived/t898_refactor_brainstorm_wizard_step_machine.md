---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Done
labels: [ait_brainstorm, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 18:59
updated_at: 2026-06-02 07:50
completed_at: 2026-06-02 07:50
---

Refactor the `ait brainstorm` wizard step machine in
`.aitask-scripts/brainstorm/brainstorm_app.py` from the current fragile
integer-indexed `_wizard_step` model into a robust, declarative step model
that makes adding **optional / conditional** steps trivial and safe.

## Why (motivation)
The wizard currently tracks progress with a bare integer `self._wizard_step`
(1, 2, 3, … `_wizard_total_steps`). Step identity is reconstructed at every
site by comparing that integer against hardcoded literals, scattered across at
least five places:
- Esc/back handler — `on_key`, ~line 3118 (`if step == total`, `step == total-1`,
  `step == 3 and _wizard_has_sections`, `step == 2` …).
- Enter dispatch — `on_key`, ~line 3150 (`_wizard_step == 1` selects op,
  `_wizard_step == 2` selects node, Tab-cycle for compare/synthesize at step 2,
  up/down navigation gated on `_wizard_step in (1, 2)`).
- Back button — `_on_actions_back`, ~line 6118 (mirror of the Esc ladder).
- Advance — `_actions_advance_*`, ~line 6196.
- `_set_total_steps`, ~line 5531 — recomputes the count per op family.

Adding a single optional step means editing every one of those integer ladders
and risking off-by-one "step renumbering" bugs. The existing optional
section-select step already shows the pattern (it independently recomputes
`_wizard_total_steps` and hardcodes step 3). Anyone editing the wizard unaware
of all five sites can silently break Back/Esc navigation. This was flagged as a
blast-radius hazard while starting t756_2 (module-aware wizard): inserting the
subgraph-selector step there required touching ~6 handlers, so t756_2 was paused
and this refactor pulled ahead of it (see "Dependency / sequencing").

## Goal
Replace the integer ladder with an explicit, ordered **step descriptor** model
driven by a small generic engine, so that:
- Each step is a declarative descriptor: stable `id`, render callable, optional
  `predicate(ctx)` deciding whether it is active for the current op/session
  (e.g. section-select active only when the chosen node has sections; the
  upcoming module subgraph-selector active only when there are 2+ subgraphs),
  and its
  back/next neighbours derived from the active-step sequence — NOT hardcoded
  integers.
- Next / Back / Esc / step-indicator ("Step X of Y") / up-down navigation are
  computed generically from the active-step list. Inserting a new optional step
  becomes "add one descriptor + predicate", touching no existing handler.
- The displayed "Step X of Y" count is derived from the count of *active* steps
  for the current path (so auto-skipped optional steps don't leave gaps).

## Scope / key file
- `.aitask-scripts/brainstorm/brainstorm_app.py` — the wizard step methods
  (`_actions_show_step1`, `_actions_show_step2`, `_actions_show_node_select`,
  `_actions_show_section_select`, `_actions_show_config`, `_actions_show_confirm`),
  `_set_total_steps`, the `on_key` Esc/Enter/navigation branches, the mouse-click
  dispatch (`on_operation_row_activated`), the Next/Back buttons
  (`_on_actions_next` / `_on_actions_back`), and `_actions_advance_from_node_select`.
- The module subgraph-selector is intentionally NOT in scope here — it is added
  by t756_2 *on top of* the model this task delivers.

## Constraints
- Pure-behaviour-preserving refactor: every existing wizard path (explore,
  compare, synthesize, detail, patch + the session-lifecycle ops) must behave
  identically, including Esc/Back ladders, Tab cycling on compare/synthesize
  config, and the optional section-select step.
- Follow `aidocs/tui_conventions.md`.
- Extract the step-sequencing logic into pure, unit-testable helpers where
  possible (precedent: `_filter_labels`, tested without a running App in
  `tests/test_brainstorm_wizard_filter.py`).

## Dependency / sequencing
**Do this BEFORE the module wizard work.** Originally gated behind the whole
t756 feature, but that was backwards: the t756_2 subgraph-selector, t756_3's new
ops, and the D-phase wizard changes would each have to fight the integer ladder.
Landing this robust step model *first* means every one of those builds on it
cleanly instead of adding more integer-ladder workarounds. Concretely, **t756_2
(module-aware wizard) now depends on this task** and resumes once it lands; this
task itself has no dependency on the module feature (it is a behaviour-preserving
refactor of the *current* wizard).

## Verification
- Existing brainstorm wizard tests still pass:
  `tests/test_brainstorm_wizard_filter.py`,
  `tests/test_brainstorm_wizard_sections.py`, plus the broader brainstorm suite.
- Add unit tests for the new step-sequencing engine (active-step computation,
  next/back resolution, "Step X of Y" derivation) without a live TUI.
- Manual: drive each op's wizard end-to-end in a multi-subgraph session per
  `aidocs/tui_conventions.md`; confirm Esc/Back/Enter and the step indicator are
  unchanged from pre-refactor behaviour.
