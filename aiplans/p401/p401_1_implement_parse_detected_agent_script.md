---
Task: t401_1_implement_parse_detected_agent_script.md
Parent Task: aitasks/t401_more_robust_self_detection_for_claude_code.md
Sibling Tasks: aitasks/t401/t401_2_*.md, aitasks/t401/t401_3_*.md, aitasks/t401/t401_4_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: aitask_parse_detected_agent.sh

## Step 1: Create `.aitask-scripts/aitask_parse_detected_agent.sh`

New shell script with this interface:
```
./.aitask-scripts/aitask_parse_detected_agent.sh --agent <agent> --cli-id <model_id>
```

**Logic flow:**
1. Check `AITASK_AGENT_STRING` env var — if set, output `AGENT_STRING:<value>`, exit 0
2. Parse `--agent` and `--cli-id` arguments
3. Validate agent is in `SUPPORTED_AGENTS=(claudecode geminicli codex opencode)`
4. Locate `$METADATA_DIR/models_${agent}.json`; if missing, go to fallback
5. Use `jq -r --arg id "$cli_id" '.models[] | select(.cli_id == $id) | .name' "$models_file"` for exact match
6. If found: output `AGENT_STRING:<agent>/<name>`, exit 0
7. If not found AND agent is `opencode`: try suffix match — `jq -r --arg id "$cli_id" '.models[] | select(.cli_id | endswith("/" + $id)) | .name' "$models_file" | head -1`
8. If suffix found: output `AGENT_STRING:<agent>/<name>`, exit 0
9. Fallback: output `AGENT_STRING_FALLBACK:<agent>/<cli_id>`, exit 0

**Conventions:** Follow `aitask_codeagent.sh` patterns: `#!/usr/bin/env bash`, `set -euo pipefail`, source libs, `METADATA_DIR="${TASK_DIR:-aitasks}/metadata"`

## Step 2: Rewrite `.claude/skills/task-workflow/model-self-detection.md`

Simplify the procedure to:
1. Check `AITASK_AGENT_STRING` env var (unchanged)
2. Identify agent name and model ID (agent-specific methods unchanged)
3. Run the script, parse single-line output

Remove all manual JSON parsing instructions.

## Step 3: Update agent instruction files

**Files (9 total):**
- `.codex/instructions.md` — "Agent Identification" section: replace steps 3-4
- `.opencode/instructions.md` — "Agent Identification" section: replace steps 3-4
- `.gemini/skills/geminicli_tool_mapping.md` — "Agent String" section: replace steps 3-4
- `.agents/skills/codex_tool_mapping.md` — "Agent String" section: replace steps 3-4
- `.opencode/skills/opencode_tool_mapping.md` — "Agent String" section: replace steps 3-4
- `seed/codex_instructions.seed.md` — matching section
- `seed/geminicli_instructions.seed.md` — matching section
- `seed/opencode_instructions.seed.md` — matching section

Each file: replace "Match against models JSON, construct string" with:
```
3. Run: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent <agent> --cli-id <model_id>`
4. Parse the output — the value after the colon is your agent string.
```

## Step 4: Create `tests/test_parse_detected_agent.sh`

Test cases using `assert_eq`/`assert_contains` helpers:
1. Env var fast path
2. Exact match claudecode (`claude-opus-4-6` → `opus4_6`)
3. Exact match for other agents (use real entries from models JSON files)
4. OpenCode suffix match
5. Fallback for unknown cli_id
6. Invalid agent → error
7. Missing args → error
8. Env var overrides args

## Step 5: Update `CLAUDE.md`

Add `bash tests/test_parse_detected_agent.sh` to the test list.

## Verification

1. `bash tests/test_parse_detected_agent.sh` — all PASS
2. `shellcheck .aitask-scripts/aitask_parse_detected_agent.sh` — clean
3. Manual test with real models

## Step 9: Post-Implementation

Archive child task and plan per standard workflow.
