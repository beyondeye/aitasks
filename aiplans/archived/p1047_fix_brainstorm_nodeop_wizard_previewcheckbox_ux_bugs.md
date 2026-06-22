---
Task: t1047_fix_brainstorm_nodeop_wizard_previewcheckbox_ux_bugs.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# Plan: Fix brainstorm wizard UX bugs by consolidating the t983_11 relocation fallout (t1047)

## Context

Three UX bugs were reported in the `ait brainstorm` node-operation wizard
(`ActionsWizardScreen`, a `ModalScreen` in `.aitask-scripts/brainstorm/brainstorm_app.py`):
explore dimension checkboxes don't move focus with ↑/↓ (only Tab); the proposal
step's contextual shortcuts (line numbers, preview width) aren't shown; and
clicking the proposal minimap doesn't jump to the section.

Investigation showed these are **not three independent bugs** — they are fallout
from the t983_11 refactor that re-hosted the former "Actions tab" out of the
App's `TabbedContent` into the `ActionsWizardScreen` modal. Two helpers were
copied byte-for-byte instead of shared, and one handler became dead code:

1. **`_navigate_rows` + `_focus_within` are exact duplicates** — wizard
   (`~3569` / `~3655`) and App (`~6675` / `~6731`). The copied `_navigate_rows`
   hard-codes `self.query_one(TabbedContent)` for its "up-past-top → focus the
   tab bar" boundary. The App screen has a `TabbedContent`; the **modal does
   not**, so the lookup raises `NoMatches` (verified with a minimal Textual
   pilot; an exception in `on_key` propagates to app teardown). Result: **all**
   wizard arrow-nav routed through `_navigate_rows` is broken — not just the
   explore dimension checkboxes, which additionally have no `on_key` branch.
   p983_11's own notes flag this as a deliberate copy.

2. **The App's `on_section_minimap_section_selected` (`~8624`) is dead code.**
   `ProposalPreviewPane` is instantiated **only** in the wizard
   (`_mount_config_with_preview`, `~4777`); its `SectionSelected` message bubbles
   within the modal and never reaches the App. The handler's docstring still
   (wrongly) claims it "bubbles up to the App."

3. Missing affordances: no `section_select` arrow branch and no contextual
   shortcut hint on the preview config steps.

Ruled out as a phantom: the wizard's other `self.query(...)` calls are correctly
scoped (`Screen.query` searches the modal's own DOM). The **only** invalid DOM
assumption is that single `TabbedContent` lookup — so the systematic problem is
bounded.

**Approach chosen (targeted consolidation):** fix the bugs by removing the
duplication that caused them, rather than adding three per-symptom branches.
Scope coordinated with **t1048** (full file modularization, depends on t1047):
t1048 will later relocate the new shared mixin into a module.

## Step 0 — Make the scope change explicit (no silent AC drift)

Before implementing, update t1047's description/acceptance criteria to reflect
the consolidation scope (the task was filed as "3 bug fixes"; it is now
"fix the bugs by consolidating the relocation duplication"). Edit the task body
and commit via `./ait git` (task files use `ait git`):
`./ait git commit -m "ait: Re-scope t1047 to relocation-fallout consolidation"`.

## Changes (all in `.aitask-scripts/brainstorm/brainstorm_app.py` unless noted)

### 1. Shared, context-agnostic row-navigation mixin (fixes Bug 1 structurally)

New module `.aitask-scripts/brainstorm/nav_mixin.py` defining `RowNavMixin` with
the single shared `_navigate_rows` and `_focus_within` (moved verbatim from the
existing copies), except the tab-bar boundary becomes an **overridable hook**:

```python
class RowNavMixin:
    def _nav_tab_bar(self):
        """Tabs widget to hand focus to at the top boundary, or None."""
        return None

    def _navigate_rows(self, direction, container_id, row_types) -> bool:
        ...
        focused = self.focused
        tabs_widget = self._nav_tab_bar()
        if tabs_widget is not None and focused is tabs_widget:
            ...
        ...
        if new_idx < 0:
            if tabs_widget is not None:
                tabs_widget.focus()
            return True   # no tab bar → stop at top (no wrap)
        ...

    def _focus_within(self, container) -> bool:
        ...
```

The module is pure Textual (uses `self.focused` / `self.query_one`; no
brainstorm imports), so it is independently unit-testable and pre-stages t1048.

- `BrainstormApp` mixes it in and **overrides** the hook to preserve current
  Browse/Session behavior (up-past-top focuses the tab bar):
  ```python
  def _nav_tab_bar(self):
      try:
          return self.query_one(TabbedContent).query_one(Tabs)
      except Exception:
          return None
  ```
- `ActionsWizardScreen` mixes it in and uses the default (`None`) → boundary
  stops at top, no crash.
- **Delete** both old `_navigate_rows` and `_focus_within` copies (App `~6675`/
  `~6731`, wizard `~3569`/`~3655`). Net ~70 lines of duplication removed.

MRO note: `class BrainstormApp(TuiSwitcherMixin, ShortcutsMixin, RowNavMixin, App)`
and `class ActionsWizardScreen(RowNavMixin, ModalScreen)` — mixin before the
Textual base so the mixin methods resolve first.

### 2. `section_select` arrow branch (Bug 1, second part)

In `ActionsWizardScreen.on_key`, after the compare-config branch (`~3481`), add
a branch for the `section_select` step mirroring it, calling
`self._navigate_rows(±1, "actions_content", (Checkbox,))` when a `chk_section`
checkbox is focused (the section checkboxes are direct children of
`#actions_content`, mounted at `~4056`). Tab nav unchanged. Optional polish: a
`[dim]↑↓ Navigate  Space Toggle[/]` hint `Label` in `_actions_show_section_select`.

### 3. Relocate the dead minimap handler onto the wizard (fixes Bug 3)

- Add `on_section_minimap_section_selected` to `ActionsWizardScreen`, mirroring
  the (now-removed) App body but querying within the modal:
  ```python
  def on_section_minimap_section_selected(self, event) -> None:
      ctrl = getattr(event, "control", None)
      if ctrl is None or not ctrl.has_class("preview_proposal_minimap"):
          return
      panes = self.query(ProposalPreviewPane)
      if not panes:
          return
      panes.first().scroll_to_section(event.section_name)
      event.stop()
  ```
- **Delete** the dead App copy at `~8624` (it can never fire — the pane is
  modal-only). Leave `NodeDetailModal.on_section_minimap_section_selected`
  (`~1251`) untouched: it is a genuinely different, id-based handler for that
  modal's own proposal tab. `ProposalPreviewPane.scroll_to_section` (`~1133`)
  already works.

### 4. Contextual shortcut hints on the preview steps (Bug 2)

In `_actions_show_config` (`~4079`), extend the existing compare/synthesize hint
block to cover the preview ops:
```python
elif op in ("explore", "module_decompose"):
    container.mount(Label(
        "[dim]  Tab Focus panes  ↑↓ Navigate  "
        "alt+n Line numbers  alt+w Preview width[/]"))
```
Keeps the file's established per-step hint-label idiom (the `alt+n`/`alt+w`
bindings are `show=False`, so the Footer won't surface them).

## Tests

New `tests/test_brainstorm_wizard_nav_consolidation.py` (host-App-pushes-modal
pilot harness from `tests/test_brainstorm_node_detail_minimap.py`):

- **Mixin / Bug 1 regression:** in the explore `section_select` step, focus the
  first `chk_section` checkbox; `down`/`up` move focus between checkboxes;
  pressing `up` at the top boundary does **not** crash and focus stays put
  (the `NoMatches` regression guard).
- **App boundary preserved:** a focused-test asserting `BrainstormApp`'s
  `_nav_tab_bar()` still resolves the Tabs widget and up-past-top focuses it
  (no Browse/Session regression).
- **Bug 2:** explore config step mounts a hint `Label` containing
  "Line numbers" / "Preview width".
- **Bug 3:** the wizard handles the preview minimap `SectionSelected` (spy that
  `ProposalPreviewPane.scroll_to_section` is invoked with the section name).
- Light unit test of `RowNavMixin` against a minimal two-class harness (one with
  a tab bar, one without) to lock the overridable-boundary contract.

Async scroll-into-view and visual hint legibility remain manual-verification
(consistent with `test_brainstorm_node_detail_minimap.py`); Step 8c offers a
standalone manual-verification task.

Run: `python3 tests/test_brainstorm_wizard_nav_consolidation.py` plus the
existing nav/wizard/preview suites — `test_brainstorm_wizard_steps.py`,
`test_brainstorm_wizard_sections.py`, `test_brainstorm_browse_view.py`,
`test_brainstorm_proposal_preview.py`, `test_brainstorm_binding_scope.py`.

## Conventions

Follow `aidocs/framework/tui_conventions.md`. No CSS or shortcut-scope manifest
changes (no new bindings; widgets reused). New module + handler relocation only;
no behavior change for the App beyond the (preserved) tab-bar boundary.

## Step 9 (Post-Implementation)

Profile 'fast', current branch — no worktree/merge. After review+commit,
archival via `./.aitask-scripts/aitask_archive.sh 1047`. t1048 (modularize)
depends on t1047 and will later move `RowNavMixin` (and other extractions) into
the modularized layout.

## Risk

### Code-health risk: medium
- The shared `RowNavMixin` is now on the hot path for App Browse/Session nav
  too (not just the wizard). A mistake in the overridable-boundary contract
  could regress tab-bar focus handoff in Browse. Mitigated by the App-boundary
  regression test + running the existing Browse/Session nav suites.
  · severity: medium · → mitigation: covered by tests (no separate task)
- Deleting the dead App minimap handler and the duplicate nav helpers is a net
  simplification; blast radius is one file plus one small new module and the
  test. · severity: low · → mitigation: N/A

### Goal-achievement risk: low
- Final visual confirmation (async scroll-into-view on minimap click, hint
  legibility) is inherently manual; pilot tests cover focus movement and handler
  routing but not pixels. · severity: low · → mitigation: standard Step 8c
  manual-verification offer

## Final Implementation Notes

- **Actual work done:** Extracted `RowNavMixin` (`brainstorm/nav_mixin.py`) with
  the single `_navigate_rows` / `_focus_within` and an overridable
  `_nav_tab_bar()` boundary hook; mixed it into both `BrainstormApp` (override
  returns its `Tabs`) and `ActionsWizardScreen` (inherits `None` → stop at top),
  deleting both byte-for-byte duplicates. Added the `section_select` ↑/↓ `on_key`
  branch. Moved the proposal-minimap handler onto the wizard and deleted the dead
  App copy. New test module `tests/test_brainstorm_wizard_nav_consolidation.py`.
- **Deviations from plan (post-review):** The contextual-shortcut fix changed
  during Step 8. Instead of a dim inline hint label (user reported "still not
  shown") and keeping the `alt+w`/`alt+n` chords, the preview toggles became
  **plain single keys** `w` (width) / `l` (line numbers) with `show=True`,
  surfaced in the **Footer** and context-scoped via a new
  `ActionsWizardScreen.check_action` to (a) the explore/module_decompose preview
  config step and (b) when the proposal/minimap is focused; `refresh_bindings()`
  on descendant focus keeps the footer in sync. This reverses the t1018_1
  "usable while typing in the Mandate TextArea" property by design
  (user-confirmed): with focus in the Mandate box, `w`/`l` type as text — you Tab
  to the proposal to toggle. `tests/test_brainstorm_proposal_preview.py` updated
  accordingly (keys + focus-scope, incl. the rationale test).
- **Issues encountered:** A headless cross-pump race in the test harness — the
  wizard's `call_after_refresh(_fill)` can run `pane.populate()` before the
  dynamically-mounted `ProposalPreviewPane` finishes composing, so `populate()`
  hits a transient `NoMatches`. The new test neutralizes it with a tolerant
  `populate` patch; production wins the race.
- **Key decisions:** Tab-bar boundary made an overridable hook rather than a hard
  `query_one(TabbedContent)` (the actual root cause); minimap handler moved (not
  re-copied) to where the pane lives; preview keys gated by focus, not globally
  active, to avoid corrupting Mandate text.
- **Upstream defects identified:** `.aitask-scripts/brainstorm/brainstorm_app.py:_mount_config_with_preview — call_after_refresh(_fill) can run pane.populate() before the dynamically-mounted ProposalPreviewPane finishes composing, raising a transient NoMatches (benign in production, fatal under headless run_test). Worth a defensive guard or awaited mount.`
