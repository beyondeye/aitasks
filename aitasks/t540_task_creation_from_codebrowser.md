---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codebrowser, aitask-create]
children_to_implement: [t540_5, t540_7]
created_at: 2026-04-14 09:26
updated_at: 2026-04-15 11:30
boardidx: 30
---

currently aitask-create bash script has the option to add references to files, but sometimes it is easier for a developer the other way around: that is identify a file in the ait codebrowser tui, select a line range and create an aitask that already have in its context the file and the affected line-range. also it would be useful, when creating aitask this way, to check if there are already specific tasks associated with that specific file and merge them automatically (with user approval confirmation) so that we can run this as a single task, when we aitask-pick with a codeagent. this is a feature that should be integrated with the codebrowser tui and adaptation to the aitask-create bash script aitask-update script. I am not sure if this new workflow should be implemented fully in codebrowser using aitask-create and aitask-update scripts in batch mode. still aitask-craate has feature like defining task dependencies, priorities, and labels that look like waste to mirrow in codebrowser tui. and additional feature that is related but more general that it would be usefult to add to aitask-create script when it runs in interactive mode is that in the phase where we choose the labels for a task, propose to add the labels uses from the previous created task (for this user: this is a local setting), that is add an addtional option in the label chooser, in addition to create new: use labels from previous task. if the option is selected then continue with the label adding flow as usual, just remove the option to add labels from previous task since we already added them. this is a complex task that must be split in child tasks. ask me questions if you need clarifications
