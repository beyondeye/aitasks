---
priority: medium
effort: high
depends: []
issue_type: bug
status: Implementing
labels: [aitakspickrem, remote]
children_to_implement: [t227_1, t227_2, t227_3, t227_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 15:33
updated_at: 2026-02-24 16:52
boardcol: now
boardidx: 10
---

I am trying to run task t187 on claude web. I started the session with aitask-pickrem 187. steps 1-4 of workflow run without errors. step 5 assign task still has issues:  aitask_own.sh 187 fails with LOCK_ERROR:race_exhaustion. when looking at the aitask-locks branch I don't see any file named after t187. the claude code running the remote tasks finally write the diagnosis that the environment has no push access to aitasks-locks branch (HTTP 403) and the comment: this is expected for claude code web with branch-restricted permissions. so basically we cannot lock aitasks when executing with aitask-pickrem. a possible alternative would be lock them manually before starting claude code web, for example if we create an android/ios board app that replicate features of the ait board app. also we should probably add the feature of allowing locking/unlccking tasks in the aitboard for remote execution. lock should probably expire after a day or so. there was previous work on how to handle stale locks to task file (see task t220) but I am not sure that work there was conclusive. so in brief what should be done 1)in aitask-pickrem remove locking logic and substitute instead with retrieval of the metadata of who is currently locking the task we want to execute: show email and when it was locked so at least we can see if A DIFFERENT USER IS TRYING implement the task 2) In task details in ait board ad button to lock/unlock a task: for force unlocking show the current locking metadata (email of who locked and locking time) 3) verify if task t220 has properly implemented some method to clear stale locks. this is a complex tasks, and it should be split in child tasks

Now that I think again about it there is an additional issue with claude web: it would probably will not have push access to the task-data branch with the plans, so it cannot write task plans, manipulate their status and so. this was also true before
because in any case claude web work in a separate branch. so in any case we need an ad hoc procedure when merging changes made by claude web in a branch to also read the aiplans/aitask modification made by claude web (that must be made in the
branch claude web is working in) and marge both the aitask aiplans (and archive) the updated aiplans aitasks to the task-data branch, and the actual code in the main branch. this is complex and potentially lengthy task task potentially nullify
the usefulness of running an aitask on claude web: I probably need to run a a local claude skill to check for branches with "signs" that it was a branch with claude web developement and handle the merge of code and tasks data. But it can be done.
Technically it can be implemented. so we need a way to identify branches that are results of claude code web runs: need to add some "marking" in the aitask-pickrem when a task is completed, and as said earlier implement all aitask and aiplan 
operations to operation in the current branch, the only one available to claude web

An addiional question if I should make a custom tailored skill aitask-pickrem that works specifically for claude-web or should I have an additional aitask-pickrem for environment with less limitations, that is sandobxed environemnt perhaps
set up by the user with some additional access permissions (for example to the task-data branch and the task-lock branch) perhaps I should keep the current implementation of aitask-pickrem for such environment and define a new skill 
aitask-pickremx for super restricted remote environment like claude code web
