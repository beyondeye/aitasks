---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [claudeskills, aitask_fold]
children_to_implement: [t143_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-16 19:19
updated_at: 2026-02-17 10:02
---

We have recently added the feature of folded tasks, in the aitask_explore claude skill, that is tasks that are incorporated in a marged tasks and they are no more independent. When executing the merged task that contains a list of folded tasks, at the of implementation, allthe associated folded tasks are simply deleted because they were actullay incorporated in the merged task and there is not need to document them separately in the archived task directory and  archived aiplans directory. the idea of the aitask_fold skill is do something similar as what is done in the aitask_explore skill but concentrated on 1) identifying tasks conneted tasks 2) and show them to the user to fold them in a single task and execute it (like in aitaks_explore) or if a list of task ids are provided explicitely by the user as argument to the aitask_fold skill just fold them without interactive tasks to fold selection. ask me questions if you need clarificaitons
