---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_board, task-archive]
children_to_implement: [t448_2, t448_3, t448_4, t448_5, t448_6]
created_at: 2026-03-23 23:48
updated_at: 2026-03-24 10:16
---

it can be useful to have a place where to view all completeed tasks, even the archived+zipped ones. I am not sure if the best place to view them is in the ait board or somewhere else. Having a separate tui for this specific purpose could also be an option. the advantage of ait board tui that it already have all the widgets needed for visualizing a task/associated plans and depdendencies. but this widgets should be refactored anyway because we want the capability to show task information for example in the brainstorm tui. anyway probably the codebrowser is the place where having the history of completed tasks make most sense. we can add a new view that show list of completed tasks in reversed chronological order, a two pane screen (in some way analogous to the two panes we currently have in the codebrowser, with file tree to the left and file content on the right. in a similar way we will have the list of completed tasks on the left: when a task is selected, we show on the right pane the task description/labels etc, similar tot he task detail view in the ait board. but in addition we show: link to associated commit (for each child if this is  a parent task with children) and list of affected files, with the options of chooosing one of the affected files that if selected will open in the current codebrowser view (that is we go back to the regular codebrower view). this is a complex task that need to be split in child tasks. also we need to document the new features of the codebrowsser in the website doc for it and probably dding some more images. also the link to the commit asscoiated to the task should be "clickable" or when selected and pressing enter it should launch the browser with the approriate github/gitlab/bitbucket page for the commit. ask me question if you need clarifications
