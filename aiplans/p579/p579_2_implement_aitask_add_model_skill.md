---
Task: t579_2_implement_aitask_add_model_skill.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_1_*.md, aitasks/t579/t579_3_*.md, aitasks/t579/t579_4_*.md, aitasks/t579/t579_5_*.md
Archived Sibling Plans: aiplans/archived/p579/p579_*_*.md
Worktree: (none — profile fast sets create_worktree: false)
Branch: main
Base branch: main
---

# Plan: t579_2 — Implement aitask-add-model skill (simplified post-t579_5)

## Context

Ship the new `aitask-add-model` skill per the design spec from t579_1
(`aidocs/model_reference_locations.md`). Depends on t579_5 (externalization
refactor) having landed; post-refactor, brainstorm agent defaults live
solely in `codeagent_config.json`, so the skill no longer needs a
`promote-brainstorm` subcommand. Does NOT add opus4_7 — that's t579_3's
validation exercise.

Read first:
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Design spec: `aidocs/model_reference_locations.md` (§3 Design spec)
- Reference skill: `.claude/skills/aitask-refresh-code-models/SKILL.md`
- Prereq refactor plan (archived): `aiplans/archived/p579/p579_5_*.md`

## Step 1 — Scaffold the skill

Create:
- `.claude/skills/aitask-add-model/SKILL.md` (frontmatter: name, description)
- `.aitask-scripts/aitask_add_model.sh` (`#!/usr/bin/env bash`, `set -euo
  pipefail`, source `lib/terminal_compat.sh` + `lib/task_utils.sh`)
- `tests/test_add_model.sh`

## Step 2 — SKILL.md workflow (7 steps)

Mirror the structure of `refresh-code-models/SKILL.md`:

1. **Parse inputs** — CLI flags or `AskUserQuestion` prompts
2. **Validate** — agent ∈ {claudecode, geminicli, codex}; `--agent
   opencode` refused with pointer to `aitask-refresh-code-models`;
   `name` matches `[a-z][a-z0-9_]*`; `cli_id` non-empty; `name` not
   already in `models_<agent>.json`
3. **Compute proposed changes** per mode
4. **Dry-run or apply** — `--dry-run` calls helpers with `--dry-run` to
   emit diffs and returns
5. **Emit manual-review list** — after a real apply only (promote-mode)
6. **Commit** per the split in the design spec §3.5
7. **Satisfaction Feedback** — `satisfaction-feedback.md` with
   `skill_name="add-model"`

## Step 3 — Helper script `aitask_add_model.sh`

Subcommands (5, down from 6 pre-t579_5):

| Subcommand | Purpose |
|---|---|
| `add-json` | Append model entry to `models_<agent>.json` (+ seed sync); jq |
| `promote-config` | Update `codeagent_config.json` defaults for specified ops (+ seed). Handles pick/explain/batch-review/qa/raw/explore AND brainstorm-* ops uniformly — all are plain config keys post-t579_5 |
| `promote-default-agent-string` | Update line 21 + line 663 in `aitask_codeagent.sh` (claudecode only; error otherwise) |
| `promote-aidocs` | Update `aidocs/claudecode_tools.md:5` (pick op + claudecode only; auto-derived display name, `--display-name` override) |
| `emit-manual-review` | Print the post-apply manual-review block |

Shared flags: `--agent`, `--name`, `--cli-id`, `--notes`, `--ops`,
`--dry-run`, `--display-name`.

Portability (per `CLAUDE.md`):
- `sed_inplace` for in-place edits
- Anchored regex: `^DEFAULT_AGENT_STRING=`, `^\*\*Model:\*\* `
- `jq` for all JSON; NEVER sed on JSON
- No GNU-only sed (`\U`, `/pattern/a`), no `grep -P`

## Step 4 — Tests `tests/test_add_model.sh`

Follow the `test_verified_update_flags.sh` structure:
- `TMPDIR`-isolated fixture copies
- Helpers: `assert_eq`, `assert_contains`, `setup_fixture`, `teardown`
- PASS/FAIL counter + summary

Cases (8, down from 9 pre-t579_5):
1. `add-json` appends entry, preserves existing `verified`/`verifiedstats`
2. `add-json` idempotent-with-error: second run errors
3. `promote-config` updates only listed ops (including brainstorm-* ops —
   all are plain config keys now)
4. `promote-default-agent-string` errors if agent != claudecode
5. `promote-default-agent-string` replaces lines 21 + 663 correctly
6. `--dry-run` across all subcommands emits diffs AND leaves fs unchanged
   (verify via `git diff --quiet`)
7. `jq .` succeeds on every produced JSON
8. Invalid inputs fail with clear errors:
   - unknown agent
   - malformed `name` (uppercase, spaces)
   - empty `cli_id`
   - `--agent opencode` → "Use aitask-refresh-code-models for opencode"

## Step 5 — Verify

```bash
shellcheck .aitask-scripts/aitask_add_model.sh
bash tests/test_add_model.sh

# Add-mode dry-run
/aitask-add-model --dry-run --agent claudecode --name opus4_7 \
  --cli-id claude-opus-4-7 --notes "test"

# Promote-mode dry-run (brainstorm ops included)
/aitask-add-model --dry-run --promote --agent claudecode --name opus4_7 \
  --cli-id claude-opus-4-7 --notes "test" \
  --promote-ops pick,explore,brainstorm-explorer,brainstorm-synthesizer
```

Expect:
- Add-mode dry-run: 2 proposed writes (metadata + seed)
- Promote-mode dry-run: ~5 proposed writes (models + seed + codeagent_config
  + seed + aitask_codeagent.sh + aidocs/claudecode_tools.md) plus manual-
  review block. NO python/yaml patching (thanks to t579_5).
- `git status` at end shows only new skill dir + helper + test file.

## Step 6 — Commit

```bash
git add .claude/skills/aitask-add-model/SKILL.md \
        .aitask-scripts/aitask_add_model.sh \
        tests/test_add_model.sh
git commit -m "feature: Add aitask-add-model skill for known-model registration and default promotion (t579_2)"
./ait git push
```

## Step 9 (Post-Implementation)

Archive via `./.aitask-scripts/aitask_archive.sh 579_2`. Final
Implementation Notes must include the final SKILL.md API surface so t579_3
has the exact flag syntax ready.
