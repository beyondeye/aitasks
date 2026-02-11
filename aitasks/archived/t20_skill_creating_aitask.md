there is already a skill of handling aitask selection (see pick-aitask skill) but it can be useful
to have a skill for creation of an aitask, it will help to save time.
## the new aitask-create skill
the skill should 
1) check in the list of filenames of archived tasks to automatically
define the task number for the new task (the last found archived task+1)
2) use the AskUserQuestion to input from the user the
priority, effort and depedencies of the new task: allow the users to choose the dependency only from 
existing aitasks numbers 
3) ask for the name of the task, and automatically sanitize the name, substituting spaces with underscores etc.
4) ask the user to enter the task definition
and when done (ask the user when he is done with AskUserQuestion tool, every time the user press enter add the new chunk of text to the task file)
when user is done, commit the file to git. 

5) The skill should be named aitask-create,

## Changes to existing skill pick-aitask
1) rename the skill pick-aitask to aitask-pick
2)  if the skill is given a single number argument it assume it is the selected task, and skip the steps for task selection
and go on with the steps after task selection in the skill definition.

## new skill aitask-cleanold
I would like to add a new skill called aitask-cleanold that will move all aitasks in aitasks/archived director and aiplans/archived
and add them to aitasks/archived/old.tar.gz and aiplans/archived/old.tar.gz respectively. ALL except the LAST ONE (the archived tasks with highest task number: keeping this
is needed so that the logic for creating a new aitask in aitask-create will not break).
Note that you should add the files to the existing archive
if the archive file already exists, don't overwrite it. the motivation for writing this skill is because I don't want to have the old tasks text pollute the
project directory, and make grep for strings in the repository harder. the aitask-cleanold, after zipping archived
files should delete original archived files and commit changes (deleted files and updated archives)

Make a plan for implementation. ask me questions if you need clarifications.

---
COMPLETED: 2026-01-29 22:45