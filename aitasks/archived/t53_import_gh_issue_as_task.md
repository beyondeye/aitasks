---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [scripting, aitasks]
created_at: 2026-02-06 15:41
updated_at: 2026-02-10 22:46
completed_at: 2026-02-10 22:46
boardcol: next
boardidx: 20
---

Createa a bash script that given a github issue number for the current project, it uses the github comand line tool (gh) ti read the issue data and create from it a new task. give the option to add metadata like labels, dependencies priorirty end effort like a regular task create script. also need to add a new metatadata file ghissue with  the number of the issue (https://github.com/basecamp/omarchy/issues/<issuenumber> is the pattern for the url but we can use gh comand tool for parsiing data i thinkg. need to update aitask_update bash script to supprt the new metadata field. the new metadata field ghissue will break the aitask_update script because any unknown field will be ignored when writing back the update task in the aitask_update script
Note for reference this python script that is used for importing github issues in the beads (https://github.com/steveyegge/beads) task management cli: see the python script described in  https://github.com/steveyegge/beads/tree/main/examples/github-import,
source code at https://github.com/steveyegge/beads/blob/main/examples/github-import/gh2jsonl.py).  I don't want to use python nor the github api directly, I want to use 
the gh cli. The gh cli is fully capable for reading issue data and also for manipolating it. it can output json data that can be parsed with jq command line tool  if needed,
The new bash script should be called aitask_import, and it should have two modes 1) interactive mode if called without arguments 2) batch mode. Let me describe first the interactive mode. The command line arguments should be similar to the existing aitask_create.sh script when relevant.
Ok so lets describe interactive mode. when opening in interactive mode, the script will ask the user for 1) a specific issue number or 2) fetch issues and choose or 3) issue number range or 4) all issues . if fetch issue and choose is choosen, then fetch the list of open issue and use fzf based
input to fuzzy search the issue of interest. once the issue (or issues) of interest has been choosen, show a preview of the markdown text of issue to the issue for confirmation . then fetch the issue and createa new task (using a call to aitask_create script) using the fetched description 
and fetched issue labels (use for label metadata) note as part of the implementation of the aitask_import, there is a need to add a new metadata field in the task frontmatter (need to add support in aitask_update and in the aitask_board python script): in the aitask_update for handling it
and in the aitask_board for handling it , showing it in task detail and when the issue is selected add the action (in the aitask_board) to open the web page of the issue in a browser. in the matadata store the full url to the issue page. this is a complex task that should be spilt in 
child tasks. ask me questions if you need clarifications
