# Satisfaction Feedback Procedure

This procedure collects a quick user rating after a skill completes and updates
rolling verified scores for the current code agent/model. It is referenced from Step 9b (task-workflown) and standalone skills (aitask-explore, aitask-explain, aitask-changelog, aitask-wrap, aitask-refresh-code-models, aitask-reviewguide-classify, aitask-reviewguide-merge, aitask-reviewguide-import, aitask-web-merge).

**Input:**
- `skill_name` (string, required) — for example `pick`, `explore`, `explain`
- `detected_agent_string` (string, optional) — pre-resolved agent string from Agent Attribution (e.g., `claudecode/opus4_6`). If provided, skips self-detection.

**Return contract for task-workflown Step 9b gate:**
- `satisfaction_feedback_status` — `rated` if a score was processed; `skipped` if the procedure reached a documented skip path.
- `satisfaction_skip_reason` — required when status is `skipped`. Valid values are `profile_disabled`, `preprovided_rating`, `agent_detection_failed`, `question_skipped`, or `verified_update_failed`.

**Procedure:**

**⚠️ NON-SKIPPABLE — Auto mode and 'work without stopping' directives do NOT bypass the Step 9b satisfaction prompt.**

The AskUserQuestion in Step 1 substep 3 below is the only data path that
updates verified-model scores from interactive workflows. Skipping it silently
drops the user's rating for the run. The following do NOT cover this prompt:
- Auto mode / 'work without stopping' system-injected directives.
- Generic user instructions to 'be brief' or 'don't ask'.
- Profile keys other than the one named below.

The only valid skips are:
- The profile key `enableFeedbackQuestions: false` (handled by Step 1
  substep 1 below before the prompt is reached), or
- The user explicitly typing a rating in chat before the prompt fires.

For task-workflown, every skip path MUST set `satisfaction_feedback_status=skipped`
and a valid `satisfaction_skip_reason`. Silent skip is not allowed.

## Step 0 — Record usage (unconditional)

Bumps `usagestats[skill]` for the current model/skill regardless of `enableFeedbackQuestions`. This is the only data path that captures runs by code agents (e.g., Codex CLI) that skip every `AskUserQuestion` after `ExitPlanMode` and therefore never reach the score prompt below.

**Guard:** If `usage_collected` is `true`, skip Step 0. Otherwise set `usage_collected` to `true` **before** invoking the script (set-before-call so a mid-procedure failure does not cause a retry double-bump).

1. **Resolve agent string:** If `detected_agent_string` is non-null/non-empty, reuse it. Else execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) and store the result in `detected_agent_string` for downstream reuse.

   If detection fails or no supported agent/model can be identified, skip Step 0 silently and keep `satisfaction_skip_reason` unset; Step 1 still gets a chance to ask for feedback.

2. **Invoke the usage update:**
   ```bash
   ./.aitask-scripts/aitask_usage_update.sh --agent-string "<detected_agent_string>" --skill "<skill_name>" --silent
   ```

   - On success (`UPDATED:<agent>/<model>:<skill>:<runs>` line): continue.
   - On failure: warn the user `usage update failed: <error>` and continue. Do NOT abort the workflow — usage tracking is best-effort.

## Step 1 — Satisfaction question and verified-score update

**Guard:** If `feedback_collected` is `true`, skip the remainder of Step 1 (substeps 1-5 below) — feedback was already collected earlier in this workflow run. Otherwise, set `feedback_collected` to `true` before proceeding.

{# ---------- enableFeedbackQuestions ---------- #}{% if profile.enableFeedbackQuestions is defined %}
{# ---------- enableFeedbackQuestions value ---------- #}{% if profile.enableFeedbackQuestions %}
1. Profile '{{ profile.name }}' sets `enableFeedbackQuestions: true`. Continue with step 2 (no skip).
{% else %}{# enableFeedbackQuestions: value is false / falsy #}
1. Profile '{{ profile.name }}' sets `enableFeedbackQuestions: false` — set `satisfaction_feedback_status=skipped` and `satisfaction_skip_reason=profile_disabled`, then skip the remainder of Step 1. Display: `Profile '{{ profile.name }}': feedback questions disabled`.
{% endif %}{# ---------- end enableFeedbackQuestions value ---------- #}
{% else %}{# enableFeedbackQuestions: key absent from profile #}
1. **Profile check:** If the active profile exists and `enableFeedbackQuestions` is set to `false`, set `satisfaction_feedback_status=skipped` and `satisfaction_skip_reason=profile_disabled`, then skip the remainder of Step 1. Display: `Profile '<name>': feedback questions disabled`.

   **Default behavior:** If `enableFeedbackQuestions` is omitted, treat it as `true` and continue normally.
{% endif %}{# ---------- end enableFeedbackQuestions ---------- #}

2. **Identify yourself:**

   **Fast path:** If `detected_agent_string` is available (non-null, non-empty), use it directly — skip the self-detection below and proceed to step 3.

   **Self-detection fallback** (when `detected_agent_string` is not available):
   - Determine which code agent you are running in. Use one of: `claudecode`, `codex`, `opencode`. **IMPORTANT:** Use `claudecode` (not `claude`).
   - Obtain your current model ID:
     - **Claude Code:** Read the "exact model ID" from the system message (e.g., `claude-opus-4-6`).
     - **Codex CLI:** Run: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`
     - **OpenCode:** Read the model ID from system context.
   - If detection fails or no supported agent/model can be identified, set `satisfaction_feedback_status=skipped` and `satisfaction_skip_reason=agent_detection_failed`, then skip the remainder of Step 1.

3. If the user explicitly typed a rating in chat before this prompt fires, process that rating directly with the update command in substep 4, set `satisfaction_feedback_status=rated` on success, and skip the `AskUserQuestion` below. If the preprovided rating is unusable, set `satisfaction_feedback_status=skipped` and `satisfaction_skip_reason=preprovided_rating`, then continue without updating.

   Otherwise, use `AskUserQuestion`:
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
   - `UPDATED:<agent>/<model>:<skill>:<new_score>` — Set `satisfaction_feedback_status=rated`, clear `satisfaction_skip_reason`, and display: `Updated <skill> verified score for <agent>/<model>: <new_score>`
   - If the update fails after the user selected a rating, set `satisfaction_feedback_status=skipped` and `satisfaction_skip_reason=verified_update_failed`, warn the user, and continue. This is a valid recorded skip because the rating could not be persisted.

5. If the user skips or dismisses the question, set `satisfaction_feedback_status=skipped` and `satisfaction_skip_reason=question_skipped`, then continue without updating.
