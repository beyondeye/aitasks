---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [ait_settings, execution_profiles]
risk_mitigation_tasks: [902]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-02 09:21
updated_at: 2026-06-02 10:18
---

in ait settings in the Profiles tab: rename in the tab, profile -> execution profile in the tab title and in the intial description. and also redesign the screen so that we move the choice of the current viewed/edited execution profile to a separate pane that remain visible even when we scroll vertically the avaiable execution profile parameters, also add  a fuzzy search box that allow to search filter the shown execution profile parameters, also put the bottom buttons save/revert/delete to a separate pane that is not scrolled together with the execution profiles parameters and remove the the name of the profile from the buttons (since now the name of the current viewed/edited profile is always shown) and also make sure that the save button button is disabled is no change is currently from the stored value for the profile, same for the revert button. ask me questions if you need clarifications
Also activate the tab key to move focus between the various panes (selected profile pane, fuzzy search pane, profile parameters pane, button+pane)
also add keyboard shortcuts for the save/revert/delete buttons
