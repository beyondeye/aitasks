---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitasks, bash]
children_to_implement: [t144_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 09:52
updated_at: 2026-02-17 10:48
---

the current implementation of ait clear_old that is the aitask_clear_old.sh script, is no more relevant. the idea was move all archived aiplans and aitasks to an old.tar.gz files and just leave the last one so that the logic for assigning a new task number will not break. now we have completely changed the logic to assign new task number in an atomic way so we don't have any such constraint of keeping the last aitask anymore. on the other hand we have a problem that currently the aitask_clear_old script does not check for archived tasks that al children of parents tasks still in the works or tasks that are related (unlocked) tasks that still need to be implemented, in other words we don't currently check if the archived tasks that needs to be moved in the tar file, are still relevant for current work (it is possible that I missed some other cases). so there is need to rewrite the logic used to select the tasks to move to the old.tar.gz. also need to be sure that even if moved in old.tar.gz the files are still accessible to the aitask_changelog.sh that is used to create changelogs update in CHANGELOG.md and it is used in the aitasks_release process. finally the script name aitask_clear_old is not clear enough better rename it aitask_zip_old. need to update accordingly the ait dispatcher script, and the shell scripts documentation in the docs directory. it is probably best to split this task in child tasks
