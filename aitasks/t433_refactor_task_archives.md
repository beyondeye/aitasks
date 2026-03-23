---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [task-archive]
children_to_implement: [t433_1, t433_2, t433_3, t433_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 09:20
updated_at: 2026-03-23 09:58
---

the current way task archives (old.tar.gz in archived task directory) is not scalable. also we would like the refactor and tidy up all bash scripts that we current use to access tasks and plan data, they have evolved quite a bit we have logic to handle task data in many script with potential duplicates. it is possible that in the future we will be required to change the backend / the way we store task data. for this is reason we want the "interface" through which we access task data to be cleaner and better organzied and avoid access to task data outside the standard path defined by the main task data access scripts. specifically in this task we want to introduce a mechanism that automatically split old.tar.gz in multiple files, on file for each hundred of tasks, that is old1.tar.gz for task from 0 to 99, old2.tar.gz for tasks from 100 to 199, and so on and rewrite all the logic for task accesss for this new format, also, instead of keeping all the old.tar.gz files in the archived directory we want to create subfolders: archived/t1 for files from old1 to old10 that is the first thousand of tasks, archived/t2 for old11..old20 that is the second thousands of tasks. we also need to update website documentation about this new format. this is a complex task that need to be split in child child tasks. also because it is basic infrastructure for the aitasks frameworks, and we want to continue work on other tasks while this is developed, we want to split the task so that we develop NEW VERSIONS, separate of current versions of the scirpt for task accesss and in the final sibling task when all the new infrastructure is ready we do the migration, that is we finally substitute the old scripts with the new ones and the task directory structure with the new structures and the old test files with the new one and clean up. ask me questions if youneed clarifications
