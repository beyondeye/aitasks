---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitasks, bash, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 21:40
updated_at: 2026-02-11 22:06
---

crate a claude code skill to check the git commits from the last assigned version label (the last github release) up to current commits, craate the list of all tasks that were implemented, load of archived plans of implemented tasks and create a summary of the new features introduced in up to new and update CHANGELOG.md (ask for user what would be the next version number) and write the summary of changes with the new version label to the CHANGELOG.md file (newer version at the top of the files). the name of the new skill should aitask-changelong make sure that it is included in the tarbal created when a new release is created. integrate with create_new_release.sh, to check if there is a section in changelog for the new release and use it towrite the description for the new release when creating it
Note that task t91 can have its implementation connected to this task, that is once this task is implemented, implementation of t91 will be easier. we should update t91 to reference the implementation plan of this task, and perhaps add a dependency of t91 from this task
