---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tui_switcher]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-18 16:14
updated_at: 2026-05-18 18:52
---

in the tui switcher that is a common dialog shared by all aitasks tuis, after the introduction of the status line with current git sync status, the footer with the list of supported keyboard shortcuts does not fit anymore: when shown in monitor and minimonitor, no footer fits at all, or only one footer line fit (depending on how many current tmux windows that fill the list are active. need to review and test to be sure that even with many tmux windows active and with the new git status line still all the foother shortcuts are visibile
