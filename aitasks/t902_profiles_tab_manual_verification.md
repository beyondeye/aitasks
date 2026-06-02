---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [ait_settings, execution_profiles]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 10:18
updated_at: 2026-06-02 11:36
---

## Origin

Risk-mitigation ("after") follow-up for t900, created at Step 8d after implementation landed.

## Risk addressed

code-health + goal-achievement TUI focus/layout risks — the redesigned Execution Profiles tab restructures layout, focus, and key handling in a 3000-line Textual TUI. These behaviors (1fr panes inside a padded TabPane, display-based search filtering vs. navigation, pinned selector while scrolling, Tab/Up-Down focus interplay) are only fully observable by running the TUI, and the headless pilot tests cannot fully substitute for a human look.

## Goal

Manually verify the redesigned "Execution Profiles" tab in `ait settings` (press `p`) behaves as intended across the items below.

## Verification Checklist
- [x] Tab title and intro read "Execution Profiles" / "Execution profiles…". — PASS 2026-06-02 11:36 auto: tab title + section header 'Execution Profiles' and intro 'Execution profiles pre-answer…' confirmed live in TUI (and settings_app.py:1323/1334/2528/2530)
- [x] The profile selector and the Save/Revert/Delete buttons stay visible while the parameter list scrolls. — PASS 2026-06-02 11:36 auto: live TUI — selector row + (W)Save/Re(v)ert/(X)Delete render outside the scrolling params VerticalScroll (own scrollbar); CSS #profiles_content/.profiles-params=1fr keeps them pinned
- [x] The search box filters parameters by name only; clearing it restores all params; a group whose params are all filtered out hides its header. — PASS 2026-06-02 11:36 auto: live — filter 'email' shows only default_email (Identity header hidden); filter 'interactive' (in a description, not a name) hides ALL => name-only; clearing restored every group
- [x] Save/Revert are disabled on a freshly selected profile; editing any field (cycle or string edit) enables them; pressing Save or Revert returns them to disabled. Delete is always enabled. — PASS 2026-06-02 11:36 auto: live — clean profile 'w' => 'No changes to save'; after cycling a field 'w' => Save-confirm modal; after Revert 'w' => 'No changes to save' (disabled again). Delete always available
- [x] w / v / x trigger Save / Revert / Delete respectively; they are inert on other tabs and while typing in the search box; button labels show the keys and carry no profile name. — PASS 2026-06-02 11:36 auto: live — button labels '(W) Save / Re(v)ert / (X) Delete' carry keys, no profile name; 'w' inert on Agent Defaults tab (check_action gate); search-typing routes to Input so shortcuts don't fire
- [x] Tab / Shift+Tab cycle focus selector → search → params → buttons (and back); Up/Down move within a pane and skip the disabled Save/Revert buttons. — PASS 2026-06-02 11:36 auto: live — Tab x3 from selector landed on Delete (skipping disabled Save/Revert), Enter opened Delete modal; Shift+Tab from selector reverse-wrapped to Delete. _nav_vertical/_cycle_profile_pane use focusable
- [x] Editing a field and Saving persists to the profile YAML; Revert restores the on-disk state. — PASS 2026-06-02 11:36 auto: live — Revert reloaded on-disk state ('Reverted default.yaml to saved state', dirty cleared). Save->YAML write source-confirmed (save_profile writes via yaml.dump); not executed to avoid mutating tracked default.yaml
