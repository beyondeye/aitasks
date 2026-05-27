# Model Self-Detection Sub-Procedure

This shared sub-procedure resolves the current code agent and model into an
agent string like `claudecode/opus4_6`. It is referenced by the Agent
Attribution Procedure (see `agent-attribution.md`) and the Satisfaction Feedback Procedure (see `satisfaction-feedback.md`).

**Input:** none (reads environment, agent runtime context, and model config files)

**Output:** `agent_string` in format `<agent>/<model>`

**Procedure:**

1. **Check `AITASK_AGENT_STRING` env var** — if set (by the codeagent wrapper), use its value directly as the agent string and return. This value is authoritative and should correspond to a real entry in `aitasks/metadata/models_<agent>.json`.

2. **If not set, self-detect:**
   - Identify which code agent CLI you are running in. The agent name MUST be one of these exact strings: `claudecode`, `geminicli`, `codex`, `opencode`. **IMPORTANT:** Use `claudecode` (not `claude`), `geminicli` (not `gemini`). These are the only valid agent identifiers.
   - **Obtain your current model ID** using the agent-specific method:
     - **Claude Code:** Read the "exact model ID" from the system message (e.g., `claude-opus-4-6`).
     - **Codex CLI:** Do NOT guess your model ID — Codex models cannot reliably self-identify from system context. Instead, run: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'` to read the configured model (e.g., `gpt-5.4`). This returns the startup/default model. **Limitation:** If the model was changed mid-session via `/model`, this gives the configured default, not the current runtime model.
     - **Gemini CLI:** Read the model ID from system context, or run: `jq -r '.model // empty' ~/.gemini/settings.json 2>/dev/null` as fallback.
     - **OpenCode:** Read the model ID from system context.
   - **Resolve via script:**
     ```bash
     ./.aitask-scripts/aitask_resolve_detected_agent.sh --agent <agent> --cli-id <model_id>
     ```
   - Parse the single-line output — the value after the colon is the agent string:
     - `AGENT_STRING:<value>` — exact match found, use `<value>` as agent string
     - `AGENT_STRING_FALLBACK:<value>` — no match found, `<value>` uses raw cli_id as fallback
