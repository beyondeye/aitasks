---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew, brainstorming]
children_to_implement: [t461_1, t461_2, t461_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-25 09:41
updated_at: 2026-04-13 11:44
boardidx: 10
---

When running code agents in agentcrew allow to set an override (using ait crew commands) for a code agent work defiintion or (perhaps in its command file?) that instruct the runner that this codeagent must be started
 in interactive mode. then update the ait brainstorm tui so that we can edit existing codeagent nodes so that we can add the force interactive mode command. also in ait brainstorm tui, in the wizard flow we use to
  create codeagents, add somewhere the option to force creation in interactive mode.
  Note that we have recently added tight integration between the aitasks framework and tmux, with the ait monitor tui that is designed to make it easy to monitor a large number of codeagent running in parallel: 
  when running agentcrew agent in interactive mode, they should integrate with the tmux session that is configured in settings tui as the tmux session name for the project where all codeagent windows are supposed to be 
  spawned so that the ait monitor can see them. 

this is a complex task, that should be split in child tasks

note that recent task 468 refactored common code to check for available terminal in order to spawn a codeagent in interactive mode: look at what was done there.
also consider that in the future we can further generalize this (launch mode for codeagent in crew:)
