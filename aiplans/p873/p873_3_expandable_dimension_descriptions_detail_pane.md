---
Task: t873_3_expandable_dimension_descriptions_detail_pane.md
Parent Task: aitasks/t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Sibling Tasks: aitasks/t873/t873_4_compare_wizard_scope_group_label_dimensions.md, aitasks/t873/t873_5_manual_verification_fix_brainstorm_dimension_proposal_linkin.md
Archived Sibling Plans: aiplans/archived/p873/p873_1_glob_dimension_link_expansion_and_badge_count.md, aiplans/archived/p873/p873_2_section_scroll_to_position_accuracy.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 17:33
---

# Plan: t873_3 — Expandable / full-text dimension descriptions in detail pane

## Context

Defect #3 of parent t873. In the `ait brainstorm` node detail pane, each
dimension renders as a `DimensionRow` pinned to CSS `height: 1`. The row's
`render()` concatenates the full (often paragraph-length) dimension value into
that single clipped line, so long descriptions are truncated with **no
in-pane way to read the full text**. The intended escape hatch — pressing
Enter to jump to the linked proposal section — is unreliable (the link is
often missing or mis-targeted, the subject of siblings t873_1/t873_2). This
task gives the detail pane a reliable, self-contained way to read a full
dimension description.

## Verification findings (this is the t873_3 verify pass)

Confirmed against current `main`:

- `DimensionRow` lives at `.aitask-scripts/brainstorm/brainstorm_app.py:1704`
  (plan's older `:1699` drifted ~+5 lines; structure intact): `DEFAULT_CSS`
  with `height: 1` at `:1718`, `render()` at `:1746`, `on_click` at `:1753`,
  `on_key` (Enter → `Activated`) at `:1757`.
- Rows are built in `_render_node_detail_widgets` (`:4969`), mounted into
  `#dash_node_info` / `#dag_node_info` containers (`:5049`). Those containers
  are `height: auto` (`:2414`, `:2438`); `Static` defaults to `width: 1fr`
  (fills the pane and wraps) — confirmed by `_show_brief_in_detail` (`:5076`)
  rendering a multi-line `Static` preview correctly in the same pane.
- **Therefore `render()` needs no `expanded` branch.** The full value is always
  in the renderable string; `height: 1` clips it to the first wrapped line and
  `height: auto` reveals all wrapped lines. Toggling the row height alone
  expands/collapses — a simplification over the original plan's step 3.
- `space` is unbound on the host screen (`:2751` BINDINGS — `s` is `tab_status`,
  not space) and nowhere else in the module. No collision with the existing
  Enter handler.
- Per `aidocs/tui_conventions.md:172`, inner-pane widgets surface
  discoverability "in the pane's own header text" (the footer rule at `:266`
  targets App/screen-level ops). The pane already uses this pattern: the
  `Press 'o' for operation details` hint at `:5018`.

## Approach

Inline auto-height toggle on `DimensionRow`, surfaced via a detail-pane hint
line. Keep the lightweight `on_key` style (consistent with the row's existing
Enter handler); do **not** route through `register_app_bindings`/
`_shortcuts_scope` — that machinery is for App/screen-owned customizable
shortcuts, not a per-row inner-widget key.

## Steps

1. **`DimensionRow` state** (`brainstorm_app.py:1736` `__init__`): add
   `self.expanded = False`.

2. **`on_key` toggle** (`:1757`): add a `space` branch alongside the existing
   `enter` branch:
   ```python
   def on_key(self, event) -> None:
       if event.key == "enter":
           self.post_message(self.Activated(self.dim_key))
           event.stop()
       elif event.key == "space":
           self.expanded = not self.expanded
           self.styles.height = "auto" if self.expanded else 1
           self.refresh(layout=True)
           event.stop()
   ```
   `refresh(layout=True)` forces the parent re-layout so the pane reflows when
   a row grows/shrinks.

3. **`render()` affordance** (`:1746`): keep the full value (always present;
   height controls clipping). Add a tiny caret prefix so a focused row signals
   it is expandable and reflects state — `▾` when expanded, `▸` when collapsed
   — without disturbing the `[N §]` badge:
   ```python
   def render(self) -> str:
       if self.section_count == 0:
           badge = "[dim][0 §][/]"
       else:
           badge = f"[bold cyan][{self.section_count} §][/]"
       caret = "[dim]▾[/]" if self.expanded else "[dim]▸[/]"
       return f"  {caret} {badge} [bold]{self.suffix}:[/] {self.value}"
   ```

4. **Discoverability hint** in `_render_node_detail_widgets` (`:5044`, right
   after the `Dimensions:` header is appended), mirroring the existing
   `Press 'o'…` hint:
   ```python
   widgets.append(Static("[bold $accent]Dimensions:[/]"))
   widgets.append(Static(
       "[dim]space: expand/collapse · enter: jump to proposal[/]",
       classes="meta_field"))
   ```

5. **No fallback needed.** The inline auto-height path is confirmed viable
   against this pane's layout (containers are `height: auto`, `Static` wraps at
   `width: 1fr`), so the plan's original `ModalScreen` fallback is not taken.
   This decision is recorded in Final Implementation Notes.

## Verification

- `bash tests/run_all_python_tests.sh` — full suite stays green (a pre-existing
  unrelated `test_desync_state` failure, noted in the t873_2 archived plan, may
  persist; the brainstorm tests must pass).
- **New light Pilot test** `tests/test_brainstorm_dimension_row_expand.py`
  (model on `tests/test_brainstorm_dag_click_focus.py`): a `_HostApp` mounts a
  single `DimensionRow` with a long value, focus it, press `space` →
  assert `expanded is True` and `styles.height` is `auto`; press `space` again
  → assert `expanded is False` and `styles.height` is `1`. Optionally assert
  pressing `enter` posts `DimensionRow.Activated` (no collision).
- Manual (no regeneration): `ait brainstorm` → session `crew-brainstorm-635` →
  focus a node with long dimension values → `space` expands a clipped row to
  the full wrapped description and collapses again; the caret flips ▸/▾; Enter
  still jumps to the proposal; the `space: expand…` hint is visible under the
  Dimensions header.

## Files to modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — `DimensionRow`
  (`__init__`, `on_key`, `render`) and `_render_node_detail_widgets` (hint line).
- `tests/test_brainstorm_dimension_row_expand.py` — new light Pilot test.

## Post-implementation

Follow task-workflow Step 8 (review/commit) and Step 9 (archival/merge).
Record the chosen inline-auto-height approach (fallback not taken) and any
upstream defect in the plan's Final Implementation Notes.
