---
priority: medium
effort: medium
depends: [t848_3]
issue_type: refactor
status: Ready
labels: [custom_shortcuts, verification]
created_at: 2026-06-01 12:45
updated_at: 2026-06-01 12:45
boardidx: 20
---

## Reassess: settings tab-switcher footer registry-derivation

During t848_7 manual verification, verification item #6 —

> [t848_3] Settings tab-switcher footer correctly lists current tab keys
> (registry-derived, not hardcoded).

— was found **not satisfied**: the Settings TUI tab-switch keys remain
hardcoded, not registry-derived. This task is to **reassess the deferral
decision** taken during t848_3 and either implement the migration or formally
accept the current state.

### Current state (the thing to reassess)

The tab-switch keys are a hardcoded `_TAB_SHORTCUTS` dict in
`settings/settings_app.py` (`a/b/c/m/p/t/s → tab ids`), driven by a raw
`on_key` handler (not Textual `Binding`s, so they are not in the keybinding
registry and not user-customizable). Three hand-composed footer hint strings
(e.g. `Enter: edit | ↑↓: navigate | a/b/c/m/p/t: switch tabs`) are likewise
literal, not rendered via the registry.

### Why this was deferred (the decision under review)

p848_3 (Deviations) deliberately deferred migrating these to a
registry-derived `self.app.label(...)` helper, deferring it to t848_5/t848_6 —
**which did not pick it up.** The stated rationale: adding hidden
`Binding("up", "nav_up", ...)` / per-tab nav bindings "would create new actions
without any user-customization story," since the tab-switch keys are a fixed
navigation convention rather than customizable shortcuts.

### Decision to make

1. **Accept as-is** — formally record that tab-switch keys are an intentional
   fixed convention, and adjust verification item #6's wording (or drop it) so
   the requirement matches reality. No code change.
2. **Migrate** — surface the tab-switch keys through the keybinding registry so
   the footer hints are registry-derived and the keys participate in the
   shortcut editor / overrides like every other binding.

Weigh the user-customization value against the added surface (new action_ids,
override story, coherence-lint scope) before implementing option 2.

### Source / traceability

- **Manual-verification task:** `aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md` (item #6)
- **Origin feature task:** t848_3
- **Origin archived plan:** `aiplans/archived/p848/p848_3_sweep_remaining_tuis.md` (see Deviations — "settings three hand-composed footer strings left as-is")
- **Introducing commit:** 663755c0 refactor: Sweep remaining TUIs onto ShortcutsMixin (t848_3)
- **Primary file:** `.aitask-scripts/settings/settings_app.py` (`_TAB_SHORTCUTS`, `on_key`, hand-composed footer strings)

Auto-generated from a manual-verification failure in t848_7 item #6, then
reframed from a bug fix into a decision reassessment per user direction.
