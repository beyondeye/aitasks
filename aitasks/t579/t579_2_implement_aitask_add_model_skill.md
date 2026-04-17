---
priority: high
effort: medium
depends: [t579_1, t579_5]
issue_type: feature
status: Implementing
labels: [codeagent, ait_settings, model_selection]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-16 23:26
updated_at: 2026-04-17 08:03
---

## Context

Child task for parent t579 (adding Opus 4.7 support). Depends on t579_1
(design spec at `aidocs/model_reference_locations.md`) AND t579_5
(externalization refactor that moves brainstorm agent defaults fully into
`codeagent_config.json`).

Build the new `aitask-add-model` skill per the approved design. The skill
registers a known new model in `models_<agent>.json` (add mode) and
optionally promotes it to the new default (promote mode). It complements
`aitask-refresh-code-models` (which does web research for discovery). Opus
4.7 specifically is NOT added here — that's t579_3's verification
exercise.

**Scope simplification (post-t579_5):** Brainstorm agent defaults now
live solely in `codeagent_config.json` (no duplicated hardcoded fallbacks
in Python/YAML/bash), so promote-mode for brainstorm ops is just another
set of config keys written alongside `pick`/`explore`/etc. Only
`aitask_codeagent.sh:21` `DEFAULT_AGENT_STRING` remains as a source-code
fallback the skill needs to patch (one anchored bash line + its line-663
mirror, claudecode-only).

## Key Files to Modify

1. **CREATE** `.claude/skills/aitask-add-model/SKILL.md` — skill workflow
2. **CREATE** `.aitask-scripts/aitask_add_model.sh` — bash helper with
   subcommands for JSON patching and default promotion
3. **CREATE** `tests/test_add_model.sh` — unit tests for the helper

No changes to any `models_*.json`, `codeagent_config.json`,
`aitask_codeagent.sh`, or brainstorm files in this task — those are
touched only when the skill is invoked in t579_3.

## Reference Files for Patterns

- `.claude/skills/aitask-refresh-code-models/SKILL.md` — structure template
- `.claude/skills/aitask-create/SKILL.md` + `.aitask-scripts/aitask_create.sh`
  — batch/interactive mode pattern (e.g., `--batch`, `--desc-file -`)
- `.aitask-scripts/aitask_verified_update.sh` — jq-based JSON manipulation
- `.aitask-scripts/aitask_opencode_models.sh` — OpenCode discovery
  (referenced for opencode refusal rationale)
- `.aitask-scripts/lib/terminal_compat.sh` — `sed_inplace`, `die`,
  `warn`, `info`
- `CLAUDE.md` — Shell Conventions section (sed/grep/wc/mktemp/base64
  portability)

## Implementation Plan

### 1. SKILL.md structure (7 steps)

```
Step 1: Parse inputs (or prompt interactively)
Step 2: Validate (agent supported; name/cli_id format; name unique)
Step 3: Compute proposed changes
  - Add-mode: 1 file + seed sync
  - Promote-mode: 1 file + seed sync (config), + optionally DEFAULT_AGENT_STRING
    bash line (+ mirror) if --agent claudecode, + optionally aidocs/claudecode_tools.md
    line 5 if pick op + claudecode
Step 4: Dry-run or apply
Step 5: Emit manual-review list (docs + tests to curate separately)
Step 6: Commit changes (./ait git for metadata, plain git for source/seed)
Step 7: Satisfaction Feedback
```

### 2. Bash helper `aitask_add_model.sh` (5 subcommands)

| Subcommand | Purpose |
|---|---|
| `add-json --agent <a> --name <n> --cli-id <id> --notes <s> [--dry-run]` | Append entry to `models_<agent>.json` + seed |
| `promote-config --agent <a> --name <n> --ops <csv> [--dry-run]` | Update `codeagent_config.json` + seed for ALL promote-ops (including brainstorm-*, since those are now plain config keys post-t579_5) |
| `promote-default-agent-string --agent <a> --name <n> [--dry-run]` | Update `aitask_codeagent.sh` line 21 + line 663 (claudecode only; error otherwise) |
| `promote-aidocs --agent <a> --name <n> --display-name <s> --cli-id <id> [--dry-run]` | Update `aidocs/claudecode_tools.md:5` (pick op + claudecode only) |
| `emit-manual-review --agent <a> --old-name <n> --new-name <n>` | Print the manual-review follow-up block |

**Gone (thanks to t579_5):** `promote-brainstorm` subcommand. Brainstorm
ops are handled by `promote-config` like any other config key.

All subcommands:
- Use `jq` for JSON; `sed_inplace` (from `lib/terminal_compat.sh`) for text
- Are idempotent (re-running after apply yields zero diffs)
- Validate every produced JSON with `jq . <f>`
- On `--dry-run`: print `diff -u` and exit 0

### 3. Unit tests `tests/test_add_model.sh`

Cases (8, down from 9):
1. `add-json` appends entry preserving existing `verified`/`verifiedstats`
2. `add-json` is idempotent-with-error: second run errors clearly
3. `promote-config` updates only listed ops — including brainstorm-* ops
4. `promote-default-agent-string` errors if agent != claudecode
5. `promote-default-agent-string` replaces line 21 + line 663 correctly
6. `--dry-run` across all subcommands emits diffs AND leaves fs unchanged
7. JSON validation: `jq .` succeeds on every produced JSON file
8. Invalid inputs fail with clear errors (unknown agent, malformed name,
   malformed cli_id, `--agent opencode` rejection)

Use `TMPDIR`-isolated fixtures and `assert_eq`/`assert_contains`/
PASS-FAIL-summary pattern from `test_verified_update_flags.sh`.

### 4. Register the skill

- Directory name `aitask-add-model` auto-registers via `.claude/skills/`
  convention
- No additional registry file

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_add_model.sh` passes
2. `bash tests/test_add_model.sh` passes (8/8)
3. Add-mode dry-run smoke:
   ```
   /aitask-add-model --dry-run --agent claudecode --name opus4_7 \
     --cli-id claude-opus-4-7 --notes "test"
   ```
   Shows 2 proposed writes (metadata + seed).
4. Promote-mode dry-run smoke:
   ```
   /aitask-add-model --dry-run --promote --agent claudecode --name opus4_7 \
     --cli-id claude-opus-4-7 --notes "test" \
     --promote-ops pick,explore,brainstorm-explorer
   ```
   Shows ~5 proposed writes (metadata + seed for models AND config, +
   aitask_codeagent.sh for DEFAULT_AGENT_STRING, + aidocs if pick op)
   and a manual-review block. NO python/yaml patching (per t579_5).
5. `git diff --quiet` holds after any dry-run invocation.
6. `git status` at end of task shows only new skill dir + helper script
   + test file. No opus4_7 entries anywhere.
7. Commit: `feature: Add aitask-add-model skill for known-model
   registration and default promotion (t579_2)`

## Reference Files

- Parent task: `aitasks/t579_support_for_opus_4_7.md`
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Archived sibling plans: `aiplans/archived/p579/p579_*_*.md` (for t579_1,
  t579_5 after they are done)
- Design spec: `aidocs/model_reference_locations.md` (from t579_1)

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 579_2`. Once
archived, the plan file (with Final Implementation Notes) becomes the
reference for t579_3 to invoke the skill with opus4_7 inputs.
