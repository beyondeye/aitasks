---
Task: t303_1_verified_update_script_and_schema.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_2_*.md, aitasks/t303/t303_3_*.md, aitasks/t303/t303_4_*.md, aitasks/t303/t303_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_1 — Verified Update Script and Schema

## Steps

### 1. Create `aitask_verified_update.sh`

Script structure following `aitask_issue_import.sh` pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"

# Score mapping: 1→20, 2→40, 3→60, 4→80, 5→100
map_score() { echo $(( $1 * 20 )); }
```

Key functions:
- `parse_args()` — handle `--agent-string`, `--skill`, `--score`, `--silent`, `--help`
- `validate_agent_string()` — split on `/`, validate agent is one of claudecode/geminicli/codex/opencode
- `update_verified()` — jq pipeline to update verifiedstats and recalculate verified score
- `main()` — orchestrate

### 2. jq update logic

```bash
update_verified() {
    local json_file="aitasks/metadata/models_${AGENT}.json"
    local mapped_score
    mapped_score=$(map_score "$SCORE")

    local updated
    updated=$(jq --arg model "$MODEL" --arg skill "$SKILL" --argjson score "$mapped_score" '
        .models |= map(
            if .name == $model then
                .verifiedstats[$skill] = {
                    runs: ((.verifiedstats[$skill].runs // 0) + 1),
                    score_sum: ((.verifiedstats[$skill].score_sum // 0) + $score)
                }
                | .verified[$skill] = ((.verifiedstats[$skill].score_sum) / .verifiedstats[$skill].runs | round)
            else . end
        )
    ' "$json_file")

    echo "$updated" > "$json_file"
}
```

### 3. Add dispatcher entry

Add to `ait` after line ~153:
```bash
verified-update) shift; exec "$SCRIPTS_DIR/aitask_verified_update.sh" "$@" ;;
```

### 4. Create test script

`tests/test_verified_update.sh` — self-contained with temp dir setup, mock model JSON, assert_eq/assert_contains helpers.

## Verification

- `shellcheck .aitask-scripts/aitask_verified_update.sh`
- `bash tests/test_verified_update.sh`
- Manual: `./ait verified-update --agent-string claudecode/opus4_6 --skill pick --score 4`

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.
