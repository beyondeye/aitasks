---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask_monitor, aitask_monitormini]
created_at: 2026-04-05 10:53
updated_at: 2026-04-09 12:53
completed_at: 2026-04-09 12:53
boardidx: 60
---

currently we have a full fledged ait monitor tui, from where we can monitor the status of code agents running inside some tmux session. the ait monitor tui also integrate with the TUI switcher. we would like to create a new tui a "mini" monitor tui that is linked to a specific codeagent session (or multiple codeagent sessions in the same tmux window) that is show as a vertical or horizontal narrow pane in the same window where a code agent is spawn when triggering Pick action from ait board, when integrated with tmux: it should work in the following way: when spawning a new "pick" or "explore" codeagent from ait board or from tui switcher, in sume tmux window, also this minimonitor tui will be spawned in the same window (if no instance of it or of the full ait monitor) is not already running in the same tmux window. this miinimonitor should show list of existing codeagent session with idle status and support the "j" (switcher dialog), switch and ask info actions. the tui should monitor for existing codeagent panes in the same window and auto close itself if no more codeagent panes are present in the same window as itself. basically it should a compact version of the full ait monitor without preview, autoclose if no more codeagent in same window, and autospawn when new codeagent is spawn in a tmux window where an ait monior (full or mini) is not present yet
