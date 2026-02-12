---
priority: medium
effort: medium
depends: [t85_10, t85_9]
issue_type: feature
status: Done
labels: [install_scripts, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 12:21
updated_at: 2026-02-12 15:38
completed_at: 2026-02-12 15:38
---

currently we have a script for installing aitasks in a project, but no script to update an existing installation. with a new version. first need to update ait.sh shell to periodically check for new available versions, store in aiscripts in some file the last time the check for updates available was done. don't check more than once in day. if an update is available then suggest to the user to update, showing the command to run to update (ait install latest, or specific version number).  when the install script is run it show changelog for the version installed versus the current version and ask confirm from the user. This is the basic way to updating the current version of aitasks. A more advanced way to update aitasks should be a claude skill that try to merge local changes made to skills/scripts to the definitions pulled from the aitasks officially repo. but this is a much more complex tasks that should left for later. the motivation for this install update with merge is that the design philosophy of aitasks is to have the source code in the user repo so that the user can customize the workflow for its uses. this makes updating scripts and skill muce more complicated need to define a strategy to allow this feature, at least for claude skills. a possibility is browse the git history of commit in order to identify the user changes to skills and scripts (user customization) vs the original code. perhaps the best would to create a claude code skill that is responsible to analize this changes and interactively ask user question to create a merge plan and write it to an aitasks that include both pulling new source of new official aitasks version and merging with current code with proper tests to verify that everyting works after the. definitely a complex skill to design. but it could be very useful to make external contributions to aitasks easier. need to think about this better
