---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [brainstorming, agentcrew]
children_to_implement: [t386_7, t386_9, t386_10]
created_at: 2026-03-15 09:06
updated_at: 2026-03-17 17:10
boardcol: unordered
boardidx: 120
---

We want to create infrastructure to support exection of multiple code agents in the background, coordinating their work, monitor their progress, forcing stopping them. the idea is that the code agents get their input from a file. each batch codeagent, also periodically write into a file to report their are "alive", and read from a "commands' file with update instruction (like force stop, or updated instructions). into the "alive" file the agents also write their status like "running", or whatever the status they want to report. (progress they are doing, and so on)

the idea is creating infrastructure for a DAG of coding agents that coordinate their work. and also develop helper bash script to extract a report of all running agents status, giving isntrcutions (like force stop) gathering outputs. each group of subagents should a git branch  where all their work and status is put. this branch will be deleted once the work is completed analyzed and summarized.

it is important to standardized some basic possible statuse for an agent like: Waiting, Running, Completed, Aborted, Error, so that the coordinating bash script and the framework in general will be able to parse and collect and act based on their status

the separate branch is for agent coordination (agent input, agent status, agent output, agent intra run instruction) but actual work will be possibly also done in main branch

so now after the genral idea lets talk about the some more detailed idea

so each agentcrew that has their agentcrew branch is initialized by a script crew init (init branch) for some agentcrew id string.

then there is a script crew addtask that initialize files that control an agent in some agentcrew branch: name, task to execute (markdown),

a scipt for updating the status of an agent in the agentcrew branch where the agent work according the agentcrew and agentname. this script is called by agents to update their status. by the way all agents at astart are givena an instruction file (in addtion to their task file, where it is explained what script to call to any of their lifecicle actions

All files associated to some agent in an agentcrews (like their input file, their ouputful, their taskfile, their status file are all in their associated agentcrew branch, and named with file name starting with the agentname and suffix that identify the specific file, like _input.md, _task.md, _status.md, and so on

clarification: in order to avoid ambiguities don't use "task" to describe the file that describe the work to be done, but instead "work2do"

the crew addtask should specifiy the list of subagent names that the created subagent depends on and the list of subagents whose work is unlocked by the completion of the subagent

actually no, each crew addtask specify only the list of the nameagents it depends on

then there is the crew runner script. the crew runner script purpose is periodically check which subagents that has not already executed are ready to execute (checking if their input is valid, and the subagents from which they depends on already completed execution and periodically update their status (waiting for agents .... [agent names]) or starting them in not started yet and their not waiting for any other agents, and also checking agents status and updating a global list (for the agentcrew, with all the status, time running for each currently running subagents, the last time running agents reported to be alive, and their reported progress/status, and identifying which agent is potentially stuck, and percentage of completion of the full agentcrew flow, total running time and expected time to completion

the crew runner script is basically runned periodically, and we need also a TUI (python with textual as all TUIs in aitaks, where we can spawn agentcrew of various types, start/stop them (basically start stop the periodical call to crew runner, and also in case of stop, basically writing a kill signal in the agent intra run instruction, that the subagent is supposed to read periodically.

when the kill signal is sent to an agentcrew (store the general status for an agentcrew so that the status "killing" means that we still need to periodically run crew runner to check agent status and send kill instruction to running agents). according the the general "agentcrew" status (stored as a file also in the agentcrew branch) we know in which mode to run (periodically) crew runner: in kill mode or run mode or "pause" mode

the "pause mode" means that the crew runner should send "kill" signal but preserve the general state of the agentcrew, and update it in a way that will make possible to resume execution later

now about the main "loop" for each subagent "work2do" so the agents "work2do" file should be structured in a way so that in addition to the actual work to do, there should be "checkpoints" where the subagent call the agentcrew framework scripts (as defined for it by the general "instruction.md" that is passed to it with the name of the scripts and how to call them for each opration, like updating status, reading input, writing ouputs, checking for intrarun instructions, running abortprocedure, updating progress status and alive status) each this standard "lifecycle" oprations call in periodical check at "checkpoints" that must be well defined in the work2do flow. the actual design will be agentcrew dependent and not in the scope of this aitask.

THIS IS THE GENERAL IDEAL. brainstorm about this specification and lets discuss the implementation of this very complex tasks, that should splitted in child tasks
