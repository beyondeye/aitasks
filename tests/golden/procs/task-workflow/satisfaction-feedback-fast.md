# Satisfaction Feedback Procedure


This procedure records skill usage for the current code agent/model. Profile 'fast' sets `enableFeedbackQuestions: false`, so there is no satisfaction question and no verified-score update — only Step 0 below runs. It is referenced from Step 9b (task-workflow) and standalone skills (aitask-explore, aitask-explain, aitask-changelog, aitask-docs-gap, aitask-wrap, aitask-refresh-code-models, aitask-reviewguide-classify, aitask-reviewguide-merge, aitask-reviewguide-import, aitask-web-merge).


**Input:**
- `skill_name` (string, required) — for example `pick`, `explore`, `explain`
- `detected_agent_string` (string, optional) — pre-resolved agent string from Agent Attribution (e.g., `claudecode/opus4_6`). If provided, skips self-detection.

**Procedure:**

## Step 0 — Record usage (unconditional)

Bumps `usagestats[skill]` for the current model/skill regardless of `enableFeedbackQuestions`. This is the only data path that records runs which never reach a rating — code agents that skip every interactive prompt after `ExitPlanMode` (e.g., Codex CLI), and profiles that disable feedback questions.

**Guard:** If `usage_collected` is `true`, skip Step 0. Otherwise set `usage_collected` to `true` **before** invoking the script (set-before-call so a mid-procedure failure does not cause a retry double-bump).

1. **Resolve agent string:** If `detected_agent_string` is non-null/non-empty, reuse it. Else execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) and store the result in `detected_agent_string` for downstream reuse.

   If detection fails or no supported agent/model can be identified, skip Step 0 silently.

2. **Invoke the usage update:**
   ```bash
   ./.aitask-scripts/aitask_usage_update.sh --agent-string "<detected_agent_string>" --skill "<skill_name>" --silent
   ```

   - On success (`UPDATED:<agent>/<model>:<skill>:<runs>` line, exit 0): continue. `<runs>` may be the literal `unknown` — the run **is** recorded, only its current total could not be read; that is still a success.
   - On `STATS_ERROR:<reason>` (non-zero exit): warn the user `usage not recorded: <reason>` and continue.
   - On any other failure: warn the user `usage update failed: <error>` and continue. Do NOT abort the workflow — usage tracking is best-effort.


## Step 1 — Satisfaction question (disabled by profile)

Profile 'fast' sets `enableFeedbackQuestions: false` — there is no satisfaction question and no verified-score update; the procedure ends after Step 0. Display: `Profile 'fast': feedback questions disabled`.

