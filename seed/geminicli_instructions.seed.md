## Agent Identification

When recording `implemented_with` in task metadata, construct `geminicli/<name>`.

1. Check `AITASK_AGENT_STRING` env var first — if set, use it directly.
2. If not set, identify your current model ID from your system context.
   Fallback: `jq -r '.model // empty' ~/.gemini/settings.json 2>/dev/null`
3. Run: `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent geminicli --cli-id <model_id>`
4. Parse the output — the value after the colon is your agent string.
