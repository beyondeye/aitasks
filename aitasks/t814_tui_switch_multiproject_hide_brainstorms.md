---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tui_switcher, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-20 10:08
updated_at: 2026-05-20 10:09
---

in the TUI switcher that is used in all main aitasks frameworks tuis support showing TUI/code agents from multiple tmux sessions. I noticed that when in "multisession mode" the TUI switcher has a bug related to brainstorm sessions: when running the tui switcher from windows in aitasks-mobile session the brainstorm session for session aitasks are not visible when in the switcher select the aitasks session. A related bug: in a window in aitasks session when we open the tui switcher it shows the braisntorm session for aitasks both in the list of windows for the aitasks session and the in the list of windows for the aitasks-mobile session.
