---
Task: t579_2_implement_aitask_add_model_skill.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_1_*.md, aitasks/t579/t579_3_*.md, aitasks/t579/t579_4_*.md
Archived Sibling Plans: aiplans/archived/p579/p579_*_*.md
Worktree: aiwork/t579_2_implement_aitask_add_model_skill
Branch: aitask/t579_2_implement_aitask_add_model_skill
Base branch: main
---

# Plan: t579_2 — Implement aitask-add-model skill

## Context

Second of 4 children for t579. Implements the new `aitask-add-model` skill per
the design spec produced in t579_1 (`aidocs/model_reference_locations.md`).
Does NOT add opus4_7 — that's t579_3's verification exercise.

Read first:
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- t579_1 deliverable: `aidocs/model_reference_locations.md` (especially §3
  Design spec)
- Reference skill: `.claude/skills/aitask-refresh-code-models/SKILL.md`

## Step 1 — Scaffold the skill

Create:
- `.claude/skills/aitask-add-model/SKILL.md` (frontmatter: name, description)
- `.aitask-scripts/aitask_add_model.sh` (`#!/usr/bin/env bash`, `set -euo
  pipefail`, source `lib/terminal_compat.sh` + `lib/task_utils.sh`)
- `tests/test_add_model.sh`

## Step 2 — SKILL.md workflow

Mirror the 9-step structure of `refresh-code-models/SKILL.md`:

1. **Parse inputs** — accept CLI flags or prompt via `AskUserQuestion`
2. **Validate** — agent ∈ {claudecode, geminicli, codex, opencode};
   name matches `[a-z][a-z0-9_]*`; cli_id non-empty; name not already in
   `models_<agent>.json`
3. **Compute proposed changes** — per mode
4. **Dry-run or apply** — if `--dry-run`, call helper with `--dry-run` to
   emit diffs and return
5. **Emit manual-review list** — after a real apply only
6. **Commit** — per the split in §3.5 of the design spec
7. **Satisfaction Feedback** — call `satisfaction-feedback.md` with
   `skill_name="add-model"`

## Step 3 — Helper script `aitask_add_model.sh`

Subcommands:

| Subcommand | Purpose |
|---|---|
| `add-json` | Append model entry to `models_<agent>.json` (+ seed sync); use `jq` with `| .models += [{name, cli_id, notes, verified, verifiedstats}]` |
| `promote-config` | Update `codeagent_config.json` defaults for specified ops (+ seed) |
| `promote-default-agent-string` | Update `DEFAULT_AGENT_STRING` in `aitask_codeagent.sh` (claudecode only) |
| `promote-brainstorm` | Update `BRAINSTORM_AGENT_TYPES` keys + `crew_meta_template.yaml` for brainstorm ops |

Shared flags: `--agent`, `--name`, `--cli-id`, `--notes`, `--ops`, `--dry-run`.

Portability (per `CLAUDE.md`):
- Use `sed_inplace` for in-place edits, not `sed -i`
- Escape regex characters when matching hardcoded defaults
- For the python file, anchor on the dictionary key name (e.g.,
  `"explorer": {"agent_string":`) to avoid false positives
- For the yaml file, use a similar anchored pattern

## Step 4 — Tests `tests/test_add_model.sh`

Follow the `test_crew_setmode.sh` / `test_verified_update_flags.sh` structure:
- Use `TMPDIR` for isolated copies of fixture files
- Helper functions: `assert_eq`, `assert_contains`, `setup_fixture`, `teardown`
- PASS/FAIL summary at end

Cases:
1. `add-json` appends entry and preserves existing entries' `verified`
2. `add-json` is idempotent (second run = no-op or clear error, decide)
3. `promote-config` updates only specified ops
4. `promote-default-agent-string` only writes when agent=claudecode
5. `promote-brainstorm` updates only brainstorm ops
6. `--dry-run` leaves filesystem unchanged AND emits diff on stdout
7. `jq .` succeeds on every produced JSON
8. Unknown agent / malformed cli_id / duplicate name fail with non-zero exit

## Step 5 — Verify

```bash
shellcheck .aitask-scripts/aitask_add_model.sh
bash tests/test_add_model.sh

# Manual dry-run exercises
/aitask-add-model --dry-run --agent claudecode --name opus4_7 \
  --cli-id claude-opus-4-7 --notes "test"
/aitask-add-model --dry-run --promote --agent claudecode --name opus4_7 \
  --cli-id claude-opus-4-7 --notes "test" --promote-ops pick,explore
```

Confirm:
- First dry-run shows 2 proposed writes (metadata + seed)
- Second dry-run shows 4+ proposed writes (metadata + seed + codeagent_config
  + seed + aitask_codeagent.sh)

## Step 6 — Commit

```bash
git add .claude/skills/aitask-add-model/SKILL.md \
        .aitask-scripts/aitask_add_model.sh \
        tests/test_add_model.sh
git commit -m "feature: Add aitask-add-model skill for known-model registration and default promotion (t579_2)"
./ait git push
```

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 579_2`. Final Implementation
Notes should include the actual final SKILL.md API surface (so t579_3 knows
the exact flags to invoke).
