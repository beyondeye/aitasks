# Model Self-Detection Sub-Procedure

This shared sub-procedure resolves the current code agent and model into an
agent string like `claudecode/opus4_6`. It is referenced by the Agent
Attribution Procedure (see `agent-attribution.md`) and the Satisfaction Feedback Procedure (see `satisfaction-feedback.md`).

**Input:** none (reads environment, agent runtime context, and model config files)

**Output:** `agent_string` in format `<agent>/<model>`

**Procedure:**

1. **Check `AITASK_AGENT_STRING` env var** — if set (by the codeagent wrapper), use its value directly as the agent string and return. This value is authoritative and should correspond to a real entry in `aitasks/metadata/models_<agent>.json`.

2. **If not set, self-detect:**
   - Identify which code agent CLI you are running in. The agent name MUST be one of these exact strings: `claudecode`, `codex`, `opencode`. **IMPORTANT:** Use `claudecode` (not `claude`). These are the only valid agent identifiers.
   - **Obtain your current model ID** using the agent-specific method:
     - **Claude Code:** Resolve the model ID, scanning for **mid-session `/model` switches before** falling back to the initial system message:
       - The system message's "exact model ID" is frozen at session start. A `/model` command does **not** update it, so using the system-message value after a switch records the wrong model.
       - Search the conversation for the most recent `<local-command-stdout>Set model to …</local-command-stdout>` line. If found, map the human-readable name (e.g., "Opus 4.7 (1M context)") to the cli_id via the resolve script below.
       - Only fall back to the system-message "exact model ID" (e.g., `claude-opus-4-6`) if no mid-session switch is visible.
       - **When you do fall back to the system-message exact ID, pass it verbatim.** The 1M-context Opus variant's exact ID carries a bracketed `[1m]` suffix (e.g. `claude-opus-4-7[1m]`); stripping it resolves to the non-1M entry (`claudecode/opus4_7` instead of `claudecode/opus4_7_1m`) and mis-attributes the model. See `aidocs/framework/model_reference_locations.md`.
       - If the human name is ambiguous (e.g., "Opus 4.7" without the `1M` suffix), ask the user which variant.
     - **Codex CLI:** Do NOT guess your model ID — Codex models cannot reliably self-identify from system context. Instead, run: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'` to read the configured model (e.g., `gpt-5.4`). This returns the startup/default model. **Limitation:** If the model was changed mid-session via `/model`, this gives the configured default, not the current runtime model.
     - **OpenCode:** Read the model ID from system context.
   - **Resolve via script:**
     ```bash
     ./.aitask-scripts/aitask_resolve_detected_agent.sh --agent <agent> --cli-id <model_id>
     ```
   - Parse the single-line output — the value after the colon is the agent string:
     - `AGENT_STRING:<value>` — exact match found, use `<value>` as agent string
     - `AGENT_STRING_FALLBACK:<value>` — no match found, `<value>` uses raw cli_id as fallback
