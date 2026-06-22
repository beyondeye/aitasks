---
Task: t1050_harden_brainstorm_mount_config_with_preview_populate_timing.md
Base branch: main
plan_verified: []
---

# Plan: Harden brainstorm preview populate timing (t1050)

## Context

Surfaced during t1047 testing. The brainstorm Actions wizard lays out its
config-with-preview steps via
`ActionsWizardScreen._mount_config_with_preview`
(`.aitask-scripts/brainstorm/brainstorm_app.py:1918`). It mounts a
`Horizontal(left, pane, …)` split and then schedules a `_fill` callback via
`self.call_after_refresh(_fill)`, where `_fill` calls
`pane.populate(proposal_text)`.

`ProposalPreviewPane.populate` (`.aitask-scripts/brainstorm/widgets.py:201`)
immediately queries its own child content widget via
`self._content()` → `query_one("#preview_proposal_content", …)`. But the
dynamically-mounted pane composes its children (`_PreviewMinimap`,
`SectionAwareMarkdown#preview_proposal_content`, `_NumberedProposal`) on its own
message pump. The screen's idle can fire `_fill` **before** the pane finishes
composing, so `query_one` raises a transient `NoMatches`.

- **Impact:** Benign in the real app (extra layout refreshes win the race) but
  fatal under headless `run_test`. t1047's pilot tests had to neutralize it
  with a tolerant `populate` monkeypatch in
  `tests/test_brainstorm_wizard_nav_consolidation.py::WizardNavTests.setUp`.

**Goal:** make the populate timing structurally race-free — populate cannot run
before the pane's content widget exists — then remove the test's monkeypatch.

## Approach (recommended)

Move populate into the pane's **own mount lifecycle**. Textual guarantees a
widget's `on_mount` fires only after the widget and its composed children are
mounted, so querying `#preview_proposal_content` there is race-free by
construction. The caller hands the proposal text to the pane at construction
instead of racing a `call_after_refresh` against the pane's `compose`.

This is the cleanest of the three options listed in the task (vs. `await`-ing
the mount, or making `_content()` defer): it puts the timing invariant inside
the widget that owns the content, so no caller has to remember the sequence.
The only caller of `ProposalPreviewPane.populate` is `_mount_config_with_preview`
(confirmed: the other `.populate(` hits in the tree are on *minimap* objects in
`widgets.py:213` and `modals.py:548`, not the pane), so the change is fully
contained.

### Change 1 — `.aitask-scripts/brainstorm/widgets.py` (`ProposalPreviewPane`)

Accept an optional proposal text at construction, store it as pending, and
populate from `on_mount`:

- In `__init__` (currently `def __init__(self, **kwargs)`), add a
  keyword param and store it:
  ```python
  def __init__(self, proposal_text: str | None = None, **kwargs) -> None:
      super().__init__(**kwargs)
      self._parsed = None
      self._text = ""
      self._numbered = False
      self._pending_text = proposal_text
  ```
  (Keyword form `proposal_text=...` avoids any clash with Textual's
  `Horizontal(*children)` positional args.)

- Add an `on_mount` right after `compose`/`_content`:
  ```python
  def on_mount(self) -> None:
      # Populate from the pane's own mount lifecycle: Textual guarantees this
      # fires after compose() has mounted #preview_proposal_content, so
      # populate()'s query_one can never hit a transient NoMatches. A None
      # pending text means a caller will populate() later (e.g. the direct
      # unit tests in test_brainstorm_proposal_preview.py).
      if self._pending_text is not None:
          self.populate(self._pending_text)
          self._pending_text = None
  ```

`populate` itself is unchanged and still callable directly (the proposal-preview
unit tests construct the pane with no text and call `populate` by hand — the
`None` guard leaves them unaffected).

### Change 2 — `.aitask-scripts/brainstorm/brainstorm_app.py` (`_mount_config_with_preview`, ~1929-1941)

Pass the text at construction and drop the populate from `_fill`:

```python
left = VerticalScroll(classes="config_preview_left")
pane = ProposalPreviewPane(proposal_text=proposal_text, classes="config_preview_pane")
split = Horizontal(left, pane, classes="config_preview_split")
container.mount(split)
self._preview_ratio = 0

def _fill() -> None:
    left_builder(left)

# Defer the left-side nested mounts until the split has settled. The preview
# pane populates itself from ProposalPreviewPane.on_mount (its content widget
# is guaranteed composed there), so it no longer races this callback.
self.call_after_refresh(_fill)
```

`left_builder` stays in `call_after_refresh` (it mounts the op's widgets into
the left scroll — not the racy path); only the pane populate moves.

### Change 3 — `tests/test_brainstorm_wizard_nav_consolidation.py`

Remove the now-obsolete `WizardNavTests.setUp` (lines ~216-236): the
`ProposalPreviewPane.populate` monkeypatch and its `addCleanup`. `setUp`
contains nothing else, so delete the whole method (TestCase has a default).

## Verification

1. The previously-patched tests now pass without the tolerant patch:
   ```bash
   bash -c 'cd /home/ddt/Work/aitasks && python -m pytest tests/test_brainstorm_wizard_nav_consolidation.py -q'
   ```
   (or `python tests/test_brainstorm_wizard_nav_consolidation.py` if it is a
   unittest main). Confirms the real `populate` runs under `run_test` with no
   transient `NoMatches`.
2. The direct preview unit tests still pass (the `on_mount` no-op path with
   `proposal_text=None`):
   ```bash
   python -m pytest tests/test_brainstorm_proposal_preview.py -q
   ```
3. Sanity-launch the brainstorm Actions wizard explore/synthesize config step
   to confirm the proposal preview still renders on first mount.

## Acceptance criteria (from task)
- `_mount_config_with_preview` no longer races: populate cannot run before the
  pane's content widget exists (no transient `NoMatches`). ✓ via on_mount.
- The `populate` monkeypatch in
  `tests/test_brainstorm_wizard_nav_consolidation.py` is removed and the tests
  still pass. ✓ via Change 3 + verification 1.

## Risk

### Code-health risk: low
- Change is fully contained to `ProposalPreviewPane` and its single caller; the
  populate timing invariant moves *into* the widget (better encapsulation, not
  worse). · severity: low · → mitigation: none needed
- Slight behavior shift: pane now self-populates on mount. Mitigated by the
  `None` guard so the direct-populate unit tests are untouched. · severity: low
  · → mitigation: covered by verification 2

### Goal-achievement risk: low
- `on_mount` firing after `compose` is a documented Textual guarantee, so the
  fix addresses the root cause directly; verification 1 proves it by removing
  the patch and re-running the formerly-failing tests. · severity: low ·
  → mitigation: none needed

## Step 9 (Post-Implementation)
Standard cleanup/archival/merge per task-workflow Step 9.
