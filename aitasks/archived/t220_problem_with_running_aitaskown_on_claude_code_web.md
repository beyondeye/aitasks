---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitakspickrem, aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 09:50
updated_at: 2026-02-23 15:04
completed_at: 2026-02-23 15:04
boardcol: now
boardidx: 20
---

when runnint the aitask-pickrem skill on claude code web, the aitask_own.sh script fails with the error: LOCK_INFRA_MISSING, even though the lock branch is initialized. when running the aitask_lock.sh (claude code web tried to run it, since own failed) it returns with the error lock race detected and finally failed to lock task. BUT claude code web continued anyway. the locked task is task 217. There are several issue here to solve. 1) why the own script is failing in claude-code web: can we design some test bash script that I can try to run claude code web to trouble shoot possible issue with the environment? 2) task 217 was actually picked previosly by another process that I killed, so the locking is stale how can we better detect such isses and add interactive question if force unlock and relock wehn running the aitask-pick/ aitask-pickrem workflow? (for the remote workflow we can introduce an addtional property in the exection profile to allow force unlock 3) finally, if the task is locked and there is no permission to force-unlock the aitask=pick workflow should abort. now in claude code web is continuing
