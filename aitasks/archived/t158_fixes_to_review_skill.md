---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [aitask_review, claudeskills, scripting]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 17:05
updated_at: 2026-02-17 18:28
completed_at: 2026-02-17 18:28
---

the claude code skill aitask-review need some fine tuning: in step 1a: remove option entire codebase.

for the recent changes option in step 1 create a helper bash script that should be added to the white list in seed file claude_settings.local.json, that substitute the fetch and filter commits in paginated batches of 10 relevant commits.

make sure to remove from the skill all parts that refers to the "entire codebase" option 1b) for review guide selection for auto-detect project environment create a claude-code  white listed bash script (in aiscript) like it was requested in step 1a) that detect project environment and return it as list of possible environment ranked from most relevant to less relevant: the environment checking script should also check the list of files modified in the commits with were requested to review or the selected file/directories at the beginning of the script. the script that autodetect the environment should also parse the avaiable files in reviewguides and select the relevant files there. the reason to delegating logic to an external script is for speed and saving llm context for a task that can be automated. we can rely instead to the llm to structure the bash script in a modular way with independent multipletest whose results is summed up to give the final ranking to the probability of each environmentm, structure the script in way that will be easy to add new tests to check the enviroment both by the llm and manually. ask me question if you need clarifications
