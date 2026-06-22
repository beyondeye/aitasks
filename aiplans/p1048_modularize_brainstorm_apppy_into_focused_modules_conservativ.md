---
Task: t1048_modularize_brainstorm_apppy_into_focused_modules_conservativ.md
Base branch: main
plan_verified: []
---

# t1048 — Modularize `brainstorm_app.py` (conservative extraction)

## Context

`.aitask-scripts/brainstorm/brainstorm_app.py` is **9,163 lines / ~362 KB** — too
large to navigate or edit safely. This task pulls the clean, low-coupling pieces
out into focused sibling modules while leaving the two big stateful classes
(`BrainstormApp` ~4,350 lines and `ActionsWizardScreen` ~1,570 lines) **in place**.
A deeper decomposition (per-tab app modules, wizard dependency-injection) is
explicitly out of scope and noted as a follow-up.

This is a **mechanical, behaviour-preserving** refactor: no UX changes. Depends on
t1047 (the three wizard/preview UX fixes), which has **already landed** (archived;
commit `925657d9d`).

### Why this is safe (validated during planning)

- **Coupling is one-directional.** Every `BrainstormApp` / `ActionsWizardScreen`
  reference in the extractable code is a *comment/docstring* — the only real code
  refs are the App instantiating the wizard and `__main__`. Extracted widgets/modals
  reach the app only at **runtime via `self.app`** (attribute access, not an
  import). So the new modules never import back into `brainstorm_app.py`.
- **No widget→modal cycle.** Every `push_screen(...)` in the extractable region
  lives inside a *modal* class, never a pure widget. Lazy imports
  (`from section_viewer import SectionViewerScreen`, `diffviewer...`) sit inside
  methods and move with them. Clean DAG:
  `constants → utils → widgets → modals → brainstorm_app`.
- **External import surface preserved.** 32 test files do
  `from brainstorm.brainstorm_app import <Name>`. `brainstorm_app.py` will
  **re-import every extracted public name** back into its namespace, so
  `brainstorm_app.<Name>` still resolves byte-for-byte. **No test file changes.**
- **CSS stays app-wide.** `BrainstormApp.CSS` (a Textual App stylesheet) applies to
  every widget/pushed-modal in the app regardless of which file defines the class.
  Moving the string to `styles.py` and assigning `CSS = APP_CSS` is behaviour-
  identical. The 5 classes that already carry their own `DEFAULT_CSS`
  (`DeleteNodeModal`, `CleanupAgentModal`, `_NumberedProposal`, `ProposalPreviewPane`,
  `DimensionRow`) keep it **verbatim**; the move does not change any modal's runtime
  styling (see "Modal CSS handling" below for why app-CSS-only modals stay that way).
- **Shortcut-scope registration untouched.** `_shortcuts_scope = "brainstorm"` lives
  only on `ActionsWizardScreen` and `BrainstormApp`, both of which **stay put**, so
  the `lib/shortcut_scopes.py` `KNOWN_BINDING_SOURCES` entry for `brainstorm_app`
  remains valid (importing `brainstorm_app` still transitively registers everything).

## Target module layout (flat single-file modules)

All under `.aitask-scripts/brainstorm/`:

| New module | Contents | Imports from |
|---|---|---|
| `constants.py` | Pure data: `STATUS_COLORS`, `AGENT_STATUS_COLORS`, `RUNNER_STATE_DISPLAY`, `AIT_PATH`, op-state sets (`_TERMINAL_AGENT_STATES`, `_NODE_SELECT_OPS`, `_NODE_SELECT_STEP_OPS`, `_SUBGRAPH_SELECT_OPS`, `_WIZARD_OP_TO_AGENT_TYPE`, `_SINGLE_NODE_OPS`, `_MODULE_OPS`, `_MULTI_NODE_OPS`, `_*_REASON`), `_DESIGN_OPS`, `_SESSION_OPS`, `_OP_LABELS`, `_OPERATION_HELP`, browse view consts (`BROWSE_DEFAULT_VIEW`, `BROWSE_VIEWS`, `BROWSE_VIEW_TO_PANE`, `BROWSE_PANE_TO_VIEW`), `NODE_HUB_OPERATIONS`, `NODE_HUB_COMPARE`, `NodeHubResult`, `_WizardStep`, `_WIZARD_STEPS`, `_WIZARD_STEPS_BY_ID` | stdlib only |
| `utils.py` | Pure functions + the `NodeSelection` model: `derive_runner_state`, `format_status_strip`, `_brainstorm_launch_mode_default`, `_sections_intersection`, `_parse_section_label`, `_parse_dimension_label`, `_read_groups`, `detect_stale_crew_branch` (+`_STALE_CREW_BRANCH_RE`), `_open_node_detail_visible`, `_validate_export_dir`, `_export_filename`, `_write_node_exports`, `_next_checkbox_index`, `compare_matrix_rows`, `_filter_labels`, `_nodes_for_subgraph`, `active_step_ids`, `step_position`, `next_step_id`, `prev_step_id`, `op_states_for_selection`, `format_node_id_summary`, `browse_toggle_view`, `_format_progress_bar`, `NodeSelection` | `constants`, brainstorm_dag/sections/schemas, launch_modes |
| `styles.py` | `APP_CSS = """…"""` — the central CSS block (current lines 4887–5576) moved **verbatim** | none |
| `widgets.py` | Textual widgets (non-modal): `_PreviewMinimap`, `_NumberedProposal`, `ProposalPreviewPane`, `FuzzyCheckList`, `NodeRow`, `DimensionRow`, `render_node_detail_widgets`, `NodeDetailPanel`, `OperationRow`, `CycleField`, `GroupRow`, `StatusLogRow`, `AgentStatusRow`, `ProcessRow` (nested `Message` subclasses move with their widgets) | `constants`, `utils`, textual/rich, diffviewer, NumberedSourceView, PollingIndicator |
| `modals.py` | `ModalScreen`s + their helper trees: `_MarkdownOnlyDirectoryTree`, `ImportProposalFilePicker`, `InitSessionModal`, `InitFailureModal`, `DeleteSessionModal`, `DeleteNodeModal`, `CleanupAgentModal`, `NodeDetailModal`, `NodeHub`, `CompareMatrixModal`, `ExportNodeDetailModal`, `OperationDetailScreen`, `AgentModeEditModal`, `LogDetailModal`, `OperationHelpModal`, `NodeActionSelectModal`, `ModulePreviewScreen` | `constants`, `utils`, `widgets`, brainstorm_session/crew/dag, agentcrew utils |
| `brainstorm_app.py` (kept) | `ActionsWizardScreen`, `BrainstormApp`, `__main__`; `CSS = APP_CSS`; re-import block | all five new modules |

Estimated result: `brainstorm_app.py` ≈ **5,000 lines** (from 9,163) — materially smaller.

## Module bootstrap & import ordering (must-follow)

The established convention for sibling modules is **self-bootstrap**: each
`brainstorm/*.py` inserts the package roots into `sys.path` *before* its
`from brainstorm.* / from agentcrew.*` imports (e.g. `brainstorm_session.py:23`,
`brainstorm_dag_display.py:14-15` insert `..` and `../lib`). The new modules
**must do the same** at their top:

```python
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
# ...then package imports (from brainstorm.constants import …, textual, etc.)
```

This makes them import-order-independent (works under `ait brainstorm` direct
script launch, package-style test imports, and inter-module imports alike).

In `brainstorm_app.py`: **leave the existing `sys.path.insert(...)` bootstrap at
the top untouched**, and place the new re-import block **with the other
`from brainstorm.* import` lines (lines ~52–113), strictly AFTER the bootstrap** —
never above it. (Inserting a `from brainstorm.styles import …` above the bootstrap
would let package-style tests pass while the direct launcher fails.)

## Implementation steps

Work on the current branch. Order is bottom-up so each module imports only
already-created modules.

1. **`constants.py`** — create with `from __future__ import annotations`; move the
   pure-data blocks listed above (current ranges ≈ 141–211, 263–528, 1356–1360,
   2143–2189, 2320–2357). Add only the imports the data needs (`typing.NamedTuple`).

2. **`utils.py`** — move the pure functions + `NodeSelection`. Add `from
   brainstorm.constants import …` for the op-state sets / wizard steps the functions
   reference, plus the brainstorm_dag/sections/schemas + launch_modes imports those
   functions use. Keep lazy in-method imports as-is.

3. **`styles.py`** — move the CSS string verbatim as `APP_CSS`. **Do not reorder or
   "organize"** the rules (CSS ordering affects specificity ties — a verbatim move
   guarantees identical rendering; reorganization is a separate, riskier task).

4. **`widgets.py`** — move the widget classes + `render_node_detail_widgets`. Import
   from `constants`/`utils` and the textual/rich/diffviewer/NumberedSourceView/
   PollingIndicator names each widget uses.

5. **`modals.py`** — move the modal classes + `_MarkdownOnlyDirectoryTree`. Import
   from `constants`/`utils`/`widgets` and the session/crew/dag/agentcrew names.

6. **`brainstorm_app.py`** — delete the moved code; keep `ActionsWizardScreen`,
   `BrainstormApp`, `__main__`. Replace the inline `CSS = """…"""` with
   `from brainstorm.styles import APP_CSS` and `CSS = APP_CSS` on the class. Add the
   **re-import block** (all extracted public names, `# noqa: F401`) with the existing
   `from brainstorm.*` imports — **after** the bootstrap (see ordering rule above) —
   so the test import surface is preserved. Ensure `ActionsWizardScreen`/
   `BrainstormApp` bodies reference the now-imported `OperationRow`, `CycleField`,
   `FuzzyCheckList`, `NodeActionSelectModal`, etc.

7. **Trim now-unused imports** in `brainstorm_app.py` (e.g. textual widgets only used
   by moved classes) — but **keep** any name still referenced by the re-export block
   or the staying classes. **Critically: keep `from launch_modes import
   DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES`** even though `_brainstorm_launch_mode_default`
   moves to `utils.py` — `DEFAULT_LAUNCH_MODE` is part of the external test import
   surface (re-exported, see below). Leave the `sys.path.insert(...)` bootstrap intact.

### Re-import block (the external surface — derive mechanically, do not hand-trust this list)

The load-bearing surface is **every name any test/shell-test imports from
`brainstorm_app`** (51 names, mechanically derived). Regenerate it during
implementation rather than copying a static list, then ensure each name resolves as
`brainstorm.brainstorm_app.<name>`:

```bash
# Regenerate the authoritative keep-set:
grep -rhoE "from brainstorm\.brainstorm_app import [^#]*|brainstorm_app import \w+" tests/ | ...
```

- **Third-party re-export (easy to lose to import-trimming):** `DEFAULT_LAUNCH_MODE`
  — imported from `brainstorm_app` by tests, but actually defined in `launch_modes`.
  It survives only because `brainstorm_app.py` imports it; keep that import (step 7).
- `constants`: `STATUS_COLORS, AGENT_STATUS_COLORS, RUNNER_STATE_DISPLAY, _DESIGN_OPS,
  _SESSION_OPS, _OP_LABELS, _OPERATION_HELP, BROWSE_DEFAULT_VIEW, BROWSE_VIEWS,
  NODE_HUB_OPERATIONS, NODE_HUB_COMPARE, NodeHubResult` (+ remaining data names used
  internally).
- `utils`: `derive_runner_state, format_status_strip, _sections_intersection,
  _parse_section_label, _parse_dimension_label, detect_stale_crew_branch,
  _open_node_detail_visible, _validate_export_dir, _export_filename, _write_node_exports,
  _next_checkbox_index, compare_matrix_rows, _filter_labels, _nodes_for_subgraph,
  active_step_ids, step_position, next_step_id, prev_step_id, op_states_for_selection,
  browse_toggle_view, NodeSelection, _format_progress_bar`.
- `widgets`: `_PreviewMinimap, _NumberedProposal, ProposalPreviewPane, FuzzyCheckList,
  NodeRow, DimensionRow, render_node_detail_widgets, NodeDetailPanel, OperationRow,
  CycleField, GroupRow, StatusLogRow, AgentStatusRow, ProcessRow`.
- `modals`: `_MarkdownOnlyDirectoryTree, ImportProposalFilePicker, InitSessionModal,
  InitFailureModal, DeleteSessionModal, DeleteNodeModal, CleanupAgentModal,
  NodeDetailModal, NodeHub, CompareMatrixModal, ExportNodeDetailModal,
  OperationDetailScreen, AgentModeEditModal, LogDetailModal, OperationHelpModal,
  NodeActionSelectModal, ModulePreviewScreen`.

A re-export guard (verification, below) asserts the full set post-refactor.

### Modal CSS handling (conservative, behaviour-preserving)

- **Preserve verbatim** the 5 classes that already own a `DEFAULT_CSS`:
  `DeleteNodeModal`, `CleanupAgentModal` (modals) and `_NumberedProposal`,
  `ProposalPreviewPane`, `DimensionRow` (widgets). Move the attribute with the class.
- **App-CSS-only extracted modals stay app-CSS-only this pass** (e.g.
  `NodeActionSelectModal`, `NodeDetailModal`, `OperationDetailScreen`,
  `CompareMatrixModal`, `ExportNodeDetailModal`, `InitSessionModal`,
  `InitFailureModal`, `DeleteSessionModal`, `OperationHelpModal`, `AgentModeEditModal`,
  `LogDetailModal`, `ModulePreviewScreen`, `ImportProposalFilePicker`). Justification:
  (1) they are only ever **pushed at runtime by `BrainstormApp`**, whose `CSS`
  (=`APP_CSS`) styles them app-wide regardless of defining file; (2) moving the class
  does **not** change its runtime styling — the App↔modal relationship is identical;
  (3) the existing modal tests boot these under a **minimal host app** (not full
  `BrainstormApp`) *today* and assert **content/behaviour** (`op_disabled`,
  `can_focus`, `render()` text, reason strings) — not app-CSS layout — so they already
  pass without `BrainstormApp.CSS` and the move introduces no regression.
- Giving app-CSS-only modals their own `DEFAULT_CSS` (for cross-App reuse hardening
  per `tui_conventions.md`) is a **behaviour-neutral enhancement deferred to a
  follow-up** — it would require extracting per-modal rules from the central block
  (drift risk) and is not needed for a verbatim, behaviour-preserving move.

## Verification (in-task; live smoke is a pre-archive gate)

Run **before & after** where noted; all must pass **before Step 9 archival**.

1. **Smoke import** (catches NameErrors / circular imports / missed module-level refs):
   `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts'); sys.path.insert(0,'.aitask-scripts/lib'); import brainstorm.brainstorm_app"` — must succeed.
2. **Re-export guard** (proves the external surface is intact, C1): assert every
   mechanically-derived name resolves on the module:
   ```bash
   python3 -c "import sys; sys.path[:0]=['.aitask-scripts','.aitask-scripts/lib']; \
     import brainstorm.brainstorm_app as m; \
     names=[...]  # the 51-name keep-set derived from tests; \
     missing=[n for n in names if not hasattr(m,n)]; \
     assert not missing, missing; print('re-export OK', len(names))"
   ```
   (Including `DEFAULT_LAUNCH_MODE`.) Capture the keep-set with the grep in the
   re-import section so it can't silently drift.
3. **Full brainstorm test suite (before & after):** capture a green baseline on the
   current tree first, then re-run every `tests/test_brainstorm_*.py` and the `.sh`
   ones post-refactor — the pass set must be **identical**.
   - Spot-critical: `test_brainstorm_binding_scope.py` (boots a real `BrainstormApp`
     — guards scope registration), `test_brainstorm_proposal_preview.py`,
     `test_brainstorm_node_detail_panel.py`, `test_brainstorm_node_action_modal.py`
     (minimal-host modal render), `test_brainstorm_wizard_steps.py`,
     `test_brainstorm_node_selection.py`, `test_brainstorm_node_export.py`,
     `test_brainstorm_compare_overlay.py`.
4. **Launcher unchanged:** `aitask_brainstorm_tui.sh` still `exec`s
   `brainstorm/brainstorm_app.py`; confirm `ait brainstorm` launches.
5. **Live-smoke GATE (proves the primary AC, C4):** in this session, launch
   `ait brainstorm` and exercise Browse (graph/list + node-op wizard), proposal
   preview + minimap, Session tab, and Running-tab polling — confirm identical
   behaviour. This is a **pre-archive gate**: t1048 is not archived until the live
   smoke passes (or, only if the environment genuinely cannot launch a TUI here, the
   blocker is documented in the plan's Final Implementation Notes and the smoke is
   carried entirely by the follow-up task). The follow-up `manual_verification` task
   (Step 8d) is a **recorded regression backstop**, not a substitute for this gate.

## Step 9 (Post-Implementation)

Standard cleanup, merge approval, and archival per the shared workflow. No branch/
worktree (current-branch profile). Do not archive until the verification gate (esp.
the live smoke) passes.

## Risk

### Code-health risk: medium
- Large mechanical move (~3,850 lines across 5 new modules) risks a missed import or module-level NameError on a runtime path not covered by unit tests (e.g. a rarely-hit modal) · severity: medium · → mitigation: brainstorm_modularize_live_smoke
- CSS block relocated to `styles.py`; an accidental reorder could shift specificity-tie rendering · severity: low (mitigated by verbatim move) · → mitigation: brainstorm_modularize_live_smoke

### Goal-achievement risk: low
- Approach validated in planning (one-way DAG, no cycles, re-export preserves the surface); AC fully covered. None of material concern.
- None identified.

### Planned mitigations
- timing: after | name: brainstorm_modularize_live_smoke | type: manual_verification | priority: medium | effort: low | addresses: code-health (runtime NameError on a UI path unit tests don't cover) | desc: Regression backstop (the in-session live-smoke gate already proves the AC) — re-run a live smoke of `ait brainstorm` exercising Browse (graph/list + node-op wizard), proposal preview + minimap, Session tab, and Running-tab polling to catch any deferred runtime regression.

## Out of scope (potential follow-up)

- Splitting `BrainstormApp` into per-tab (Browse/Session/Running) modules.
- Extracting `ActionsWizardScreen` with injected dependencies (removing `self.app`
  coupling).
- Splitting `widgets.py` / `modals.py` into `widgets/` + `modals/` sub-packages.
- "Organizing" the CSS (moved verbatim here).
