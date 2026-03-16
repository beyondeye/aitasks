## Agent Identification

When recording `implemented_with` in task metadata, construct `codex/<name>`.

1. Check `AITASK_AGENT_STRING` env var first — if set, use it directly.
2. If not set, read your configured model:
   `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`
3. Run: `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent codex --cli-id <model_id>`
4. Parse the output — the value after the colon is your agent string.

**Do NOT guess your model ID from memory** — Codex models cannot reliably
self-identify. Always use the env var or config file method above.
