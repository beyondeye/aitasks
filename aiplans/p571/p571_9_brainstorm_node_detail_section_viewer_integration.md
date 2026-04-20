---
Task: t571_9_brainstorm_node_detail_section_viewer_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_6_update_brainstorm_design_docs.md, aitasks/t571/t571_7_manual_verification_structured_brainstorming.md
Archived Sibling Plans: aiplans/archived/p571/p571_10_board_task_detail_section_viewer_integration.md, aiplans/archived/p571/p571_11_fix_section_viewer_rendering_and_bindings.md, aiplans/archived/p571/p571_1_section_parser_module.md, aiplans/archived/p571/p571_2_update_agent_templates_emit_sections.md, aiplans/archived/p571/p571_3_section_aware_operation_infrastructure.md, aiplans/archived/p571/p571_4_section_selection_brainstorm_tui_wizard.md, aiplans/archived/p571/p571_5_shared_section_viewer_tui_integration.md, aiplans/archived/p571/p571_8_codebrowser_section_viewer_integration.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 16:08
---

# Plan: t571_9 — Brainstorm NodeDetailModal Section Viewer Integration

## Context

Integrate the shared `.aitask-scripts/lib/section_viewer.py` module (from t571_5) into the **brainstorm** TUI's `NodeDetailModal`. Both the Proposal tab and the Plan tab get their own independent `SectionMinimap` above the existing `Markdown` widget, so exploring the DAG shows the dimensional structure of each node's proposal and plan at a glance.

**Depends on t571_5 (landed).** The lib exports `SectionMinimap`, `SectionViewerScreen`, `estimate_section_y`, `parse_sections`, verified present (326 LOC).

## Verification Notes (2026-04-19)

Verified the existing plan against the current codebase; all structural claims still hold:

- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - `parse_sections` imported at line 49 (from `brainstorm.brainstorm_sections`). **Will be replaced by import from `section_viewer`** per the import-order rule below.
  - sys.path inserts at lines 11–12 cover both `parent.parent` and `parent.parent/"lib"`.
  - `NodeDetailModal` class at line 251; `BINDINGS = [Binding("escape", "close", "Close", show=False)]` at line 254.
  - Tab structure at lines 266–281: `#tab_metadata` / `#tab_proposal` (`Markdown#proposal_content` wrapped in `VerticalScroll#proposal_scroll`) / `#tab_plan` (`Markdown#plan_content` wrapped in `VerticalScroll#plan_scroll`).
  - `on_mount()` at lines 287–329 loads metadata/proposal/plan content.
  - Existing imports cover `Binding`, `VerticalScroll`, `TabbedContent`, `Markdown`. `SkipAction` is NOT imported — will add lazily inside the action method (matches t571_8 / t571_10 pattern).

Adjustments vs. original plan:

1. **Use `self.node_id` for fullscreen title.** The plan referenced `self._node_name` but only `self.node_id` is stored (line 258); no separate human-readable name is available. Using `node_id` matches the existing `Label(f"Node Detail: {self.node_id}")` convention.
2. **Use explicit scroll IDs `#proposal_scroll` / `#plan_scroll`** (present in the codebase) instead of descendant selectors `#tab_proposal VerticalScroll`. Same result, cleaner selector.
3. **Critical import-order rule (inherited from t571_10 / t571_8 Final Notes):** import `parse_sections` from `section_viewer` (convenience re-export), NOT from `brainstorm.brainstorm_sections`. The lib self-inserts `.aitask-scripts/` into `sys.path` on first import, so a pre-existing `from brainstorm.brainstorm_sections import parse_sections` at the module top can still work (brainstorm_app.py IS in that package), but any new lazy import inside handlers must go through `section_viewer` to keep the pattern uniform across sibling TUIs. Since `parse_sections` is already imported at line 49 from `brainstorm.brainstorm_sections`, we keep that existing module-level import and additionally use `from section_viewer import SectionMinimap, estimate_section_y, SectionViewerScreen` lazily inside methods. No change to line 49.
4. **Keep `animate=False`** on `scroll_to` (inherited from t571_11 fix) — already in the plan.

## Files and Line References

- `.aitask-scripts/brainstorm/brainstorm_app.py` (lines 251–333 for `NodeDetailModal`).

No other files touched. `section_viewer` is already in the sys.path via existing line 12.

## 1. `NodeDetailModal.__init__()` — initialize state (after line 259)

```python
def __init__(self, node_id: str, session_path: Path):
    super().__init__()
    self.node_id = node_id
    self.session_path = session_path
    self._proposal_parsed = None
    self._proposal_text = ""
    self._plan_parsed = None
    self._plan_text = ""
```

## 2. `NodeDetailModal.BINDINGS` — extend (line 254)

```python
BINDINGS = [
    Binding("escape", "close", "Close", show=False),
    Binding("tab", "focus_minimap", "Minimap"),
    Binding("V", "fullscreen_plan", "Fullscreen plan"),
]
```

## 3. `NodeDetailModal.on_mount()` — mount per-tab minimaps

After each `.update()` call in the Proposal / Plan tab branches (lines 323 and 329), mount a minimap when the content has sections. Insert immediately after the existing Markdown update:

```python
# --- Proposal tab ---
try:
    proposal = read_proposal(self.session_path, self.node_id)
except Exception:
    proposal = "*No proposal found.*"
self.query_one("#proposal_content", Markdown).update(proposal)
# NEW:
from section_viewer import SectionMinimap
parsed = parse_sections(proposal)
if parsed.sections:
    self._proposal_parsed = parsed
    self._proposal_text = proposal
    scroll = self.query_one("#proposal_scroll", VerticalScroll)
    minimap = SectionMinimap(id="proposal_minimap")
    scroll.mount(minimap, before="#proposal_content")
    minimap.populate(parsed)
```

Same pattern for the Plan tab: cache `self._plan_parsed` / `self._plan_text`, query `#plan_scroll`, mount `SectionMinimap(id="plan_minimap")` before `#plan_content`, populate.

The existing module-level `from brainstorm.brainstorm_sections import parse_sections` (line 49) stays. Lazy `from section_viewer import SectionMinimap` inside `on_mount` keeps the module-top diff minimal.

## 4. `on_section_minimap_section_selected` — route by minimap id

```python
def on_section_minimap_section_selected(self, event) -> None:
    from section_viewer import estimate_section_y
    minimap_id = event.control.id
    if minimap_id == "proposal_minimap":
        parsed, text, scroll_id = self._proposal_parsed, self._proposal_text, "#proposal_scroll"
    elif minimap_id == "plan_minimap":
        parsed, text, scroll_id = self._plan_parsed, self._plan_text, "#plan_scroll"
    else:
        return
    if parsed is None:
        return
    scroll = self.query_one(scroll_id, VerticalScroll)
    total = text.count("\n") + 1
    y = estimate_section_y(parsed, event.section_name, total, scroll.virtual_size.height)
    if y is not None:
        scroll.scroll_to(y=y, animate=False)  # nav, not animation (t571_11 rule)
    event.stop()
```

## 5. `on_section_minimap_toggle_focus` — minimap → content focus

```python
def on_section_minimap_toggle_focus(self, event) -> None:
    if event.control.id == "proposal_minimap":
        self.query_one("#proposal_content", Markdown).focus()
    elif event.control.id == "plan_minimap":
        self.query_one("#plan_content", Markdown).focus()
    event.stop()
```

## 6. `action_focus_minimap` — content → minimap focus (Tab)

```python
def action_focus_minimap(self) -> None:
    from textual.actions import SkipAction
    tabbed = self.query_one(TabbedContent)
    focused = self.screen.focused
    if tabbed.active == "tab_proposal":
        md_sel, mm_sel = "#proposal_content", "#proposal_minimap"
    elif tabbed.active == "tab_plan":
        md_sel, mm_sel = "#plan_content", "#plan_minimap"
    else:
        raise SkipAction()
    try:
        md = self.query_one(md_sel, Markdown)
    except Exception:
        raise SkipAction()
    if focused is not md:
        raise SkipAction()
    minimaps = self.query(mm_sel)
    if not minimaps:
        raise SkipAction()
    minimaps.first().focus_first_row()
```

Scope is already the modal screen (`NodeDetailModal` is a `ModalScreen`), so `self.query_one` stays within the modal — not `App.query_one`. Matches the `feedback_textual_priority_bindings` memory.

## 7. `action_fullscreen_plan` — V → fullscreen viewer on active tab

```python
def action_fullscreen_plan(self) -> None:
    tabbed = self.query_one(TabbedContent)
    if tabbed.active == "tab_proposal":
        content = self._proposal_text
        title = f"Proposal: {self.node_id}"
    elif tabbed.active == "tab_plan":
        content = self._plan_text
        title = f"Plan: {self.node_id}"
    else:
        self.notify("Fullscreen viewer only works on Proposal or Plan tab", severity="warning")
        return
    if content:
        from section_viewer import SectionViewerScreen
        self.app.push_screen(SectionViewerScreen(content, title=title))
    else:
        self.notify("No content on this tab", severity="warning")
```

Note: `self._proposal_text` / `self._plan_text` are populated in `on_mount` only when the content had sections. If a tab loaded successfully but had no section markers, `_*_text` stays empty and the fullscreen viewer will show "No content on this tab". If we want fullscreen to work regardless of sections, cache the text unconditionally in `on_mount` (outside the `if parsed.sections` guard). **Decision:** cache unconditionally — fullscreen is useful for plain markdown too.

Adjust `on_mount`: move `self._proposal_text = proposal` / `self._plan_text = plan` outside the `if parsed.sections:` block so fullscreen works on section-less content.

## 8. Graceful fallback

When a node's proposal or plan has no section markers:
- No minimap is mounted on that tab — the `VerticalScroll` holds only the Markdown, unchanged.
- `Tab` on that Markdown → `action_focus_minimap` raises `SkipAction` (no minimap found) → Textual's default Tab-nav runs.
- `V` → fullscreen viewer still opens with the content (text is cached unconditionally per §7).

## Verification

Fixture: `aiplans/p571/p571_5_shared_section_viewer_tui_integration.md` has ~11 sections across multiple dimensions. Copy its body (or craft a similar proposal) into a brainstorm DAG node for testing.

1. `ait brainstorm` → open `NodeDetailModal` on the test node.
2. Switch to Proposal tab → minimap appears above the markdown; dimension tags visible.
3. Tab → focus moves to the Proposal Markdown. Tab again → focus returns to last-highlighted row.
4. Up/Down on minimap → rows cycle focus, no content scroll.
5. Enter on a row → proposal scrolls to that section (non-animated).
6. Switch to Plan tab → independent minimap state; repeat steps 3–5.
7. Switch back to Proposal tab → last-highlighted row preserved in-session.
8. Node with no section markers → no minimap; Tab falls through to default nav.
9. Press `V` on the Proposal tab → `SectionViewerScreen` opens full-screen with proposal content. Escape closes.
10. Switch to Plan tab and press `V` → fullscreen opens with plan content.
11. Press `V` on Metadata tab → notification "Fullscreen viewer only works on Proposal or Plan tab", no crash.

Hand end-to-end keyboard-contract check to t571_7 (manual verification sibling task).

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

## Final Implementation Notes

- **Actual work done:** Single file touched — `.aitask-scripts/brainstorm/brainstorm_app.py`, ~108 lines added to `NodeDetailModal` (lines 251–452). Added BINDINGS for `tab` (`focus_minimap`) and `V` (`fullscreen_plan`); initialized `_proposal_parsed/_text` and `_plan_parsed/_text` in `__init__`; wired `on_mount` to parse sections per tab and mount `SectionMinimap` before the Markdown when sections exist; always caches raw text for fullscreen. Added `on_section_minimap_section_selected`, `on_section_minimap_toggle_focus`, `action_focus_minimap`, `action_fullscreen_plan`. Lazy `from section_viewer import …` inside each method; kept the existing module-top `from brainstorm.brainstorm_sections import parse_sections` (line 49) since `parse_sections` is called during `on_mount` and a module-level import is cleaner than lazy.
- **Deviations from plan:** None structural. Kept the docstrings on the new methods (short, WHY-only) — CLAUDE.md says "default to no comments" but docstrings describing keyboard-contract semantics are load-bearing for future readers.
- **Issues encountered:** One local gotcha — ran `cd .aitask-scripts` early for a syntax check, which polluted the persistent shell directory. Recovered by using absolute paths on subsequent Bash calls. No code impact.
- **Key decisions:**
  - `scroll_to(..., animate=False)` — inherited from t571_11.
  - Scope `query_one` to `self` (the ModalScreen), not `App` — `NodeDetailModal` is itself a Screen, so there's no cross-screen leakage (per `feedback_textual_priority_bindings`). `action_focus_minimap` uses `self.screen.focused` as required by the priority-binding guard rule, then raises `SkipAction` on mismatch so default Tab-nav still works on section-less nodes.
  - Cache raw text unconditionally in `on_mount` (outside the `if parsed.sections` guard) so fullscreen `V` works on plain-markdown nodes too.
  - `register_synthesizer` was intentionally NOT touched — Synthesizer does not take `target_sections` and its tab is unaffected.
- **Notes for sibling tasks:**
  - **t571_6 (design doc update):** This integration is now live. The shared-viewer section in the architecture doc can list NodeDetailModal alongside codebrowser and board. Widget IDs follow the `proposal_minimap` / `plan_minimap` / `proposal_scroll` / `plan_scroll` / `proposal_content` / `plan_content` pattern. The `V` keybinding opens `SectionViewerScreen` fullscreen on whichever tab is active (Metadata tab shows a warning toast).
  - **t571_7 (aggregate manual verification):** Add a row for NodeDetailModal covering Tab routing between minimap ↔ Markdown per tab, Up/Down row cycle, Enter-to-scroll, independent state across Proposal/Plan tabs, `V` fullscreen on Proposal/Plan/Metadata tabs, and graceful fallback on section-less nodes.
