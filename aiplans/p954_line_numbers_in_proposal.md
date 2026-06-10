---
Task: t954_line_numbers_in_proposal.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t954 — Reference-able line numbers in the brainstorm Actions-tab proposal preview

## Context

In the `ait brainstorm` TUI's **Actions** tab, the **explore** and **module
decompose** wizard config steps show the selected node's *base proposal* in a
side-by-side preview (`ProposalPreviewPane`, added in t945/t946) so the user can
read it while writing the exploration mandate / decomposition request. The user
wants to be able to *refer to specific lines* of that proposal ("adapt the part
around line 30") — which requires **stable, reference-able line numbers**.

The proposal is currently rendered as **Markdown** (`SectionAwareMarkdown`),
which reflows and has **no 1:1 mapping to source lines**, so it cannot carry
meaningful line numbers. The task note explicitly anticipates the hard part:
on narrow terminals one logical proposal line wraps across multiple terminal
rows, so naive "count the visible rows" numbering would drift.

**Chosen approach (user-selected):** keep Markdown + section minimap as the
default view, and add a **toggle key** that swaps the content pane to a
**numbered source-line view**. Line numbers = source proposal lines. Wrapping is
handled by the proven **codebrowser pattern** (`code_viewer.py`): a Rich `Table`
with a fixed-width, right-justified line-number column (`no_wrap=True`) beside a
content column that wraps (`no_wrap=False`). Each source line is exactly one
table row, so the number stays anchored even when its content wraps to several
terminal rows. Additive, lowest blast radius — the t946 minimap and markdown
rendering are untouched in their default mode.

## Constraints (must respect)

- **No `TextArea`/`CycleField`/`RadioSet` inside the pane.** `_actions_collect_config`
  resolves the op's inputs with recursive single-match `query_one(TextArea)` /
  `query_one(CycleField)` over `#actions_content`; adding either to the preview
  pane breaks those queries (see `ProposalPreviewPane` docstring,
  `brainstorm_app.py:972-977`). The numbered view is a **`Static` rendering a
  Rich `Table`**, inside a `VerticalScroll` — none of the forbidden widgets.
- Toggle must use a **modifier key combo**, not a bare letter — focus may sit in
  the left-pane mandate `TextArea`, where a bare key would be typed as text.
  Mirror the existing `ctrl+shift+b` (preview width) binding.

## Files to modify

1. `.aitask-scripts/brainstorm/brainstorm_app.py` — the pane, a new numbered
   widget, the app-level toggle action + binding + `check_action` guard, and the
   focus ring.
2. `tests/test_brainstorm_proposal_preview.py` — extend with numbered-view tests.
3. Docs: `aidocs/framework/tui_conventions.md` is reference-only; the
   user-facing keybinding belongs in the brainstorm docs (see step 6).

## Implementation

### 1. New numbered-source widget (`brainstorm_app.py`, near `ProposalPreviewPane`)

Add a small scrollable widget that renders source lines with a gutter, adapting
the codebrowser pattern (`code_viewer.py:283-367`):

```python
class _NumberedProposal(VerticalScroll):
    """Scrollable source-line view: fixed line-number gutter + wrapping content.

    One source line == one Rich Table row (codebrowser pattern), so the line
    number stays anchored to its line even when the content wraps on a narrow
    terminal. Rebuilds on resize so column widths track the pane width.
    """
    DEFAULT_CSS = """
    _NumberedProposal { height: 1fr; width: 1fr; padding: 0 1; }
    """
    LINE_NUM_WIDTH = 5

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._text = ""

    def compose(self) -> ComposeResult:
        yield Static(id="preview_numbered_inner")

    def set_text(self, text: str) -> None:
        self._text = text or ""
        self._rebuild()

    def on_resize(self, event) -> None:
        if self._text:
            self._rebuild()

    def _rebuild(self) -> None:
        from rich.table import Table
        available = self.size.width if self.size.width > 0 else 120
        content_w = max(20, available - self.LINE_NUM_WIDTH - 2)
        table = Table(show_header=False, show_edge=False, box=None, pad_edge=False)
        table.add_column(style="dim", justify="right",
                         width=self.LINE_NUM_WIDTH, no_wrap=True)
        table.add_column(no_wrap=False, width=content_w)   # wraps; number anchored
        for i, line in enumerate(self._text.split("\n"), start=1):
            table.add_row(Text(str(i), style="dim"), Text(line))
        self.query_one("#preview_numbered_inner", Static).update(table)
```

Notes: `Static` and `Text` are already imported (`brainstorm_app.py:36,46`);
`Table` is imported lazily inside `_rebuild` (codebrowser imports it top-level —
either is fine; lazy keeps the import diff minimal). Render the proposal **raw**
(plain `Text`, no markdown parsing) so line N == proposal source line N.

### 2. Dual-mode in `ProposalPreviewPane`

- `__init__`: add `self._numbered = False`.
- `compose` (currently `brainstorm_app.py:1003-1006`): also yield the numbered
  view, hidden by default:
  ```python
  yield _NumberedProposal(id="preview_proposal_numbered")
  ```
  Add CSS so it fills the pane like `#preview_proposal_content` and starts hidden
  (`display: none`), in the pane's `DEFAULT_CSS` block (`:980-996`).
- `populate` (`:1015-1032`): after updating markdown/minimap, also feed the
  numbered view: `self.query_one("#preview_proposal_numbered", _NumberedProposal).set_text(text)`.
  Reset to markdown mode on every populate (each config step builds a fresh pane,
  so `_numbered` is already False, but set it explicitly + ensure display state).
- New method `toggle_numbered(self) -> bool`:
  ```python
  def toggle_numbered(self) -> bool:
      self._numbered = not self._numbered
      md = self._content()
      num = self.query_one("#preview_proposal_numbered", _NumberedProposal)
      minimap = self._minimap()
      if self._numbered:
          md.display = False
          minimap.display = False
          num.display = True
      else:
          num.display = False
          md.display = True
          # minimap only when the proposal actually has sections
          minimap.display = self._parsed is not None
      return self._numbered
  ```

### 3. App-level toggle action, binding, guard

- **Binding** (after `brainstorm_app.py:3463`):
  ```python
  Binding("ctrl+shift+l", "toggle_preview_numbered", "Line numbers"),
  ```
- **`check_action` guard** — clone the `cycle_preview_ratio` block
  (`:3595-3604`) for `toggle_preview_numbered` (active tab == `tab_actions` and a
  `ProposalPreviewPane` is mounted).
- **Action method** (next to `action_cycle_preview_ratio`, `:7103`):
  ```python
  def action_toggle_preview_numbered(self) -> None:
      from textual.actions import SkipAction
      panes = self.query(ProposalPreviewPane)
      if not panes:
          raise SkipAction()
      panes.first().toggle_numbered()
  ```

### 4. Focus ring (`_preview_focus_ring`, `:7136-7175`)

The Tab ring appends the minimap then `#preview_proposal_content`. Make it follow
the visible content widget so Tab reaches whatever is shown:
- When `pane._numbered` is True: skip the minimap, and append the
  `#preview_proposal_numbered` scroller instead of the markdown.
- Else: unchanged (minimap when `display`, then `#preview_proposal_content`).

Implement by gating the existing minimap/content appends on `display`, and
appending whichever of markdown / numbered is currently displayed. Keep returning
`[]` when no pane is mounted.

## Tests (`tests/test_brainstorm_proposal_preview.py`)

Extend the existing pilot suite (mirror its `_HostApp` / `run_test` style):

- `test_toggle_numbered_swaps_visible_widget`: populate, assert markdown visible &
  numbered hidden; call `pane.toggle_numbered()`; assert numbered visible,
  markdown + minimap hidden; toggle back restores markdown (and minimap when
  sections present).
- `test_numbered_view_lists_one_row_per_source_line`: feed a known multi-line
  proposal; after toggle, assert the numbered widget's `_text` split length and
  that the rendered gutter starts at 1 (assert on `_NumberedProposal._text` /
  `set_text` line count — robust without scraping the Rich table).
- `test_numbered_line_numbers_survive_narrow_width`: run at `size=(40, x)`, feed a
  proposal with a line longer than the content column; assert row count (logical
  lines) is unchanged regardless of width — proves numbers track source lines, not
  wrapped rows.
- `test_focus_ring_targets_numbered_when_toggled`: after `toggle_numbered()`,
  `_preview_focus_ring()` ends with `preview_proposal_numbered` and excludes the
  minimap.

Run: `python tests/test_brainstorm_proposal_preview.py` (and a broad
`python tests/test_brainstorm_wizard_steps.py` to confirm no config-collector
regression from the new child widget).

## Verification

1. `python tests/test_brainstorm_proposal_preview.py` — all pass.
2. Launch `./ait brainstorm` on a session with at least one node, open the
   **Actions** tab, start **explore** (and **module decompose**); the proposal
   shows as markdown. Press `Ctrl+Shift+L` → numbered source view; numbers are
   right-aligned in a gutter and continue past wrapped lines. Press again →
   markdown returns; the section minimap reappears when the proposal has sections.
3. Shrink the terminal narrow enough to force wrapping while in numbered mode —
   confirm a wrapped long line keeps a single line number and the next line's
   number is sequential (no drift). `Ctrl+Shift+B` (width cycle) still works.
4. Confirm explore/decompose still *apply* correctly (the left-pane mandate
   `TextArea`/`CycleField` collectors are unaffected).

## Post-implementation

- Cross-agent ports: this is a Python TUI change (not a skill/`.md.j2`), so no
  Codex/OpenCode skill port is needed.
- Brainstorm user docs: if the Actions-tab keybindings are documented in
  `website/content/docs/` or a brainstorm aidoc, add the `Ctrl+Shift+L` line.
- Follow Step 9 (Post-Implementation) of the task-workflow for archival; working
  on current branch (no worktree to clean up).

## Risk

### Code-health risk: medium
- Touches the shared `_preview_focus_ring` (used by both explore + decompose wizards, with existing tests); mis-gating the display checks could break Tab traversal · severity: medium · → mitigation: covered in-plan by `test_focus_ring_targets_numbered_when_toggled` + existing ring tests
- New child widget in the pane risks the documented `query_one(TextArea)/query_one(CycleField)` collector ambiguity · severity: low · → mitigation: numbered view is `Static`/`VerticalScroll` only (no forbidden widget); guarded by a broad wizard-steps test run

### Goal-achievement risk: low
- None identified — the codebrowser one-row-per-source-line pattern is proven to keep numbers anchored across reflow, fully covers the requirement, and the toggle/default choice was user-confirmed.

## Post-Review Changes

### Change Request 1 (2026-06-10) — keybinding customizability
- **Requested by user:** Confirm the new `Ctrl+Shift+L` binding is in the customizable keybindings map.
- **Outcome:** No code change needed. `BrainstormApp` subclasses `ShortcutsMixin` (scope `brainstorm`), whose `__init__` calls `register_app_bindings(scope, self.BINDINGS)` over the whole `BINDINGS` list — so the binding, placed directly in `BINDINGS`, is auto-registered as `("brainstorm","toggle_preview_numbered") → ("ctrl+shift+l","Line numbers")`. It appears in the in-TUI shortcut editor (`?`) and is rebindable via `userconfig.yaml` `shortcuts.brainstorm.toggle_preview_numbered`, identical to the sibling `cycle_preview_ratio`.

### Change Request 2 (2026-06-10) — syntax highlighting
- **Requested by user:** The numbered view should syntax-highlight the markdown (parity with codebrowser, which shows highlighted markdown + line numbers).
- **Changes made:** `_NumberedProposal.set_text` now markdown-highlights the source via Rich `Syntax(text, "markdown", theme="monokai").highlight(text)` (the codebrowser approach), splits into per-line `Text` (the highlighter drops the trailing-newline empty line → conventional line count), and caches the lines so `_rebuild` (per-resize) only re-lays out the table width. Added `test_numbered_view_is_syntax_highlighted`; adjusted the test fixture to omit a trailing newline so raw and highlighted line counts align.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`, `tests/test_brainstorm_proposal_preview.py`.

## Final Implementation Notes

- **Actual work done:** Added a `Ctrl+Shift+L` toggle in the brainstorm Actions-tab proposal preview (explore / module-decompose config steps) that swaps the `SectionAwareMarkdown` for a new `_NumberedProposal` widget — a scrollable, **markdown-syntax-highlighted** source view with a right-justified line-number gutter. Built on the codebrowser Rich-`Table` pattern: one source line per row, number column `no_wrap`, content column wraps, so line numbers survive reflow on narrow terminals. Markdown remains the default; the section minimap is hidden in numbered mode and restored (only when the proposal has sections) on toggle-back. `populate()` resets to markdown mode and feeds the numbered view. Focus ring (`_preview_focus_ring`) follows the visible content view. Binding gated to the Actions tab via `check_action`, auto-registered in the customizable shortcuts map.
- **Deviations from plan:** Added markdown syntax highlighting (Change Request 2) beyond the original plain-text plan. Cached the highlighted lines in `set_text` (not in the plan's sketch) so per-resize `_rebuild` does not re-run the highlighter.
- **Issues encountered:** Textual's `Static` exposes no `.renderable` in this version — tests assert against a cached `_NumberedProposal._table` instead. `Syntax.highlight().split("\n")` drops the trailing-newline empty line (conventional line count); test fixture omits the trailing newline to keep raw/highlighted counts aligned.
- **Key decisions:** Numbered view is a `Static`-rendered Rich `Table` inside a `VerticalScroll` (never a `TextArea`/`CycleField`/`RadioSet`) to preserve the `_actions_collect_config` single-match collector contract. Theme `monokai` for codebrowser parity.
- **Upstream defects identified:** None.
