---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [remote, sanboxing, openshell]
created_at: 2026-03-22 10:04
updated_at: 2026-03-22 10:04
boardidx: 50
boardcol: now
---

https://github.com/NVIDIA/OpenShell is prject to support out of the box sandboxing for ai agents. I want to add integration with openshell, like automatically configure sandboxes to execute aitasks, a monitoring tui for running sandboxes or integrating with them. etc. the first stage is 1) study the openshell architecture 2) suggest implementation path for feature in aitasks to sandbox support. probably run this task in brainstorming mode. this is currently a very vague task. need brainstorming
note recent tasks 461 and 468 that started refactoring code that is used to launch a codeagent in an external emulator in interactive mode. the first step for integrating openshell should be in those places (launching a codeagent from ait board, ait codebrowser or ait brainstorm)
the main issue for openshell that i see is configuration (add a new tab in ait settings for manage openshell config for the repo/aitasks?) and low friction integration with the aitasks framework

