---
priority: high
effort: high
depends: []
issue_type: documentation
status: Ready
labels: [aitask_monitor, tmux]
created_at: 2026-04-10 17:38
updated_at: 2026-04-10 17:38
---

We have more ore less finalized integration of the the ait framework with tmux. with this integration aitasks become a full development environment, kind of an ide for agentic coding. we need to explain this into the dcoumentation, specifically in the terminal setup subpage of the installation page where we currently talk of multi-tab terminal workflow. Although not a requirement, a tmux based workflow is now the recommended one, since with ait monitor ait minimonitor and the new tui switcher that we have integrated in ait board ait monitor ait settings and in ait codebrowser, we can basically consider all tui + multiple codeagents as a full integrated development environment: no need to talk about Warp anymore. Also the role of tmux is now completely different and actually the documentaiton is wrong since tmux is not actually a terminal emulater, it "lives" inside a terminal emulator like Ghostty or WezTerm. we need also review the website Getting Started page and the TUIs page in website to explain how all are integrated and we can automatically swith between them when running tmux. The steps to start the aitask development environment are: 1) start a terminal 2) cd to the project repo dir where we want to work with aitasks and have run ait setup there 3) run tmux 4) run ait monitor: from there everything is integrated. please review the full code of all tuis, understand all the details of the aitask/tmux integration (review also latest aitasks, to follow the actual development of the tmux integration) and create multiple child tasks for updating the documentation. if needed add as steps of the implemenentation plan manual steps where screenshot of the new TUI switcher dialong, minimonitor and ait monitor and the new tmux tab in settings to complement the documentation being written. by the way there is no documentation of ait monitor tui itself in details and no documentaiton in details of the tui switcher. this where part of tasks t475_5 and t494 that should be folded into this task. ask me questions if you need more clarifications
