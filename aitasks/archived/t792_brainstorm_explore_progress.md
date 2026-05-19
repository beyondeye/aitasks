---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [ait_brainstorm, brainstorm_explore]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-05-18 22:26
updated_at: 2026-05-19 09:50
completed_at: 2026-05-19 09:50
---

in ait brainstorm in brainstorm-635 I have run an explore operation with two subagents. I have noticed that while when running the previous "patch" operation the status tab shown the percent progress of the operation correctly progressing from 0 to 100%, for this explore operation, the status update of the two parallel agent where apparantly ignored: it would be nice to integrate a similar progress indicator as for the patch operation. the challenge here is that there are multiple agents working in parallel whose progress need to be merged. by the way I have identified another bug, when viewing the resulting generated new nodes in the brainstorm graph tab: I now correclty see two nodes (the two explore subagents generated node outputs), but only one of the reports its associated opration that generated it as explore, the other one has no such information (by the way now I noticed that the second explore node has actuall the information about all the sub agents that run: so that is what was suppossed to be? results for all multiple explore subagent in a single node? but how we merge/combine the results of the multiple agents? in practice we have multiple node? what the design dcoument for the explore operation in the aidocs for the brainstorm say that should work? I am confused
