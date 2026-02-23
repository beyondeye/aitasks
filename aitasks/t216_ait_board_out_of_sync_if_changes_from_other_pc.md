---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board]
children_to_implement: [t216_1, t216_2, t216_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 08:58
updated_at: 2026-02-23 15:51
boardcol: now
boardidx: 40
---

the ait board, if work is done from other PCs can get out of sync, we need to issue a git pull + rebase command to retrieve tasks updated by other pcs. the problem is that running git pull + rebase when inside a claude session is relatively safer since claude code is smart enough handling possible conficts, in the python ait board I am not sure I want to to automate calling git pull to refresh the task list, perhaps this could be an action accessible only from the command palette, in any case the action should have git rebase support it should not be just a call to git pull. propose me possible solutions. ask me questions if you need clarifications
after task t221, with task data in a separate branch, refreshing the board with git pull is not dangerous. so we should implement the feature for refreshing content
of the task-data branch (pull). perhaps eanble this only if the .aitask-data directory exists that means that we hava separate task branch, but it would be better
to refactor this logic to refresh tasks to an ait refresh that pull/merge task data. and integrate this with already existing autorefresh board mechanism that
that only refresh the board from data on disk, with git pull from remote repo. also we must be careful not cause issues hangs if no network connection. working
with board should not necessarily require an internet conenction. probbably instead of calling the command ait refresh call it ait sync: a bash script that 
push local changes and pull remote changes/ merges, handle conflicts interactively. so this is becoming a more complex tasks. the board will periodically run git sync and
if some errors, with open a dialog with the message with something like this: conflicts detected between local task definitions and remote: interactive resolve 
conflicts? if the user click on yes then we open a new shell (same mechanism as pick) where we launch ait sync interactively. so basically ait sync should have
a batch mode that return an error if something went wrong with specific error for merge conflicts, for integration with git board and possibly other scripts/skills
and an interactive mode for resolving conflicts. conflicts will be most frequently about metadata field (priority, board column etc) but even if conflicts are 
about descirption i think it is possible to add support for interactive conflict resolution to ait sync
