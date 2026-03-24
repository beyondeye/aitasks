---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [agentcrew, brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-24 12:41
updated_at: 2026-03-24 21:53
completed_at: 2026-03-24 21:53
---

currently when we start a codeagent with agencrew we use the ait codeagent invoke-raw -p command with inline prompt. that is the full prompt is printed to log. this is not desirable. we should be about to start the code agent by passing to the ait codeagent the path to the work2do file: I also noticed that the atual prompt passed to the code agent does not include proper links to the agent _input_md and _instructions.md file. and also all other references to work2do associated files are not assigned: see /home/ddt/Work/aitasks/.aitask-crews/crew-brainstorm-427/explorer_001_work2do.md and the _log.txt from the actual call to the codeagent. there is something missing here. this specifc  crew runner was started from he ait brainstorm tui. I thought that the job of the crew runner was to assemble all this instructions and send to the code agent the correct prompt
