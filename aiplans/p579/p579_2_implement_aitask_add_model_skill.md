---
Task: t579_2_implement_aitask_add_model_skill.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_3_add_opus_4_7_as_new_default_using_add_model_skill.md, aitasks/t579/t579_4_update_tests_and_docs_for_opus_4_7.md
Archived Sibling Plans: aiplans/archived/p579/p579_1_audit_refresh_code_models_and_design_add_model_skill.md, aiplans/archived/p579/p579_5_externalize_model_defaults.md
Base branch: main
plan_verified:
  - claudecode/claude-opus-4-7 @ 2026-04-17 08:15
---

# Plan: t579_2 — Implement `aitask-add-model` skill (verified)

## Context

Child task of t579 (Opus 4.7 support). Ships a new skill
`aitask-add-model` that complements `aitask-refresh-code-models`:
register a known new model in `models_<agent>.json` (add mode) and
optionally promote it to default across `codeagent_config.json`,
`DEFAULT_AGENT_STRING`, and the claudecode pick-model doc reference
(promote mode). Opus 4.7 itself is NOT added here — t579_3 validates the
skill end-to-end with it.

This task was picked via `/aitask-pick 579_2` with the `fast` execution
profile (default for `pick`). `plan_preference_child: verify` triggered
verification of the existing plan at
`aiplans/p579/p579_2_implement_aitask_add_model_skill.md`.

## Verification findings (verify path)

The existing plan was checked against the current codebase. All
assumptions hold:

- **`aitask_codeagent.sh:21`** — `DEFAULT_AGENT_STRING="claudecode/opus4_6"` (confirmed).
- **`aitask_codeagent.sh:663`** — `"4. Hardcoded default: claudecode/opus4_6"` (confirmed).
- **`aidocs/claudecode_tools.md:5`** — `**Model:** Claude Opus 4.6 (\`claude-opus-4-6\`)` (confirmed).
- **`aitasks/metadata/codeagent_config.json`** — contains `pick`, `explain`, `batch-review`, `qa`, `raw`, `explore`, `brainstorm-*` keys plus `brainstorm-explorer-launch-mode`. Config is the sole source of truth for brainstorm agent strings post-t579_5.
- **`seed/`** exists with `codeagent_config.json`, `models_*.json` — seed sync targets are live.
- **t579_5 prerequisite is complete** — `agent_string` removed from `BRAINSTORM_AGENT_TYPES`; `crew_meta_template.yaml` deleted; `aitask_brainstorm_init.sh` fallbacks dropped. Confirms `promote-brainstorm` subcommand is NOT needed (per the post-t579_5 simplification documented in the plan).
- **Reference patterns available:**
  - `.claude/skills/aitask-refresh-code-models/SKILL.md` for skill structure.
  - `.aitask-scripts/aitask_verified_update.sh` for `jq`-based JSON patching with tempfile `mv` atomicity and `ensure_model_exists` pattern.
  - `tests/test_verified_update_flags.sh` for test scaffolding (`assert_eq`, `assert_contains`, PASS/FAIL summary).
  - `.aitask-scripts/lib/terminal_compat.sh` provides `sed_inplace`, `die`, `warn`, `info`, `success`.

No plan updates needed. Proceeding with the existing plan as-is.

## Simplification from the original plan

The original plan (archived from t579_1 design spec) had 5 subcommands
and 8 test cases. After user review: drop `promote-aidocs` and
`emit-manual-review` as over-engineered.

- **`promote-aidocs`**: one-line sed to `aidocs/claudecode_tools.md:5`,
  only fires for claudecode+pick. Doc updates belong in t579_4's docs
  scope (which already enumerates this file). Move to the manual-review
  list instead.
- **`emit-manual-review`**: prints a static block of text with no real
  logic. Inline as a heredoc in SKILL.md after apply.

Net: 3 subcommands, 6 test cases, same end-user behavior.

## Implementation summary

### Files to CREATE (3)

1. **`.aitask-scripts/aitask_add_model.sh`** — bash helper with **3 subcommands**:
   | Subcommand | Purpose |
   |---|---|
   | `add-json --agent --name --cli-id --notes [--dry-run]` | Append model entry to `models_<agent>.json` + sync `seed/models_<agent>.json` |
   | `promote-config --agent --name --ops <csv> [--dry-run]` | Update `codeagent_config.json` defaults for listed ops (including `brainstorm-*`) + sync seed |
   | `promote-default-agent-string --agent --name [--dry-run]` | Update `aitask_codeagent.sh` line 21 + line 663 (claudecode-only; error otherwise) |

   Portability: `jq` for JSON only, `sed_inplace` for text, anchored regex (`^DEFAULT_AGENT_STRING=`), no GNU-only sed/grep features. All subcommands idempotent; `--dry-run` prints unified diff and exits 0 without writing.

2. **`.claude/skills/aitask-add-model/SKILL.md`** — 7-step workflow:
   1. Parse inputs (CLI flags or `AskUserQuestion`)
   2. Validate: agent ∈ {claudecode, geminicli, codex}; refuse opencode with pointer to `aitask-refresh-code-models`; `name` matches `[a-z][a-z0-9_]*`; `cli_id` non-empty; `name` unique in target registry
   3. Compute proposed changes per mode
   4. Dry-run (emit diffs) OR apply (invoke helper subcommands)
   5. Print static manual-review block inline via heredoc (promote-mode post-apply only). Block lists `aidocs/claudecode_tools.md:5`, `tests/test_codeagent.sh`, `tests/test_brainstorm_crew.py`, `website/content/docs/commands/codeagent.md`, with a pointer to `aidocs/model_reference_locations.md` for the full audit.
   6. Commit: `./ait git` for `aitasks/metadata/` and seed metadata; plain `git` for `.aitask-scripts/`; split per the design spec §3.5
   7. Satisfaction Feedback (`satisfaction-feedback.md`, `skill_name="add-model"`)

3. **`tests/test_add_model.sh`** — **6 test cases** (TMPDIR-isolated fixtures, patterned on `test_verified_update_flags.sh`):
   1. `add-json` appends entry preserving existing `verified`/`verifiedstats`
   2. `add-json` errors on second run (idempotent-with-error)
   3. `promote-config` updates only listed ops (including `brainstorm-*`)
   4. `promote-default-agent-string` errors if agent != claudecode; replaces lines 21 AND 663 correctly when agent == claudecode
   5. `--dry-run` across all subcommands emits diffs AND leaves filesystem unchanged; `jq .` succeeds on every produced JSON
   6. Invalid inputs fail with clear errors (unknown agent, malformed name, malformed cli_id, `--agent opencode` rejection)

### Files NOT touched in this task
- `models_*.json`, `codeagent_config.json`, `aitask_codeagent.sh`, `aidocs/claudecode_tools.md`, brainstorm files — these are only modified when the skill is invoked (t579_3). `aidocs/claudecode_tools.md:5` is now part of t579_4's docs scope (already enumerated there).

## Verification steps

1. `shellcheck .aitask-scripts/aitask_add_model.sh` exits 0
2. `bash tests/test_add_model.sh` — 8/8 PASS
3. Add-mode dry-run smoke (no real model added):
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
   Shows 4 proposed writes (metadata + seed for models AND config, + `aitask_codeagent.sh`) plus the static manual-review block. NO python/yaml patching, NO aidocs patching (deferred to t579_4).
5. `git diff --quiet` holds after any dry-run invocation.
6. `git status` at end of task shows ONLY the 3 new files (skill dir + helper + test). No opus4_7 entries anywhere.

## Commit

```bash
git add .claude/skills/aitask-add-model/SKILL.md \
        .aitask-scripts/aitask_add_model.sh \
        tests/test_add_model.sh
git commit -m "feature: Add aitask-add-model skill for known-model registration and default promotion (t579_2)"
```
Plan file update (Final Implementation Notes) committed separately via `./ait git`.

## Step 9 (Post-Implementation)

Archive via `./.aitask-scripts/aitask_archive.sh 579_2`. The archived
plan (with Final Implementation Notes) becomes the reference for
t579_3 to invoke the skill with opus4_7 inputs.
