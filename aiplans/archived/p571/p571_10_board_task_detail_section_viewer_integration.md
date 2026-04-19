---
Task: t571_10_board_task_detail_section_viewer_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_5_*.md, aitasks/t571/t571_6_*.md, aitasks/t571/t571_7_*.md, aitasks/t571/t571_8_*.md, aitasks/t571/t571_9_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-04-19 10:10
---

# Plan: t571_10 — Board TaskDetailScreen Section Viewer Integration

<!-- section: context [dimensions: motivation, integration] -->

## Context

Integrate the shared `.aitask-scripts/lib/section_viewer.py` module (from t571_5) into the **board** TUI's `TaskDetailScreen`. Two entry points:

1. **Inline minimap in plan view** — when the user toggles to plan view (`v` key), a `SectionMinimap` appears inside `#md_view` above the `Markdown`.
2. **Full-screen plan viewer via `V`** — pushes a `SectionViewerScreen` for dedicated reading. This pairs semantically with `v` (inline toggle).

Board users already rely on `p` for pick and `v` for toggle — we must NOT override lowercase `v`. Board BINDINGS (lines 1898–1922) currently defines every action as both its lower- and upper-case variant (e.g. `v`/`V` both → `action_toggle_view`). We break that convention **only for the `v/V` pair** so that `V` can open the fullscreen viewer — semantically clean and matches the other two TUIs (see "Cross-TUI keybinding alignment" below).

**Depends on t571_5 (already landed).** This is the first host TUI consumer of `section_viewer.py`; t571_8 and t571_9 are still pending, so no precedent exists yet — the keyboard contract defined in t571_5's archived plan is the authoritative spec.

## Cross-TUI Keybinding Alignment

All three plan-viewer host TUIs (board, codebrowser, brainstorm) MUST use the **same key** for fullscreen `SectionViewerScreen`. Chosen key: **`V`** (uppercase / `shift+v`).

As part of this task, we also update the sibling plan files so future pickers of t571_8 / t571_9 land on the aligned keybinding:
- `aiplans/p571/p571_8_codebrowser_section_viewer_integration.md` — change the fullscreen binding from `p` to `V`.
- `aiplans/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md` — add a `V` → fullscreen binding on `NodeDetailModal` (currently absent).

The inline-mount mechanism remains architecturally TUI-specific (board has task↔plan toggle, codebrowser auto-mounts from annotation, brainstorm mounts per tab). Only the shared lib-defined keys (`tab` / `up` / `down` / `enter` / `escape`) plus the new `V` fullscreen key are contract-bound across TUIs.

<!-- /section: context -->

<!-- section: verification_notes [dimensions: verify-path] -->

## Verification Notes (2026-04-19)

Verified against the current codebase at the time of implementation:
- `.aitask-scripts/lib/section_viewer.py` exists (326 LOC) and exports `SectionRow`, `SectionMinimap`, `SectionAwareMarkdown`, `SectionViewerScreen`, `estimate_section_y`, `parse_sections`.
- `.aitask-scripts/brainstorm/brainstorm_sections.py` exports `parse_sections` at line 56.
- `.aitask-scripts/board/aitask_board.py` line numbers still accurate:
  - sys.path insert at **line 12** (originally cited as 13; negligible drift).
  - `TaskDetailScreen` at line 1895; BINDINGS at 1898–1922 (p/P, l/L, u/U, c/C, s/S, r/R, e/E, d/D, n/N, v/V, b/B).
  - `compose()` at line 1952; `VerticalScroll(id="md_view")` at 2082–2083; `btn_view` at 2097–2098.
  - `toggle_view()` at 2180–2207 — already handles YAML frontmatter stripping, so `_read_plan_content()` extraction is a clean refactor.
- **No conflicts:** `shift+v` and `tab` are unbound on `TaskDetailScreen`.
- **No sibling precedent:** t571_8 (codebrowser) and t571_9 (brainstorm) are both pending; board is the first `section_viewer` host.

<!-- /section: verification_notes -->

<!-- section: files_and_lines [dimensions: deliverables] -->

## Files and Line References

- `.aitask-scripts/board/aitask_board.py`:
  - sys.path insert at line 12 already covers `lib/`; rely on `section_viewer.py`'s own sys.path self-insert for brainstorm access — no changes needed here.
  - `TaskDetailScreen` class at line 1895.
  - `BINDINGS` at lines 1898–1922 (**remove** existing `Binding("V", "toggle_view", ...)` at line 1919; **add** `Binding("V", "fullscreen_plan", "Fullscreen plan")` and `Binding("tab", "focus_minimap", "Minimap")`).
  - `compose()` at lines 1952+; `VerticalScroll(id="md_view")` at 2082–2083 containing `Markdown(self.task_data.content)` (no id on the `Markdown`).
  - `toggle_view()` at lines 2180–2207 — refactor to extract `_read_plan_content()` and mount/remove minimap.
  - `btn_view` button at lines 2097–2098 (`(V)iew Plan` / `(V)iew Task`). Button label still references `V` — now the button displays the plan inline, and typing `V` (uppercase) triggers the fullscreen viewer. Update the button label to read `(v)iew plan` (lowercase `v`) to match actual behavior, and the indicator remains unchanged.

- `aiplans/p571/p571_8_codebrowser_section_viewer_integration.md`:
  - Change `Binding("p", "view_plan", "Plan viewer")` to `Binding("V", "view_plan", "Fullscreen plan")` (and also `Binding("shift+v", ...)` if Textual requires both forms — prefer `V` alone since codebrowser already accepts single-case bindings).
  - Update verification step 6 from "Press `p`" to "Press `V`".

- `aiplans/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md`:
  - Add a new section "Fullscreen binding" documenting `Binding("V", "fullscreen_plan", "Fullscreen plan")` on `NodeDetailModal.BINDINGS`, plus an `action_fullscreen_plan()` that dispatches to the currently-active tab's content (proposal or plan) and pushes `SectionViewerScreen`.
  - Add a verification step covering `V` → fullscreen open.

<!-- /section: files_and_lines -->

<!-- section: toggle_view_enhancement [dimensions: integration, widget-design] -->

## 1. `toggle_view()` — mount/remove minimap on plan toggle

Refactor `toggle_view()` to extract the plan-reading logic into `_read_plan_content()`:

```python
def _read_plan_content(self) -> str | None:
    """Return plan content for the current task with YAML frontmatter stripped, or None."""
    if not self._plan_path:
        return None
    content = self._plan_path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()
    return content
```

In the plan-direction branch of `toggle_view()`, after updating the `Markdown` with plan content:

```python
from brainstorm.brainstorm_sections import parse_sections
from section_viewer import SectionMinimap
parsed = parse_sections(plan_content)
md_view = self.query_one("#md_view", VerticalScroll)
if parsed.sections:
    self._plan_parsed = parsed
    self._plan_text = plan_content
    existing = md_view.query("#board_minimap")
    if not existing:
        minimap = SectionMinimap(id="board_minimap")
        # Mount BEFORE the Markdown inside #md_view
        md_view.mount(minimap, before="Markdown")
    md_view.query_one("#board_minimap", SectionMinimap).populate(parsed)
else:
    for w in list(md_view.query("#board_minimap")):
        w.remove()
```

In the task-direction branch (going back to task view), unconditionally remove `#board_minimap`:

```python
md_view = self.query_one("#md_view", VerticalScroll)
for w in list(md_view.query("#board_minimap")):
    w.remove()
```

Initialize `self._plan_parsed = None`, `self._plan_text = ""` in `__init__`.

<!-- /section: toggle_view_enhancement -->

<!-- section: section_select_handler [dimensions: integration, scroll-estimation] -->

## 2. Handle `SectionMinimap.SectionSelected`

```python
def on_section_minimap_section_selected(self, event) -> None:
    if self._plan_parsed is None:
        return
    from section_viewer import estimate_section_y
    md_view = self.query_one("#md_view", VerticalScroll)
    total = self._plan_text.count('\n') + 1
    y = estimate_section_y(self._plan_parsed, event.section_name, total, md_view.virtual_size.height)
    if y is not None:
        md_view.scroll_to(y=y, animate=True)
    event.stop()
```

<!-- /section: section_select_handler -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. Tab focus contract (crucial: scoped guard)

Minimap→content:

```python
def on_section_minimap_toggle_focus(self, event) -> None:
    self.query_one("#md_view Markdown", Markdown).focus()
    event.stop()
```

Content→minimap (screen-level) — add `Binding("tab", "focus_minimap", "Minimap")` to BINDINGS:

```python
def action_focus_minimap(self) -> None:
    from textual.actions import SkipAction
    md = self.query_one("#md_view Markdown", Markdown)
    minimaps = self.query("#board_minimap")
    if self.screen.focused is not md or not minimaps:
        raise SkipAction()
    minimaps.first().focus_first_row()
```

The `SkipAction` guard is load-bearing: `TaskDetailScreen` is a form with many focusable fields the user Tabs between. This binding must only activate when plan markdown has focus AND a minimap is mounted.

<!-- /section: focus_routing -->

<!-- section: fullscreen_binding [dimensions: keybinding, integration] -->

## 4. `V` → full-screen `SectionViewerScreen`

**Rebind `V` in BINDINGS (lines 1898–1922):**
- Replace `Binding("V", "toggle_view", "Toggle View", show=False)` at line 1919 with:
  ```python
  Binding("V", "fullscreen_plan", "Fullscreen plan", show=False),
  ```
- Keep `Binding("v", "toggle_view", "Toggle View", show=False)` at line 1918 unchanged — lowercase `v` still toggles the inline plan view.
- Also add a `tab` binding for focus routing (per §3 above).

```python
def action_fullscreen_plan(self) -> None:
    plan_content = self._read_plan_content()
    if plan_content:
        from section_viewer import SectionViewerScreen
        self.app.push_screen(SectionViewerScreen(
            plan_content,
            title=f"Plan for t{self.task_data.id}"))
    else:
        self.notify("No plan file found", severity="warning")
```

<!-- /section: fullscreen_binding -->

<!-- section: binding_safety [dimensions: keybinding, robustness] -->

## 5. Binding safety regression

After adding the new bindings, manually confirm:
- `p` / `P` still trigger `action_pick` (not overridden by any new binding).
- `v` (lowercase) still triggers `action_toggle_view` (inline toggle).
- `V` (uppercase / `shift+v`) now triggers `action_fullscreen_plan`.
- `tab` inside the form navigates fields as before (the `SkipAction` guard must pass through).
- All other upper-case bindings (`L`, `U`, `C`, `S`, `R`, `E`, `D`, `N`, `B`, `P`) still dispatch to their respective actions — only the `V` entry is repurposed.

<!-- /section: binding_safety -->

<!-- section: sibling_plan_updates [dimensions: cross-task-alignment] -->

## 6. Align sibling plan files (t571_8 and t571_9)

Edit the two pending sibling plan files so future pickers land on the shared `V` fullscreen keybinding:

**`aiplans/p571/p571_8_codebrowser_section_viewer_integration.md`:**
- In the "app_binding" section, replace `Binding("p", "view_plan", "Plan viewer")` with `Binding("V", "view_plan", "Fullscreen plan")`.
- In the Verification section, change "Press `p`" to "Press `V`" (step 6 and any other occurrences).

**`aiplans/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md`:**
- Add a new section `## 5. `V` → full-screen plan viewer` with:
  ```python
  BINDINGS += [Binding("V", "fullscreen_plan", "Fullscreen plan")]

  def action_fullscreen_plan(self) -> None:
      tabbed = self.query_one(TabbedContent)
      if tabbed.active == "tab_proposal":
          content = self._proposal_text
      elif tabbed.active == "tab_plan":
          content = self._plan_text
      else:
          return
      if content:
          from section_viewer import SectionViewerScreen
          self.app.push_screen(SectionViewerScreen(content, title=f"Node {self._node_name}"))
  ```
- Add a verification step covering `V` → fullscreen open on both tabs.

Commit these plan updates alongside the plan update commit for t571_10 (via `./ait git`). They are plan-file changes only, no code change — they simply keep the siblings aligned before they are picked.

<!-- /section: sibling_plan_updates -->

<!-- section: verification [dimensions: testing] -->

## Verification

Fixture content: t571_5's archived plan embeds ~14 sectioned entries — great test fixture. Drive through:

1. `ait board` → select task (e.g. `t571_10` or any task with a sectioned plan) → open `TaskDetailScreen`.
2. Press `v` (lowercase) → plan view shows. Minimap appears above the markdown with all section names + dimension tags.
3. `Tab` → focus moves to plan markdown. `Tab` again → focus returns to the last-highlighted minimap row.
4. `Up`/`Down` on minimap → focus cycles, no scroll.
5. `Enter` on a row → plan scrolls to that section.
6. Press `V` (uppercase / `shift+v`) → `SectionViewerScreen` opens with split layout; Tab/Arrow/Enter contract holds; Escape closes.
7. Press `v` again → back to task view; `#board_minimap` is removed.
8. Select a task with no sectioned plan → `v` shows plan markdown only (no minimap).
9. Regression: `p` still triggers pick; `Tab` still cycles form fields when plan view is NOT active; other upper-case bindings (`L`, `U`, `C`, `S`, `R`, `E`, `D`, `N`, `B`, `P`) still work.

**Since this is a TUI change, hand the final check to t571_7 (manual verification sibling task).** The code-side verification above is sufficient for archival; the end-to-end keyboard-contract check lives in t571_7.

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->

<!-- section: final_implementation_notes [dimensions: retrospective] -->

## Final Implementation Notes

- **Actual work done:** Edited `TaskDetailScreen` in `.aitask-scripts/board/aitask_board.py`:
  - Rebound `V` from `toggle_view` to new `fullscreen_plan` action (BINDINGS lines 1898–1923, one line changed).
  - Added `tab` binding → `focus_minimap` with a `SkipAction` guard so form-field Tab navigation still works.
  - Added instance state `self._plan_parsed = None`, `self._plan_text = ""` in `__init__`.
  - Extracted `_read_plan_content()` helper from the inline plan-reading logic in `toggle_view()`.
  - Added `_mount_or_update_minimap()` and `_remove_minimap()` helpers that wrap `SectionMinimap` lifecycle inside `#md_view`.
  - Added message handlers `on_section_minimap_section_selected()` (scroll using `estimate_section_y`) and `on_section_minimap_toggle_focus()` (focus plan Markdown).
  - Added `action_fullscreen_plan()` (push `SectionViewerScreen`) and `action_focus_minimap()` (Tab from plan Markdown → minimap, with scoped `SkipAction` guard via `self.screen.query_one`, per the `feedback_textual_priority_bindings` memory).

- **Cross-TUI alignment propagated:**
  - `aiplans/p571/p571_8_codebrowser_section_viewer_integration.md` — changed fullscreen binding from `p` to `V`; updated verification steps.
  - `aiplans/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md` — added a new §4 "Fullscreen binding" with `V` → `action_fullscreen_plan` dispatching to the currently-active `TabbedContent` tab (proposal or plan), plus matching verification steps.

- **Deviations from plan:**
  - Factored the plan-direction branch of `toggle_view()` into two private helpers (`_mount_or_update_minimap` + `_remove_minimap`) instead of inlining the code. Keeps `toggle_view()` readable and makes the task-direction branch trivially call `_remove_minimap(md_view)`.
  - Wrapped `section_viewer` / `brainstorm_sections` imports in `try/except` with a `notify` on failure, so a missing/broken lib gracefully degrades to the old task/plan toggle behavior instead of crashing the modal.
  - Button label was NOT changed from `(V)iew Plan` to `(v)iew plan` — the button still dispatches to `toggle_view` (inline toggle), which is triggered by lowercase `v`; the capitalized glyph in the button label is a codebase-wide visual convention matching all other buttons (`(P)ick`, `(L)ock`, `(E)dit`, …). Users who press `V` get the fullscreen viewer instead, which is also a "view plan" action, so the label remains intuitively correct.

- **Issues encountered:**
  - `.aitask-scripts/codebrowser/codebrowser_app.py` showed as modified in working tree but was pre-existing in-progress work from a parallel session (adding a `ContextualFooter` class). Excluded from this task's commit scope.

- **Key decisions:**
  - Chose `V` (uppercase / `shift+v`) as the cross-TUI fullscreen key after discussion with user. Board's existing BINDINGS listed every action as both lower- and upper-case; we broke that convention **only for the `v/V` pair** so `v` → inline toggle and `V` → fullscreen form a clean semantic pair. All other upper-case duplicates (P, L, U, C, S, R, E, D, N, B) are preserved.
  - Scoped the Tab guard to `self.screen.query_one(...)` (per the feedback memory about Textual priority bindings): `App.query_one` walks the whole screen stack, so an unscoped guard can match widgets from underlying screens and consume the key. Using `self.screen.query_one` + `raise SkipAction()` on guard-miss lets the form's default Tab navigation proceed.
  - Import of `SectionViewerScreen` / `SectionMinimap` / `estimate_section_y` / `parse_sections` is done lazily inside each handler to avoid touching module-level imports and keep the diff small.

- **Notes for sibling tasks (t571_8, t571_9):**
  - The `V` key is now the authoritative fullscreen binding. Both sibling plans have been updated to match — do not re-introduce `p` (t571_8) or skip the binding (t571_9).
  - Pattern for `action_focus_minimap` with `SkipAction` guard is the same contract for all three TUIs. Scope guards to `self.screen.query_one` (or `self.query_one` inside a modal), NOT `self.query_one` on an `App`.
  - `_read_plan_content()` helper is local to `TaskDetailScreen`; codebrowser and brainstorm have their own content-access paths (annotation data for t571_8, DAG node state for t571_9) — they do not need this helper.
  - Board intentionally keeps the task↔plan inline toggle (`v` key); codebrowser and brainstorm auto-mount based on content availability. The difference is architectural, not a keybinding drift.

- **Manual verification deferred:** TUI behavior (Tab focus cycling, Up/Down minimap nav, Enter scroll-to-section, `V` fullscreen push, Escape dismiss, regression on `p`/`v`) is handed off to t571_7 (manual verification sibling task). Code-level checks (syntax, imports, binding wiring, handler presence) all passed.

<!-- /section: final_implementation_notes -->
