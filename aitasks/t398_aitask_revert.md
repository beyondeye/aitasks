---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_revert]
children_to_implement: [t398_1, t398_2, t398_3]
folded_tasks: [38]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-16 09:02
updated_at: 2026-03-16 10:39
boardcol: now
boardidx: 10
---

While experimenting with new features with ai development it can happen that we add features that later we find of limited used, and for avoiding bloat and unneeded complexity we want to revert the changes associated to some specific set of tasks. This is an enhancment of task t38 that was never implemented. There are several possible use cases and ways on how to implement this feature. We don't consider the just reverting git commits, this can be done manually. One possibility is that we want to revert the changes associated to some specific aitask. and eventyally of related aitasks. so the flow for the skill should look like this: if the user call the aitask_undo skill without a task number, the skill fetch latest commits, and create a list of the latest implemented tasks. alternatively the skill can ask for an area in the code and interactively drill down to specific files (in similar way as this is done in the aitask_contribute skill), we should consider if to extract a common procedure for code drill down, common to aitask_contribute, aitask_undo, aitask_explore.) once we selecte a select of files or directory we can use git, or the aitask-explain infrastructure (see task t369) to extract the relevant iatasks associated to latest changes in those files.

Now that we have aitask number we want to revert. we need to ask the user the type of revert he wants. Teo types of possible revert. 1) Completelly revert the aitask changes and then ask if delete aitasks or not delete it but keep it archived, or move it back to not implemented (not archived) state (obviosly do the same for the associated aiplan  2) Partially revert.  we need to analyze the code changes the components and areas that the change affected, and ask the user which areas want to revert and which not, use also information of child tasks decomposition for this, but allow more granual choice of areas to keep/revert. allow user to choose between areas with askuserquestion checboxes, or a free text answer. ask again confirmation after user choice or he wants to change something in the selection.

Once the areas that need to be reverted/kept are choosen, create an aitask for the rquired task reverts and then enter in plan mode to design the changes needed to reverrt the choosen areas, in other words proceed to the normal aitask workflow, similar to what happens in the aitask-explore where we switch from exploration to task implementation, give also the user the choice to implement the revert now, or keep it to later.

note that in the revert aitask that is build we must also include steps (according to user choide) to 1) keep the reverted task archived or 2) move it back to not implemented, and in this case add to it notes about which part were kept and which were reverted with reference to the revert task number

after implementaiton of the aitask_undo skill (or perhaps better call it aitask_revert, it is more clear the purpose), after implementation create the associated webpage doc page for the skill and also a new Revert Changes with AI workflow that document use cases and workflow steps.

This is a very complex task that must be decomposed in child tasks
