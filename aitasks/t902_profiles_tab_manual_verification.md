---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [ait_settings, execution_profiles]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 10:18
updated_at: 2026-06-02 10:25
---

## Origin

Risk-mitigation ("after") follow-up for t900, created at Step 8d after implementation landed.

## Risk addressed

code-health + goal-achievement TUI focus/layout risks — the redesigned Execution Profiles tab restructures layout, focus, and key handling in a 3000-line Textual TUI. These behaviors (1fr panes inside a padded TabPane, display-based search filtering vs. navigation, pinned selector while scrolling, Tab/Up-Down focus interplay) are only fully observable by running the TUI, and the headless pilot tests cannot fully substitute for a human look.

## Goal

Manually verify the redesigned "Execution Profiles" tab in `ait settings` (press `p`) behaves as intended across the items below.

## Verification Checklist
- [ ] Tab title and intro read "Execution Profiles" / "Execution profiles…".
- [ ] The profile selector and the Save/Revert/Delete buttons stay visible while the parameter list scrolls.
- [ ] The search box filters parameters by name only; clearing it restores all params; a group whose params are all filtered out hides its header.
- [ ] Save/Revert are disabled on a freshly selected profile; editing any field (cycle or string edit) enables them; pressing Save or Revert returns them to disabled. Delete is always enabled.
- [ ] w / v / x trigger Save / Revert / Delete respectively; they are inert on other tabs and while typing in the search box; button labels show the keys and carry no profile name.
- [ ] Tab / Shift+Tab cycle focus selector → search → params → buttons (and back); Up/Down move within a pane and skip the disabled Save/Revert buttons.
- [ ] Editing a field and Saving persists to the profile YAML; Revert restores the on-disk state.
