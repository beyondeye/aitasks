---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 23:19
updated_at: 2026-02-24 23:41
completed_at: 2026-02-24 23:41
---

with the introduction of aitask-pickweb skill and workflow, it has become relevant to allow the user to pre-lock a task before actual running of aitask-pickweb (see aitask-pickweb documentaiton page in website). locking can be currently done using the ait board ui. the ait-pickweb skill documentaiton in the website also talk about using ait own, but ait own does not actually currently exists: the bash scripts aitask_lock and aitask_own bash script are currently marked as internal scripts. so the question is: should expose them (or better only one of them) to allow the same funcitonaly that is tnt aitboard to be avaiable via scripts? and if yes which of them? own or lock? what is the difference between them? i think that is that own also update the assigned_to metadata field, but this is different from what the ait board currently do that only lock a task, but not "assign". an assigned tasks is a task which somebady is actually implementing. There is some redundancy between the two. probably we should expose only ait lock (and update the aitweb documentation correspondinlgy) and make sure that ait lock can automatically get the email from the current user profile
