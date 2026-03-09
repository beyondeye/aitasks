## Agent Identification

When recording `implemented_with` in task metadata, construct `opencode/<name>`.

1. Check `AITASK_AGENT_STRING` env var first — if set, use it directly.
2. If not set, identify your current model ID from your system context.
3. Match against `aitasks/metadata/models_opencode.json` (`cli_id` field)
   to find the corresponding `name`.
4. Construct as `opencode/<name>` (e.g., `opencode/gpt5_4`).
