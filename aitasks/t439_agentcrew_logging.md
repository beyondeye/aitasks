---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [brainstorming, agentcrew]
children_to_implement: [t439_1, t439_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 12:05
updated_at: 2026-03-23 12:53
---

ait brainstorm is based on agentcrews. we currently don't have a log of actual commands issued by the crew runner to spwan codeagents and when the batch commands return or if they log output, we should better handle logging, this is needd also to troubple shoot agentcrew run that fails. currently agentrunner create the inputs for angentcrew agent and monitor alive files and outputs but don't record actual logs from batch execution. there should be a way (perhaps with output redirect for the spawn batch code agents, so that we can what is happening, and way from ait agencrew tui interface to browse this log files/ monitor which one was last updated/order them by update time and allow to easily open and read them in the tui. the same functionality should be integrated in the ait brainstorming tui reusing common code for this
