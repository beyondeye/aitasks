# Satisfaction Feedback Procedure

This procedure collects a quick user rating after a skill completes and updates
rolling verified scores for the current code agent/model. It is referenced from Step 9b (task-workflow) and standalone skills (aitask-explore, aitask-explain, aitask-changelog, aitask-wrap, aitask-refresh-code-models, aitask-reviewguide-classify, aitask-reviewguide-merge, aitask-reviewguide-import, aitask-web-merge).

**Input:**
- `skill_name` (string, required) — for example `pick`, `explore`, `explain`
- `detected_agent_string` (string, optional) — pre-resolved agent string from Agent Attribution (e.g., `claudecode/opus4_6`). If provided, skips self-detection.

**Procedure:**

## Step 0 — Record usage (unconditional)

Bumps `usagestats[skill]` for the current model/skill regardless of `enableFeedbackQuestions`. This is the only data path that captures runs by code agents (e.g., Codex CLI) that skip every `AskUserQuestion` after `ExitPlanMode` and therefore never reach the score prompt below.

**Guard:** If `usage_collected` is `true`, skip Step 0. Otherwise set `usage_collected` to `true` **before** invoking the script (set-before-call so a mid-procedure failure does not cause a retry double-bump).

1. **Resolve agent string:** If `detected_agent_string` is non-null/non-empty, reuse it. Else execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) and store the result in `detected_agent_string` for downstream reuse.

   If detection fails or no supported agent/model can be identified, skip Step 0 silently.

2. **Invoke the usage update:**
   ```bash
   ./.aitask-scripts/aitask_usage_update.sh --agent-string "<detected_agent_string>" --skill "<skill_name>" --silent
   ```

   - On success (`UPDATED:<agent>/<model>:<skill>:<runs>` line): continue.
   - On failure: warn the user `usage update failed: <error>` and continue. Do NOT abort the workflow — usage tracking is best-effort.

## Step 1 — Satisfaction question and verified-score update

**Guard:** If `feedback_collected` is `true`, skip the remainder of Step 1 (substeps 1-5 below) — feedback was already collected earlier in this workflow run. Otherwise, set `feedback_collected` to `true` before proceeding.

1. **Profile check:** If the active profile exists and `enableFeedbackQuestions` is set to `false`, skip the remainder of Step 1. Display: `Profile '<name>': feedback questions disabled`.

   **Default behavior:** If `enableFeedbackQuestions` is omitted, treat it as `true` and continue normally.

2. **Identify yourself:**

   **Fast path:** If `detected_agent_string` is available (non-null, non-empty), use it directly — skip the self-detection below and proceed to step 3.

   **Self-detection fallback** (when `detected_agent_string` is not available):
   - Determine which code agent you are running in. Use one of: `claudecode`, `geminicli`, `codex`, `opencode`. **IMPORTANT:** Use `claudecode` (not `claude`), `geminicli` (not `gemini`).
   - Obtain your current model ID:
     - **Claude Code:** Read the "exact model ID" from the system message (e.g., `claude-opus-4-6`).
     - **Codex CLI:** Run: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`
     - **Gemini CLI:** Read the model ID from system context, or run: `jq -r '.model // empty' ~/.gemini/settings.json 2>/dev/null`
     - **OpenCode:** Read the model ID from system context.
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

   **If using `detected_agent_string` (fast path):**
   ```bash
   ./.aitask-scripts/aitask_verified_update.sh --agent-string "<detected_agent_string>" --skill "<skill_name>" --score <rating> --silent
   ```

   **If using self-detection fallback:**
   ```bash
   ./.aitask-scripts/aitask_verified_update.sh --agent "<agent>" --cli-id "<model_id>" --skill "<skill_name>" --score <rating> --silent
   ```
   The script resolves the agent string internally — no need to call `aitask_resolve_detected_agent.sh` separately.

   Parse the structured result:
   - `UPDATED:<agent>/<model>:<skill>:<new_score>` — Display: `Updated <skill> verified score for <agent>/<model>: <new_score>`

5. If the user skips or dismisses the question, continue without updating.
