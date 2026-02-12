---
priority: medium
effort: high
depends: [97]
issue_type: feature
status: Ready
labels: [aitasks, claudeskills]
created_at: 2026-02-11 11:53
updated_at: 2026-02-12 10:30
boardcol: next
boardidx: 30
---

I would like to create a new claude code skill to explain some specific file or multiple files in the project repo. the explanation should be composed of several parts 1) the actual functionality implemeted by the code, example of usage if relevants (from the project itself if possible). In addition add the skill capability to track recent changes to completed aitasks, and explanation of the recent changes done: for finding changes relevant to the file simply search commits in git history that involve the file(s) for explanation of the changes, extract the aitask number associated with the commit searching the text "(t<taskid>)" in the commit description, then retrieve relevant aiplans files from aiplans/archived and use them together to the undertanding of the actual source code to explain where the changes where made and for what reason. ask me questions if you need clarifications the idea for the feature come from https://docs.entire.io/cli/commands#explain

**Note:** Task t97 implements shared infrastructure in `aiscripts/lib/task_utils.sh` (functions: `resolve_task_file`, `resolve_plan_file`, `extract_final_implementation_notes`) that can be reused for the commit-to-task mapping and plan resolution needed by this skill.
