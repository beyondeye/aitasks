---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-09 09:26
updated_at: 2026-06-10 10:40
---

## Origin

Spawned from t945_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_app.py:886 — _InlineSectionMinimap documents itself as "Tab-binding-free" (BINDINGS = []) but Textual merges BINDINGS across the MRO, so it still inherits SectionMinimap's priority tab→toggle_focus binding; its remaining consumer (NodeDetailModal) masks this with its own screen-level tab binding, so it is not visibly broken, but the docstring claim is false and the inherited binding is latent/misleading.`

## Diagnostic context

While fixing t945_3's "Tab stuck on the proposal-preview minimap" bug, MRO-binding inspection confirmed `_NoTabMinimap(BINDINGS = [])` still resolves a merged `tab → toggle_focus` priority binding from `SectionMinimap`. t945_3 sidestepped this for the preview pane by adding a dedicated `_PreviewMinimap` subclass that *overrides* the Tab/Shift+Tab bindings (overriding a key works; clearing the list does not). `_InlineSectionMinimap` is now used only by `NodeDetailModal`, which masks the inherited binding with its own screen-level `tab` priority binding — so the bug is latent, not active.

## Suggested fix

Either drop `_InlineSectionMinimap` entirely (fold its only consumer onto a correct minimap subclass) or fix the comment/implementation so the inherited binding is genuinely neutralized (override the key, do not set `BINDINGS = []`). Verify NodeDetailModal's Tab/minimap behavior is unchanged.
