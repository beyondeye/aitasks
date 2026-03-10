---
Task: t303_1_verified_update_script_and_schema.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_2_*.md, aitasks/t303/t303_3_*.md, aitasks/t303/t303_4_*.md, aitasks/t303/t303_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_1 — Verified Update Script and Schema

## Planned Files

- `.aitask-scripts/aitask_verified_update.sh` — new internal helper script used by later procedures/skills
- `aitasks/metadata/models_claudecode.json` — initialize `verifiedstats` for existing models
- `aitasks/metadata/models_codex.json` — initialize `verifiedstats` for existing models
- `aitasks/metadata/models_geminicli.json` — initialize `verifiedstats` for existing models
- `aitasks/metadata/models_opencode.json` — initialize `verifiedstats` for existing models
- `tests/test_verified_update.sh` — regression coverage for update logic and error handling

## Steps

### 1. Create `.aitask-scripts/aitask_verified_update.sh`

Build a non-user-facing helper script with this structure:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
```

Implement these functions:

- `show_help()` — documents `--agent-string`, `--skill`, `--score`, `--silent`, `--help`
- `require_jq()` — fail early if `jq` is missing
- `map_score()` — map satisfaction scores `1..5` to `20,40,60,80,100`
- `parse_agent_string()` — split `<agent>/<model>`, validate agent against `claudecode|geminicli|codex|opencode`, and reject malformed values
- `parse_args()` — require `--agent-string`, `--skill`, and `--score`; validate score range
- `update_model_file()` — load `aitasks/metadata/models_<agent>.json`, update the matching model entry, and return the new verified score
- `commit_metadata_update()` — stage the metadata file with `./ait git add` and create an `ait:` commit only when the file changed
- `main()` — orchestrate parsing, update, commit, and structured output

### 2. Implement JSON update logic with safe writes

Use `jq` to update a single model entry by `.name`, not by `cli_id`. The script should:

1. Read `aitasks/metadata/models_<agent>.json`
2. Verify the target model exists
3. Initialize missing objects:
   - `.verified // {}`
   - `.verifiedstats // {}`
   - `.verifiedstats[$skill] // {"runs":0,"score_sum":0}`
4. Increment:
   - `runs += 1`
   - `score_sum += mapped_score`
5. Recalculate `.verified[$skill]` as `round(score_sum / runs)`
6. Preserve all unrelated fields and pre-existing verified keys like `task-pick`, `explain`, and `batch-review`
7. Write through a temp file, then move it into place so partial writes cannot corrupt the JSON

Reference jq shape:

```jq
.models |= map(
  if .name == $model then
    .verified = (.verified // {}) |
    .verifiedstats = (.verifiedstats // {}) |
    .verifiedstats[$skill] = {
      "runs": ((.verifiedstats[$skill].runs // 0) + 1),
      "score_sum": ((.verifiedstats[$skill].score_sum // 0) + $score)
    } |
    .verified[$skill] = ((.verifiedstats[$skill].score_sum / .verifiedstats[$skill].runs) | round)
  else
    .
  end
)
```

### 3. Initialize tracked metadata schema

Update the tracked model config files under `aitasks/metadata/` so each model entry includes:

```json
"verifiedstats": {}
```

This makes the schema visible immediately in-repo even before the first feedback update. Do not change existing `verified` values.

### 4. Add regression tests in `tests/test_verified_update.sh`

Create a self-contained bash test following the style of the existing `tests/test_*.sh` scripts.

Test setup should:

- create a temporary git repo
- copy in `.aitask-scripts/aitask_verified_update.sh`
- copy required library files from `.aitask-scripts/lib/`
- create minimal `ait`, `aitasks/metadata/models_<agent>.json`, and optional metadata directories needed for `./ait git` to work in legacy mode
- use `jq` to assert JSON values instead of brittle string matching

Cover these cases:

1. valid update from empty stats: score `4` creates `runs=1`, `score_sum=80`, `verified.pick=80`
2. rolling average: two updates `4` then `5` produce `runs=2`, `score_sum=180`, `verified.pick=90`
3. invalid agent string fails
4. invalid score fails
5. missing model fails
6. `--help` exits successfully
7. existing `verified` keys remain unchanged
8. missing `verifiedstats` is created automatically
9. output includes `UPDATED:<agent>/<model>:<skill>:<new_score>`

### 5. Verification and completion

Run, in order:

```bash
bash -n .aitask-scripts/aitask_verified_update.sh
shellcheck .aitask-scripts/aitask_verified_update.sh
bash tests/test_verified_update.sh
```

If implementation differs from this plan, record the deviation in the plan file before final review/commit.

## Step 9 Reference

Post-implementation cleanup still follows task-workflow Step 9: review, separate code/plan commits, archival, lock release, and `./ait git push` for task data.

## Post-Review Changes

### Change Request 1 (2026-03-10 00:00)
- **Requested by user:** Add `.aitask-scripts/aitask_verified_update.sh` to the allowed Bash-script whitelists for Claude Code, Gemini CLI, and OpenCode in both the local repo and seed configuration.
- **Changes made:** Added the new helper script to `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, and `seed/opencode_config.seed.json`.
- **Files affected:** `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`

## Final Implementation Notes

- **Actual work done:** Added `.aitask-scripts/aitask_verified_update.sh` as an internal helper that validates agent/model inputs, maps 1-5 feedback scores to 20-100 verification scores, updates `verifiedstats` and `verified` via `jq`, stages metadata with `./ait git`, and emits structured `UPDATED:...` output. Added `tests/test_verified_update.sh` to cover success, rolling averages, validation failures, lazy `verifiedstats` creation, and silent-mode output. Initialized `verifiedstats: {}` across tracked `aitasks/metadata/models_*.json` files and added script allowlist entries for Claude Code, Gemini CLI, and OpenCode seed/local configs.
- **Deviations from plan:** Did not add an `ait` dispatcher entry because the script is intentionally internal and called directly by workflow procedures. The script suppresses `git commit` output when `--silent` is used so structured output remains machine-readable.
- **Issues encountered:** The first implementation leaked `git commit` output in silent mode, which broke the test expectation; fixed by redirecting commit output to `/dev/null` only for silent mode. `shellcheck` also needed an explicit `SC1091` suppression for the sourced helper library path.
- **Key decisions:** Kept schema initialization both in the script (lazy creation) and in tracked metadata files so the new `verifiedstats` structure is visible immediately in repository data. Used temp-file JSON writes for safer updates instead of in-place overwrite pipelines.
- **Notes for sibling tasks:** Later tasks can call `.aitask-scripts/aitask_verified_update.sh` directly with `--agent-string`, `--skill`, `--score`, and optional `--silent`; no dispatcher command is required. Satisfaction-feedback workflows should rely on the structured `UPDATED:<agent>/<model>:<skill>:<new_score>` line and may assume missing `verifiedstats` is handled automatically by the script.
