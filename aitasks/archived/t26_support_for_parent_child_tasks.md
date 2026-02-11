---
priority: high
effort: high
depends: []
issue_type: feature
status: Done
labels: [scripting]
created_at: 2026-02-01 19:24
updated_at: 2026-02-01 19:24
---

This is a big features. I want to adapt the aitasks_create, aitasks_ls, aitasks_update, aitask_celar_old scripts to support tasks with child tasks. Also the the claude code skills defined in this project, aitask_cleanold and aitask-pick and aitask-create2 skills must be updated to support parent/child tasks. First of all what are parent/child tasks? need to add two properties to task metadata: parent and children. for example for a task t1_sometask.md that have 3 child taks t1_1_first_child, t1_2_second_child, t1_3_third_child, the parent task has a property children: [t1_1,t1_2,t1
aitasks_create.sh
aitasks_ls.sh
aitasks_update.sh
aitask_clear_old.sh

sorry correction the property in the parent task is called children_to_implement and it lists only the children tasks that still need to be implemented. all child tasks of the task t1_sometaks.md are stored in the subdirectory t1 that is stored in the same directory where the parent task file is stored. Child tasks know which is their parent task form their name. a parent tasks has autmoatically a dependency from all its child tasks, and cannot be completed until all its child tasks are completed. when a child tasks completed it is moved the archived/t1 (for parent task t1). When a csks when a child tasks is executed, a prompt is generated that include refeerence to sibling tasks and parent tasks. so that although we are working on a specific child task we have available in the context as indirect reference to parent and sibiling tasks file that store their status (completed or not)

So here tha main changes I see (but they are probably not all of them, please analyze the new architecture, and suggest if I am missing somthing) task creation: add option to select a parent task: if a parent task is selected then the path where the new (child) task will be written in the associated subdirectory of the parent task: task number for child task: the numbering of child task is done considering the existing childer t all tasks that is if chilren t1_1 and t1_2 exists, the next child task id is t1_3. Default dependency for child tasks: a child task t1_2 by default depends from task t1_1 (the previous child tasks). This default dependency can be removed.  aitask-pick: we pick choice is done only for parent tasks, but then if thetask is parent task there is  secondary pick that is the child task to execute, between the parent children that are ready to executed.

We need to make a separate plan for updating each of the current aitasks script and each of curent aitasks_ skills to support parent and child tasks. ask me questions and create a separate implementation plan for each script and each skill the order for impleemnting the changes is the following 1) aitasks_create 2) skill aitask_create 3) aitasks_update 4) aitasks_ls 5) skill aitask_pick 6) script aitask_clear 7) skill aitask_clear. Also I would like to modify the aitask_pick skill so that if during planning the complexity of the implementation is high suggest the option to create child tasks and then run aitask_pick and impleemnt each child separately

note that we can use the shell script aitasks_create in batch mode to create tasks and aitasks_update script to update tasks

note that when child tasks are archived they should be archived including the subdirectory the old.tar.gz file, that is the old.tar.gz should
contain a subdirectory for each parent tasks that contains the archived task description of the child asks
the same should be done for the aiplans: aiplans for a parent task plan p1_sometask.md should be stored in the
p1 subdirectory of the aiplans directory.
---
COMPLETED: 2026-02-01 23:50
