## Agent Identification

When recording `implemented_with` in task metadata, construct `geminicli/<name>`.

1. Check `AITASK_AGENT_STRING` env var first — if set, use it directly.
2. If not set, identify your current model ID from your system context.
   Fallback: `jq -r '.model // empty' ~/.gemini/settings.json 2>/dev/null`
3. Match against `aitasks/metadata/models_geminicli.json` (`cli_id` field)
   to find the corresponding `name`.
4. Construct as `geminicli/<name>` (e.g., `geminicli/gemini2_5pro`).
