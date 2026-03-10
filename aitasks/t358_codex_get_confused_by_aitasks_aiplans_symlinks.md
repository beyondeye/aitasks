---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [task_workflow, codexcli]
created_at: 2026-03-10 09:46
updated_at: 2026-03-10 09:46
---

when codex start implementation phase after plan confirmation it get confused by the aiplans aitaks symlinks. here is an excerpt of the conversation

• I’m moving from the approved plan into implementation. First I’m checking the current task/worktree state, existing plan file, and relevant stats/docs tests so I can make the code changes without trampling unrelated repo state.

Perhaps we can add specific instructions in the workflow to avoid the code agent getting confused? there are already indirect references to this at the end of the workflow at the finalization stage with all the notes about using ait git instead of regular git for task files, but probably there is not explicit references to these symlinks to a separate worktree that is checked out at .aitask-data, this can confuse the agent that is built to interact with a git repo and find it in an unusual state
