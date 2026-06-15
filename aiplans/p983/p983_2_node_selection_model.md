---
Task: t983_2_node_selection_model.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_2_node_selection_model
Branch: aitask/t983_2_node_selection_model
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-15 11:47
---

# p983_2 — Pure `NodeSelection` model

Child of t983 (brainstorm TUI IA redesign). **Testability-first centerpiece:**
land the headless selection model + exhaustive unit tests BEFORE any UI
consumer. Purely additive — the old single-selection `_current_focused_node_id`
keeps working until t983_3 wires this in.

## Context

The target IA (parent t983) replaces single-node selection with `space`-marking
(single OR multi); the new Operations dialog (t983_4) greys ops by selection
**cardinality**. Today selection is single-only via
`self._current_focused_node_id` (`.aitask-scripts/brainstorm/brainstorm_app.py`,
now `:3567`, read at 13 sites). This child lands the pure, headless selection
model first — no Textual dependency, exhaustively unit-tested — ahead of its UI
consumer. It does NOT touch any of the 13 existing `_current_focused_node_id`
sites; those keep working until t983_3.

## Verify-pass findings (plan re-checked against current code)

- The model is **purely additive** — it adds a new class + a new test file and
  modifies no existing code path. The plan's original line references shifted
  (`_current_focused_node_id` moved `:3453 → :3567`, "~10 sites" is now 13)
  because t983_1 landed, but none of that is load-bearing for an additive change.
- The template to mirror is intact and exactly as described: the wizard's pure
  model — `_WizardStep` NamedTuple + `_WIZARD_STEPS` list + module-level
  `active_step_ids` / `next_step_id` / `prev_step_id` / `step_position`
  (`.aitask-scripts/brainstorm/brainstorm_app.py:1796-1868`), unit-tested with
  zero Textual via plain ctx dicts in `tests/test_brainstorm_wizard_steps.py`.
- `tests/test_brainstorm_node_selection.py` does **not** yet exist (new file).
  The brainstorm suite is the family `tests/test_brainstorm*.py` (35 files).

## Design

Add a module-level `NodeSelection` class to
`.aitask-scripts/brainstorm/brainstorm_app.py`, placed alongside the other pure,
headless model (right after the wizard step helpers, ~`:1869`, before the modal
classes) so the I/O-free models live together. Mirror the wizard model's style:
plain class, reads/writes only its own state, no Textual import, no session-file
reads.

```python
class NodeSelection:
    """Pure, headless node-selection model for the Browse UI (t983_2).

    Tracks a `primary` cursor node plus an explicitly space-marked `marked`
    set, with NO Textual / I/O dependency — mirrors the wizard step model so it
    is exhaustively unit-testable without a running App. It is purely additive;
    the legacy `_current_focused_node_id` path is untouched until t983_3 wires
    this model in.

    Semantics (the primary-vs-marked decision this task fixes):
      * `primary` is the cursor / focused node. SINGLE-node operations act on
        `primary`.
      * `marked` is the space-marked set. MULTI-node operations act on `marked`.
        Marking is what promotes a selection from single to multi; the cursor
        moves independently of marking.
      * `cardinality` is the EFFECTIVE selection size the Operations dialog
        greys ops by: `len(marked)` when anything is marked, else `1` when a
        `primary` cursor exists, else `0`.
      * `effective()` is the concrete target set an operation runs on: the
        `marked` set if non-empty, else `{primary}`, else empty — the runnable
        form of the cardinality rule.
    """

    def __init__(self, primary=None, marked=None):
        self.primary = primary
        self.marked = set(marked) if marked else set()

    def set_primary(self, node_id):
        self.primary = node_id

    def mark(self, node_id):
        self.marked.add(node_id)

    def unmark(self, node_id):
        self.marked.discard(node_id)        # no-op if absent

    def toggle(self, node_id):
        if node_id in self.marked:
            self.marked.discard(node_id)
        else:
            self.marked.add(node_id)

    def clear(self):
        """Clear the marked set only — the cursor (`primary`) persists."""
        self.marked.clear()

    def remove(self, node_id):
        """Drop a node from the selection entirely (e.g. when it is deleted
        from the graph): unmark it AND clear it as `primary` if it was the
        cursor. Single-call cleanup so consumers (t983_3) don't have to
        remember a two-step purge. No-op if the node is in neither."""
        self.marked.discard(node_id)
        if self.primary == node_id:
            self.primary = None

    @property
    def cardinality(self):
        if self.marked:
            return len(self.marked)
        return 1 if self.primary is not None else 0

    def effective(self):
        """Node ids an operation targets: marked set if any, else the primary
        as a singleton, else empty."""
        if self.marked:
            return set(self.marked)
        return {self.primary} if self.primary is not None else set()
```

Decisions:
- **`effective()` included** beyond the task's bare method list — it is the
  runnable expression of "single-node ops act on primary; multi-node ops act on
  marked", the exact decision the task asks to make concrete, and it gives the
  t983_4 consumer a rich answer (the target set) rather than only a count. Still
  pure; no UI dependency.
- **`clear()` clears marks only**, leaving the cursor in place (clearing a
  selection shouldn't relocate the cursor). Documented + tested.
- **`mark`/`unmark` are idempotent** (`set.add` / `set.discard`) — re-marking or
  unmarking-absent is a no-op, never an error.
- **`remove(node_id)` does both-sided cleanup in one call** — unmarks AND clears
  primary-if-cursor — so node deletion (t983_3) is a single call rather than a
  two-step purge the consumer must remember. It generalizes the existing
  legacy-path purge at `brainstorm_app.py:4333-4334`
  (`if _current_focused_node_id in deleted: ... = None`).
- **Cursor and marks are independent** — `toggle` does not move `primary`,
  matching the IA (arrows move the cursor; `space` marks the node under it).

## Implementation steps

1. Add the `NodeSelection` class above to
   `.aitask-scripts/brainstorm/brainstorm_app.py` after the wizard helpers
   (~`:1869`). No other edits to that file. Do NOT wire it into the UI (t983_3).
2. New `tests/test_brainstorm_node_selection.py` — fully headless, `unittest`,
   mirroring the `test_brainstorm_wizard_steps.py` harness (sys.path insert for
   `.aitask-scripts` + `lib`; `from brainstorm.brainstorm_app import
   NodeSelection`). Exhaustive coverage:
   - **`cardinality` transitions:** empty (0); primary-only (1); single-marked
     (1); multi-marked (N); marked overrides primary (primary set + 2 marked →
     2); primary-in-marked stays consistent.
   - **mutators:** `set_primary`, `mark`/`unmark` (incl. unmark-absent no-op),
     `toggle` (mark↔unmark round-trip), `mark` idempotent, `clear` empties
     `marked` but preserves `primary`.
   - **`remove(node_id)`:** removing the primary node → `primary` becomes
     `None` (marked untouched); removing a marked node → dropped from `marked`,
     `primary` untouched; removing a node that is both primary AND marked →
     both cleared; removing a node in neither → no-op (selection unchanged).
   - **`effective()`:** empty → `set()`; primary-only → `{primary}`;
     marked-present → exact marked set (primary excluded when not marked).
   - Constructor: defaults (`primary=None`, empty `marked`); seeded `marked`
     copied (mutating the model does not mutate the caller's set).

## Verification

- `python -m pytest tests/test_brainstorm_node_selection.py -v` (or
  `bash tests/run_all_python_tests.sh`) — new test green.
- Suite `tests/test_brainstorm*.py` green (additive — nothing else changes).

## Risk

### Code-health risk: low
- Purely additive: one new module-level class + one new test file; zero existing
  code paths touched, zero blast radius (nothing imports it until t983_3). Fits
  the established pure-model pattern (wizard steps). · severity: low · →
  mitigation: n/a
- None other identified.

### Goal-achievement risk: low
- Goal is well-specified and the approach is a proven mirror of an existing,
  tested model. The only judgment call — the primary-vs-marked / `cardinality`
  semantics — is decided, documented inline, and exhaustively unit-tested
  (incl. the marked-overrides-primary case the Operations dialog depends on).
  · severity: low · → mitigation: n/a
- None other identified.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_2`.
