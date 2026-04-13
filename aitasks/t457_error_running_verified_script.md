---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [verifiedstats, task_workflow]
assigned_to: ''
created_at: 2026-03-24 22:23
updated_at: 2026-04-12 11:15
boardcol: unordered
boardidx: 100
---

I have noticed a couple of times that the verified score procedure in task workflow failed. the score was collected but the agent failed to call the script to update the score: here is the log of the failure:  feedback_collected is false and the fast profile has enableFeedbackQuestions: true. Using

can you help me trouble shoot the issue?
