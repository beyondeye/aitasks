---
priority: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [codeagent, ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: opencode/zen_gpt_5_4
created_at: 2026-03-08 11:09
updated_at: 2026-03-10 19:06
completed_at: 2026-03-10 19:06
---

## Context

This is child task 1 of t303 (Automatic update of model verified scores). It creates the foundational script and JSON schema changes needed for automatic verification score collection.

Currently, model verification scores in `aitasks/metadata/models_<agent>.json` are manually set and never updated. This task adds a `verifiedstats` field that tracks rolling statistics (run count + score sum), and a script to update it.

## Key Files to Create

- `.aitask-scripts/aitask_verified_update.sh` (~200-300 lines)
- `tests/test_verified_update.sh` (~150 lines)

## Key Files to Modify

- `ait` — add `verified-update)` dispatcher entry

## Reference Files for Patterns

- `.aitask-scripts/aitask_codeagent.sh` — agent string parsing (`parse_agent_string()`), model lookup (`get_cli_model_id()`)
- `.aitask-scripts/aitask_opencode_models.sh` — jq JSON manipulation patterns for model files
- `aitasks/metadata/models_claudecode.json` — current JSON schema to extend
- `tests/test_claim_id.sh` — test structure pattern

## Implementation Plan

### New JSON Schema

Add `verifiedstats` field alongside existing `verified`:

```json
{
  "name": "opus4_6",
  "cli_id": "claude-opus-4-6",
  "notes": "...",
  "verified": { "task-pick": 80, "explain": 80, "batch-review": 0, "pick": 80 },
  "verifiedstats": {
    "pick": { "runs": 5, "score_sum": 400 }
  }
}
```

Existing `verified` keys (task-pick, explain, batch-review) are preserved for backward compatibility. New skill-based keys are added alongside them.

### Script: `aitask_verified_update.sh`

**Arguments:**
- `--agent-string <agent/model>` — e.g., `claudecode/opus4_6` (required)
- `--skill <skill-name>` — e.g., `pick`, `explore`, `explain` (required)
- `--score <1-5>` — user satisfaction rating (required)
- `--silent` — output only structured result
- `--help` — show usage

**Score mapping:** 1→20, 2→40, 3→60, 4→80, 5→100

**Algorithm:**
1. Parse agent string → extract agent name and model name
2. Read `aitasks/metadata/models_<agent>.json`
3. Find model entry by name
4. Get current `verifiedstats.<skill>` (default: `{ "runs": 0, "score_sum": 0 }`)
5. Increment: `runs += 1`, `score_sum += mapped_score`
6. Calculate new verified score: `verified.<skill> = round(score_sum / runs)`
7. Write back JSON with `jq`
8. Commit via `./ait git add` + `./ait git commit -m "ait: Update verified score for <agent>/<model> <skill>"`
9. Output: `UPDATED:<agent>/<model>:<skill>:<new_score>`

**Error handling:**
- Invalid agent string → die with error
- Model not found in JSON → die with error
- Score not 1-5 → die with error
- JSON file not found → die with error

### Test: `tests/test_verified_update.sh`

Test cases:
1. Valid update: score 4 → verify verifiedstats.runs=1, score_sum=80, verified.pick=80
2. Rolling average: two updates (4, 5) → verify average=(80+100)/2=90
3. Invalid agent string → error
4. Invalid score (0, 6) → error
5. Missing model → error
6. `--help` exits 0
7. Preserves existing verified keys (task-pick, explain, batch-review)

### Dispatcher Entry

Add to `ait` at line ~153:
```bash
verified-update) shift; exec "$SCRIPTS_DIR/aitask_verified_update.sh" "$@" ;;
```

## Verification Steps

- `shellcheck .aitask-scripts/aitask_verified_update.sh` passes
- `bash tests/test_verified_update.sh` — all tests pass
- Manual test: `./ait verified-update --agent-string claudecode/opus4_6 --skill pick --score 4`
- Verify `models_claudecode.json` has updated verifiedstats and recalculated verified score
