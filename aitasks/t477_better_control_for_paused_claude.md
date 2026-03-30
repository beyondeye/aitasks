---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitor]
created_at: 2026-03-30 10:11
updated_at: 2026-03-30 10:11
---

currently in ait monitor has UX problems that make it not usable. it mainly goes down on how focusing the various panes and widget in the tui works:I propose to change how focusing works, we can move between options with tab, or by selecting with mouse, but after a few seconds the focus is lost automatically. this make the tui unusable. also instead of using tab to move between focusable widget right now, I suggest to use tab to move focus between panes (3 panes: need attention pane, full list pane and content preview pane, and allow top down arrows to move between focusable widget in each pane only. and in the preview pane, actually send all user keystroks to the previewed session, so we ca directly confirm/choose options when claude ask questions. only grab the "tab" key to change focus to the next pane. so this bassically substitute the confirm/later keybindings: we directly interact withe the preview pane and send actual user input directly to there. ask me questions if you need clarifications
