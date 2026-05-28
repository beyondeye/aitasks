---
priority: medium
effort: low
depends: [t835_1]
issue_type: test
status: Ready
labels: [task_workflow]
created_at: 2026-05-28 08:41
updated_at: 2026-05-28 08:41
---

## Context

Migrated from t401_3 (geminicli-era, archived). t401_1 established
`.aitask-scripts/aitask_parse_detected_agent.sh` as the canonical
agent parser. This task verifies the procedure works end-to-end when
running from agy (Antigravity CLI), replacing the geminicli-targeted
verification.

## Verification Steps

1. Launch agy in this repository.
2. Run a workflow that triggers model-self-detection (e.g.,
   `/aitask-pick` on a test task, or manually invoke the Agent
   Attribution Procedure).
3. Confirm the script is called correctly:
   `./.aitask-scripts/aitask_parse_detected_agent.sh --agent agy --cli-id <model_id>`
4. Verify the output is a valid `AGENT_STRING:agy/<name>` matching
   an entry in `aitasks/metadata/models_agy.json`.
5. Check that `implemented_with` is written correctly to the task
   frontmatter.

## Key Files (anticipated)

- `.aitask-scripts/aitask_parse_detected_agent.sh` — script being
  verified for the agy code path.
- `.agents/skills/...` or agy-specific skill surface — Agent String
  section may need updating.
- `aitasks/metadata/models_agy.json` — agy models registry.

## Special Considerations

agy identifies its model differently from geminicli (see sibling
task `identifying_model_id_in_agy`, t835_1). This verification
assumes that sibling has landed first; if not, escalate to its
planner.
