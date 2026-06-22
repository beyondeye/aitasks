---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ui, brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-22 09:51
updated_at: 2026-06-22 09:53
---

Three related UX bugs in the `ait brainstorm` node-operation wizard
(`ActionsWizardScreen`) and its side-by-side proposal preview. All live in
`.aitask-scripts/brainstorm/brainstorm_app.py`. The wizard and
`ProposalPreviewPane` are shared by every node operation (explore, compare,
synthesize, module ops), so the preview fixes (#2, #3) cover all of them in one
place.

## Bug 1 — Arrow keys don't move focus between dimension checkboxes (explore op)

In the explore op's `section_select` step, the dimension list is mounted as
plain Textual `Checkbox` widgets inside a `VerticalScroll`
(`_actions_show_section_select()`, ~lines 4030–4059). These are only
Tab-focusable. `ActionsWizardScreen.on_key()` (~line 3415) has **no up/down
branch for the `section_select` step**, whereas the **compare** op's `config`
step already supports arrow nav via `_navigate_rows(...)` (lines 3481–3494).

**Fix:** add an up/down branch for the `section_select` step that reuses the
existing `_navigate_rows(...)` helper (target container `actions_content`,
row type `(Checkbox,)`), mirroring the compare-config pattern. Boundary
behaviour (no wrap, focus hand-off to the tab bar at top) should match the
existing helper.

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

**Fix:** add `on_section_minimap_section_selected()` to `ActionsWizardScreen`
that routes the event to its own `ProposalPreviewPane` (guard on the
`preview_proposal_minimap` control class, mirroring the app handler).

## Scope note
Fixes #2 and #3 are on the shared `ActionsWizardScreen` / `ProposalPreviewPane`,
so they apply to all node-op wizards that show a proposal side-by-side
(compare, synthesize, module ops), not just explore. Verify the compare and
synthesize wizards after the change.

## Acceptance criteria
- Up/down arrows move focus between dimension checkboxes in the explore
  `section_select` step (Tab still works; boundary behaviour matches compare).
- The proposal-preview shortcuts (line numbers, preview width, navigation) are
  visibly indicated on the explore step-3 screen and on any other node-op
  wizard step that shows the proposal side-by-side.
- Clicking a minimap section in the wizard scrolls the proposal to that section.
- Verified across explore, compare, and synthesize wizards.
- Follow TUI conventions (`aidocs/framework/tui_conventions.md`); add/adjust
  tests where the existing brainstorm TUI test suite allows.
