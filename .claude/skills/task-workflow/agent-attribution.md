# Agent Attribution Procedure

This procedure records which code agent and LLM model is executing the task by setting the `implemented_with` field in the task's frontmatter. It is referenced from Step 7 (task-workflow), aitask-wrap (Step 4a), aitask-pickrem (Step 8), and aitask-pickweb (Step 6).

**When to execute:** At the start of implementation, after plan mode has been exited. This timing is critical because some code agents (e.g., Codex CLI) run initial workflow steps in plan mode, which is read-only and cannot write metadata.

**Procedure:**

1. Execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) to get `agent_string`.

2. **Write to frontmatter:**
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_num> --implemented-with "<agent_string>" --silent
   ```

3. **Store for reuse:** Set `detected_agent_string` to the resolved `agent_string` value. This allows downstream procedures (e.g., Satisfaction Feedback) to skip re-detection.

**Variant for aitask-pickweb:** Since pickweb does not call `aitask_update.sh` (no cross-branch operations), store the agent string in the completion marker JSON instead (add an `"implemented_with"` field). The `aitask-web-merge` skill will apply it during archival.
