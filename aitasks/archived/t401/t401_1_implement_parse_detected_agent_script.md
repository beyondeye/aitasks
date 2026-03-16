---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-16 11:21
updated_at: 2026-03-16 11:58
completed_at: 2026-03-16 11:58
---

## Context

The model-self-detection procedure (`.claude/skills/task-workflow/model-self-detection.md`) currently instructs the LLM to manually parse `models_<agent>.json` files. Claude Code frequently writes custom jq/Python code that fails and retries, wasting tokens and time. The fix is a shell script that encapsulates the JSON lookup so the LLM just runs one command.

Parent task: `aitasks/t401_more_robust_self_detection_for_claude_code.md`

## Key Files to Modify

- **`.aitask-scripts/aitask_parse_detected_agent.sh`** (NEW) — Shell script accepting `--agent <name> --cli-id <model_id>`, looks up in `models_<agent>.json`, returns structured output
- **`.claude/skills/task-workflow/model-self-detection.md`** — Rewrite to use the script instead of manual JSON parsing
- **`.codex/instructions.md`** — Update "Agent Identification" section (lines 71-83)
- **`.opencode/instructions.md`** — Update "Agent Identification" section (lines 69-78)
- **`.gemini/skills/geminicli_tool_mapping.md`** — Update "Agent String" section (lines 43-51)
- **`.agents/skills/codex_tool_mapping.md`** — Update "Agent String" section (lines 48-56)
- **`.opencode/skills/opencode_tool_mapping.md`** — Update "Agent String" section (lines 51-58)
- **`seed/codex_instructions.seed.md`** — Update matching section
- **`seed/geminicli_instructions.seed.md`** — Update matching section
- **`seed/opencode_instructions.seed.md`** — Update matching section
- **`tests/test_parse_detected_agent.sh`** (NEW) — Test script
- **`CLAUDE.md`** — Add test to test list

## Reference Files for Patterns

- **`.aitask-scripts/aitask_codeagent.sh`** — Uses `SUPPORTED_AGENTS`, `METADATA_DIR`, `jq` lookup patterns. Follow its conventions for the new script.
- **`.aitask-scripts/aitask_query_files.sh`** — Structured output pattern (`KEY:value` format). Follow this pattern.
- **`tests/test_detect_env.sh`** — Test structure with `assert_eq`/`assert_contains` helpers
- **`aitasks/metadata/models_claudecode.json`** — JSON structure: `{ "models": [ { "name": "opus4_6", "cli_id": "claude-opus-4-6", ... } ] }`

## Implementation Plan

### Step 1: Create `.aitask-scripts/aitask_parse_detected_agent.sh`

Script interface: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent <agent> --cli-id <model_id>`

Logic:
1. Fast path: if `AITASK_AGENT_STRING` env var is set, output `AGENT_STRING:<value>` and exit
2. Validate `--agent` is one of: `claudecode`, `geminicli`, `codex`, `opencode`
3. Locate `aitasks/metadata/models_<agent>.json`
4. Use `jq` to find entry where `.cli_id == $cli_id`, extract `.name`
5. If found: output `AGENT_STRING:<agent>/<name>`
6. If not found AND agent is `opencode`: try suffix match (entries whose `cli_id` ends with `/<cli_id>`)
7. Fallback: output `AGENT_STRING_FALLBACK:<agent>/<raw_cli_id>`

Conventions: `#!/usr/bin/env bash`, `set -euo pipefail`, source `lib/terminal_compat.sh` + `lib/task_utils.sh`, use `METADATA_DIR="${TASK_DIR:-aitasks}/metadata"`

### Step 2: Rewrite `model-self-detection.md`

Replace manual JSON parsing with:
1. Check `AITASK_AGENT_STRING` env var — if set, use directly
2. If not set: identify agent name + model ID (agent-specific methods unchanged), then run: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent <agent> --cli-id <model_id>`, parse single-line output

### Step 3: Update 6 agent instruction files + 3 seed files

Replace "match against JSON, construct string" steps with:
```
3. Run: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent <agent> --cli-id <model_id>`
4. Parse the output line — the value after the colon is your agent string.
```

### Step 4: Create test + update CLAUDE.md

Test cases: env var fast path, exact match per agent, opencode suffix match, fallback, invalid agent, missing args, env var priority over args.

## Verification Steps

1. `bash tests/test_parse_detected_agent.sh` — all tests pass
2. `shellcheck .aitask-scripts/aitask_parse_detected_agent.sh` — no warnings
3. Manual: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent claudecode --cli-id claude-opus-4-6` → `AGENT_STRING:claudecode/opus4_6`
4. Manual fallback: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent claudecode --cli-id unknown` → `AGENT_STRING_FALLBACK:claudecode/unknown`
