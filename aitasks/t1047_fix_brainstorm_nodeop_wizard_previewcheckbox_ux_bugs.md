---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ui, brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-22 09:51
updated_at: 2026-06-22 10:35
---

Three related UX bugs in the `ait brainstorm` node-operation wizard
(`ActionsWizardScreen`) and its side-by-side proposal preview. All live in
`.aitask-scripts/brainstorm/brainstorm_app.py`. The proposal preview
(`ProposalPreviewPane`) is used by the **explore** and **module_decompose**
config steps; the wizard hosts every node operation.

> **Re-scoped (2026-06-22):** investigation showed these are not three
> independent bugs but **fallout from the t983_11 relocation** that re-hosted
> the former "Actions tab" into the `ActionsWizardScreen` modal. Two helpers
> (`_navigate_rows`, `_focus_within`) were copied byte-for-byte App↔wizard, and
> the copied `_navigate_rows` hard-codes `self.query_one(TabbedContent)` for its
> tab-bar boundary — which raises `NoMatches` in the modal (no `TabbedContent`),
> breaking **all** wizard arrow-nav routed through it. The App's
> `on_section_minimap_section_selected` is now dead code (the preview pane is
> modal-only). So the fix is a **targeted consolidation** — remove the
> duplication that caused the bugs — not three per-symptom patches. The broader
> file modularization stays in **t1048** (depends on this task), which will
> later relocate the new shared mixin into a module.

## Bug 1 — Arrow keys don't move focus between dimension checkboxes (explore op)

In the explore op's `section_select` step, the dimension list is mounted as
plain Textual `Checkbox` widgets inside a `VerticalScroll`
(`_actions_show_section_select()`, ~lines 4030–4059). These are only
Tab-focusable. `ActionsWizardScreen.on_key()` (~line 3415) has **no up/down
branch for the `section_select` step**, whereas the **compare** op's `config`
step already supports arrow nav via `_navigate_rows(...)` (lines 3481–3494).

**Fix (consolidation):** extract a shared, context-agnostic `RowNavMixin`
(new module `brainstorm/nav_mixin.py`) holding the single `_navigate_rows` /
`_focus_within`, with the tab-bar boundary as an overridable hook
(`_nav_tab_bar()` — App returns its `Tabs`, the modal returns `None` → stop at
top). Delete both copies. Then add the missing `section_select` up/down branch
to `on_key` (reusing the now-fixed helper).

## Bug 2 — Contextual shortcuts not visible (wizard step 3 of 4)

On the explore "exploration mandate" step (step 3 of 4) with the proposal
shown side-by-side, the active shortcuts for the proposal (e.g. `alt+n` toggle
line numbers, `alt+w` preview width) are not visible. Two causes:
- `ActionsWizardScreen.BINDINGS` (lines 3319–3330) all set `show=False`, so the
  `Footer` renders nothing.
- The compare/synthesize steps mount a manual hint `Label`
  ("↑↓ Navigate  Space Toggle …", lines 4080–4082) but the explore config step
  does not.

**Fix:** surface the contextual shortcuts on the explore step (and any other
proposal-preview step missing them) — by flipping the relevant preview bindings
to `show=True` and/or mounting a contextual hint label consistent with the
compare/synthesize steps. Keep the displayed shortcuts accurate to what is
actually active on that step.

## Bug 3 — Clicking the proposal minimap does not jump to the section

The minimap posts `SectionMinimap.SectionSelected`, handled by
`BrainstormApp.on_section_minimap_section_selected()` (lines 8624–8639) which
calls `ProposalPreviewPane.scroll_to_section()`. But `ActionsWizardScreen` is a
`ModalScreen`: the message bubbles to the modal and stops — the modal has no
handler, so it never reaches the app. `scroll_to_section()` itself works.

**Fix (consolidation):** move the handler onto `ActionsWizardScreen` (where the
pane lives) and **delete the dead App copy**. Leave `NodeDetailModal`'s separate
id-based minimap handler untouched.

## Scope note
The preview steps (explore, module_decompose) share `ActionsWizardScreen` /
`ProposalPreviewPane`, so the hint (#2) and minimap (#3) fixes cover both. The
shared `RowNavMixin` is also on the App's Browse/Session nav path — verify no
regression there.

## Acceptance criteria
- `_navigate_rows` / `_focus_within` exist in exactly one place (shared mixin);
  no byte-for-byte App↔wizard duplicate remains.
- Up/down arrows move focus between dimension checkboxes in the explore
  `section_select` step (Tab still works); pressing up at the top boundary does
  not crash (the `NoMatches` regression).
- App Browse/Session row nav is unchanged (up-past-top still focuses the tab bar).
- The proposal-preview shortcuts (line numbers, preview width, navigation) are
  visibly indicated on the explore (and module_decompose) preview config step.
- Clicking a minimap section in the wizard scrolls the proposal to that section;
  the dead App handler is removed.
- Follow TUI conventions (`aidocs/framework/tui_conventions.md`); add pilot/unit
  tests for the mixin contract, the section nav, the hint, and the minimap route.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-22T07:35:16Z status=pass attempt=1 type=human
