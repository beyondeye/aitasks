---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitakspickrem, remote]
created_at: 2026-02-23 15:33
updated_at: 2026-02-23 15:33
---

I am trying to run task t187 on claude web. I started the session with aitask-pickrem 187. steps 1-4 of workflow run without errors. step 5 assign task still has issues:  aitask_own.sh 187 fails with LOCK_ERROR:race_exhaustion. when looking at the aitask-locks branch I don't see any file named after t187. the claude code running the remote tasks finally write the diagnosis that the environment has no push access to aitasks-locks branch (HTTP 403) and the comment: this is expected for claude code web with branch-restricted permissions. so basically we cannot lock aitasks when executing with aitask-pickrem. a possible alternative would be lock them manually before starting claude code web, for example if we create an android/ios board app that replicate features of the ait board app. also we should probably add the feature of allowing locking/unlccking tasks in the aitboard for remote execution. lock should probably expire after a day or so. there was previous work on how to handle stale locks to task file (see task t220) but I am not sure that work there was conclusive. so in brief what should be done 1)in aitask-pickrem remove locking logic and substitute instead with retrieval of the metadata of who is currently locking the task we want to execute: show email and when it was locked so at least we can see if A DIFFERENT USER IS TRYING implement the task 2) In task details in ait board ad button to lock/unlock a task: for force unlocking show the current locking metadata (email of who locked and locking time) 3) verify if task t220 has properly implemented some method to clear stale locks. this is a complex tasks, and it should be split in child tasks
