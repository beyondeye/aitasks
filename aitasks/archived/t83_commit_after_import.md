---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 21:44
updated_at: 2026-02-10 21:53
completed_at: 2026-02-10 21:53
---

in aitask_import bash script we create a new task from a github issue. currently the script misses the step of adding the new created task to git and committing the change. this is done at the end of aitask_create in interactive mode. the smae must be done for aitask_import when running in interactive mode. also there should be an option (if not already present) to optionally add the new task and commit to git when running in batch mode both in aitask_create shell script and in aitask_import shell script. need also to update the help text acoordining for both aitask_import and aitask_create. the same option to allow to commit changes to git should be added to aitask_update script, use the same option name for all the three scripts.
