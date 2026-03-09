## Agent Identification

When recording `implemented_with` in task metadata, construct `codex/<name>`.

1. Check `AITASK_AGENT_STRING` env var first — if set, use it directly.
2. If not set, read your configured model:
   `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`
3. Match the result against `aitasks/metadata/models_codex.json` (`cli_id` field)
   to find the corresponding `name` (e.g., `gpt-5.4` → `gpt5_4`).
4. Construct as `codex/<name>` (e.g., `codex/gpt5_4`).

**Do NOT guess your model ID from memory** — Codex models cannot reliably
self-identify. Always use the env var or config file method above.
