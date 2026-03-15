# Satisfaction Feedback Procedure

This procedure collects a quick user rating after a skill completes and updates
rolling verified scores for the current code agent/model. It is referenced from Step 9b (task-workflow) and standalone skills (aitask-explore, aitask-explain, aitask-changelog, aitask-wrap, aitask-refresh-code-models, aitask-reviewguide-classify, aitask-reviewguide-merge, aitask-reviewguide-import, aitask-web-merge).

**Input:** `skill_name` (string, for example `pick`, `explore`, `explain`)

**Guard:** If `feedback_collected` is `true`, skip this procedure entirely (feedback was already collected earlier in this workflow run). Otherwise, set `feedback_collected` to `true` before proceeding.

**Procedure:**

1. **Profile check:** If the active profile exists and `enableFeedbackQuestions` is set to `false`, skip this procedure entirely. Display: `Profile '<name>': feedback questions disabled`.

   **Default behavior:** If `enableFeedbackQuestions` is omitted, treat it as `true` and continue normally.

2. Execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) to get `agent_string`.
   - If detection fails or no supported agent/model can be identified, skip silently.

3. Use `AskUserQuestion`:
   - Question: `How well did this skill work? (Rate 1-5, helps improve model selection)`
   - Header: `Feedback`
   - Options:
     - `5 - Excellent` (description: `Completed perfectly, no issues`)
     - `4 - Good` (description: `Completed with minor issues`)
     - `3 - Acceptable` (description: `Completed but with notable issues`)
     - `1-2 - Poor` (description: `Significant problems or failures`)

   **Score mapping:** `5 -> 5`, `4 -> 4`, `3 -> 3`, `1-2 -> 2`

4. If the user selected a rating, update verified stats:
   ```bash
   ./.aitask-scripts/aitask_verified_update.sh --agent-string "<agent_string>" --skill "<skill_name>" --score <rating> --silent
   ```
   Parse the structured result:
   - `UPDATED:<agent>/<model>:<skill>:<new_score>` — Display: `Updated <skill> verified score for <agent>/<model>: <new_score>`

5. If the user skips or dismisses the question, continue without updating.
