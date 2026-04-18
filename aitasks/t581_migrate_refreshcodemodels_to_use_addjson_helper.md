---
priority: low
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [codeagent, ait_settings]
created_at: 2026-04-17 09:02
updated_at: 2026-04-17 09:12
boardcol: now
boardidx: 100
---

## Context

With t579_2 complete, `.aitask-scripts/aitask_add_model.sh` exposes an `add-json` subcommand that atomically appends a model entry to `models_<agent>.json` (+ seed sync, JSON validation, duplicate check, `--dry-run`). The `aitask-refresh-code-models` skill currently has Claude write the JSON directly — duplicating the logic. For consistency between skills, migrate the NEW-model append path to the helper.

## Scope

- Replace the "append new model" logic in `.claude/skills/aitask-refresh-code-models/SKILL.md` Step 6 with a call to:
  ```
  ./.aitask-scripts/aitask_add_model.sh add-json --agent <a> --name <n> --cli-id <id> --notes "<s>"
  ```
- Keep UPDATE (change `notes`) and optional DELETE (remove deprecated) inline in the skill — the helper intentionally does not cover those.
- Helper's duplicate-check semantics (error on existing `name`) align with refresh's "skip if `cli_id` matches" filtering — no behavioral change expected, but document the edge case where a user renames a model locally and the cli_id-based categorization says "NEW" while the name collides.
- Seed sync becomes automatic (the helper handles it) — remove the now-redundant seed copy block from the skill's Step 6.

## Out of Scope

- Adding `update-json` / `remove-json` subcommands to the helper (deferred; would be its own task).
- OpenCode path — unchanged, still uses `aitask_opencode_models.sh`.
- Commit-message / group split in the skill — unchanged.

## Verification

1. `shellcheck .aitask-scripts/aitask_add_model.sh` still exit 0 (no helper changes expected)
2. Dry-run a refresh that discovers one new dummy model — the skill should invoke `add-json --dry-run` and emit a diff identical in shape to what it used to produce by direct write
3. Apply path: JSON still validates, seed still syncs, verified/verifiedstats on existing entries untouched
4. `bash tests/test_add_model.sh` still passes (helper unchanged)

## Sibling Skill Mirrors

After Claude Code SKILL.md is updated, flag the same change for the Gemini CLI, Codex CLI, and OpenCode mirrors per CLAUDE.md "WORKING ON SKILLS" guidance. Do NOT edit those in this task — suggest follow-up tasks to the user.
