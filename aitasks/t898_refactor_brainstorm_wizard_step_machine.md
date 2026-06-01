---
priority: medium
effort: high
depends: [756]
issue_type: refactor
status: Ready
labels: [ait_brainstorm, tui]
created_at: 2026-06-01 18:59
updated_at: 2026-06-01 18:59
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

Adding a single optional step (the t756_2 subgraph-selector; the earlier
section-select step) means editing every one of those integer ladders and
risking off-by-one "step renumbering" bugs. Anyone editing the wizard unaware
of all five sites can silently break Back/Esc navigation. This was explicitly
flagged as a blast-radius hazard during t756_2 (see
`aiplans/archived/p756/p756_2_*` "Design decisions" once archived).

## Goal
Replace the integer ladder with an explicit, ordered **step descriptor** model
driven by a small generic engine, so that:
- Each step is a declarative descriptor: stable `id`, render callable, optional
  `predicate(ctx)` deciding whether it is active for the current op/session
  (e.g. subgraph-selector active only when `len(list_subgraphs()) >= 2`;
  section-select active only when the chosen node has sections), and its
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
  `_actions_show_subgraph_select` [added in t756_2], `_actions_show_section_select`,
  `_actions_show_config`, `_actions_show_confirm`), `_set_total_steps`, the
  `on_key` Esc/Enter/navigation branches, and `_on_actions_back`.

## Constraints
- Pure-behaviour-preserving refactor: every existing wizard path (explore,
  compare, synthesize, detail, patch + the session-lifecycle ops) must behave
  identically, including Esc/Back ladders, Tab cycling on compare/synthesize
  config, and the optional section-select and subgraph-selector steps.
- Follow `aidocs/tui_conventions.md`.
- Extract the step-sequencing logic into pure, unit-testable helpers where
  possible (precedent: `_filter_labels` / `list_subgraphs`, tested without a
  running App in `tests/test_brainstorm_wizard_filter.py`).

## Dependency / sequencing
`depends: 756`. Do this AFTER the whole module-decomposition feature (t756)
lands. Phases B2 (t756_3, new ops), D1 (t756_5, status views) and D2 (t756_6,
fast-track preset) all keep touching the wizard; refactoring the step machine
mid-feature would thrash against those siblings. Once t756 is complete the step
set is stable and can be migrated wholesale.

## Verification
- Existing brainstorm wizard tests still pass:
  `tests/test_brainstorm_wizard_filter.py`,
  `tests/test_brainstorm_wizard_sections.py`, plus the broader brainstorm suite.
- Add unit tests for the new step-sequencing engine (active-step computation,
  next/back resolution, "Step X of Y" derivation) without a live TUI.
- Manual: drive each op's wizard end-to-end in a multi-subgraph session per
  `aidocs/tui_conventions.md`; confirm Esc/Back/Enter and the step indicator are
  unchanged from pre-refactor behaviour.
