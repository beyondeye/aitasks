---
priority: high
effort: high
depends: []
issue_type: documentation
status: Implementing
labels: [aitask_monitor, tmux]
children_to_implement: [t519_1, t519_2, t519_3, t519_4, t519_5, t519_6]
folded_tasks: [494]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-10 17:38
updated_at: 2026-04-12 15:17
---

We have more ore less finalized integration of the the ait framework with tmux. with this integration aitasks become a full development environment, kind of an ide for agentic coding. we need to explain this into the dcoumentation, specifically in the terminal setup subpage of the installation page where we currently talk of multi-tab terminal workflow. Although not a requirement, a tmux based workflow is now the recommended one, since with ait monitor ait minimonitor and the new tui switcher that we have integrated in ait board ait monitor ait settings and in ait codebrowser, we can basically consider all tui + multiple codeagents as a full integrated development environment: no need to talk about Warp anymore. Also the role of tmux is now completely different and actually the documentaiton is wrong since tmux is not actually a terminal emulater, it "lives" inside a terminal emulator like Ghostty or WezTerm. we need also review the website Getting Started page and the TUIs page in website to explain how all are integrated and we can automatically swith between them when running tmux. The steps to start the aitask development environment are: 1) start a terminal 2) cd to the project repo dir where we want to work with aitasks and have run ait setup there 3) run tmux 4) run ait monitor: from there everything is integrated. please review the full code of all tuis, understand all the details of the aitask/tmux integration (review also latest aitasks, to follow the actual development of the tmux integration) and create multiple child tasks for updating the documentation. if needed add as steps of the implemenentation plan manual steps where screenshot of the new TUI switcher dialong, minimonitor and ait monitor and the new tmux tab in settings to complement the documentation being written. by the way there is no documentation of ait monitor tui itself in details and no documentaiton in details of the tui switcher. this where part of tasks t475_5 and t494 that should be folded into this task. ask me questions if you need more clarifications
A note about starting the new "new" coding agent "IDE" based on tmux integration of aitask tuis: starting the "IDE" require multiple steps: 1) start a terminal 2) cd to the project repo that has aitasks framework integration 3) run tmux 4) run ait monitor. this is not good User experience. We should document that this is the way to start the "IDE" but also find a way to make this easier: perhaps a dedicated new ait subcommand? also currently we running ait monitor in a tmux session whose name does not match the one defined for the project (see settings/tmux/default session) ait monitor ask to change the name to that of the expected session name. the problem is when we start tmux withot a session name. if we integrate starting tmux+monitor in ad-hoc ait subcommand we can set the session name parameter directly

## Merged from t494: j shorcut doc


we have recently added the "j" shortcut that triggers the tui switched dialog, integrated in all main TUIs (board codebrowser settings, brainstrom) but the shortcut is not documented in website doc, nor it is listed in TUI footer with list of shorcut, if we are running inside tmux (check) then this shortcut should be prominetly shown in footer of TUI, with its name "TUI switcher" (not Jump TUI), it also should be mentioned in website docs for all affected TUI, in a new documentation section for each TUI: tmux integration. ask me questions if you need clarfications

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t494** (`t494_j_shorcut_doc.md`)
