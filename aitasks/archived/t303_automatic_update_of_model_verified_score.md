---
priority: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [codeagent, ait_settings]
created_at: 2026-03-03 16:47
updated_at: 2026-03-11 08:51
completed_at: 2026-03-11 08:51
boardcol: now
boardidx: 30
---

each model supported by codeagent has metadata (see models_codex.json, models_geminicli.json, models_opencode.json, models_claudecode.json that for each aitask operation (currently actually only a few ops are listed) that tells if the models has been verified to work with some skill in satisfactory way. we should modify all skills to add a step that ask how satisfactory the skill worked (if we reach the end of the skill withour errors etc. and update a rolling average for the verified per project scores. this require changes to the current format of storing the verified data in models_<>.json in addition to the existing 0-100 scores, add a verifiedstats field where for each skill we store two numbers: number of runs and the sum of received scores (voting by users) then need a new bash script that will be called in the finalization phase of each skill after the user feedback about the satisfaction (if given) that update verifiedstats and recalculate verified scores (and commit changes to the aitask branch where metadata is stored) also we need the infromation about current code agent and llm model used, in aitask-pick and task-workflow we already integrated instruction on how to query the cli for this information (or use batch variable taht is defined by the ait codeagent script when invoking code agent see ait codeagent docs). so this information about current model should be refactor to a common skill that can be invoked by any skill that want to obtain this information, this is a complex task split it into multiple tasks
