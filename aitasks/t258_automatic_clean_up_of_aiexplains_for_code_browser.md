---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codebrowser]
children_to_implement: [t258_2, t258_3, t258_4, t258_5]
created_at: 2026-02-26 12:19
updated_at: 2026-02-26 15:27
boardidx: 20
---

currently codebrowser does not do a good job at cleaining up old aitexplain_extract runs. I can see for the same source directories multiple runs data in aiexplains/codebrowser (for example /home/ddt/Work/aitasks/aiexplains/codebrowser/aiscripts__20260226_100306 and similar directory with different date) I think that there a mechanism, when we trigger refresh in the codebrowser tui that delete the previous run after the refresh, but still there is stale data that is left behind. I think there is place for a general bash script that clear up stale directory, when multiple directory assoicated to the same source directory are found with same file list inside (files.txt) or even without this check, perhaps, if the run is newer? this new scirpt could benefit also runs data created with the aitask-explain skill, we must simply change the convention used to name run directories to use the same convention used in codebrowser so that we can identify runs associated to the same directory. we can call this script for removing stale directory at the beginning of the explain skills, and in the codebrowser tui perhaps at tui startup. this is a complex task, that require writing the new bash scripts, and integrating it in codebrowser tui and in aitask-explain skill and also changing the convention used to name explain runs, this possibly also  involve chnages in the existing aitask_explain_runs.sh script. if a new bash script is created it should be also added to the whitelisted list of scripts in seeds/claude_settings.local.json
