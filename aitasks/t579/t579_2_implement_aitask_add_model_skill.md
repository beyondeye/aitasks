---
priority: high
effort: medium
depends: [t579_1]
issue_type: feature
status: Ready
labels: [codeagent, ait_settings, model_selection]
created_at: 2026-04-16 23:26
updated_at: 2026-04-16 23:26
---

## Context

This is child 2 of 4 for parent task t579 (adding Opus 4.7 support). Depends on
t579_1, which produces `aidocs/model_reference_locations.md` — the inventory +
design spec that drives this implementation.

Build the new `aitask-add-model` skill per the approved design. The skill
registers a known new model in `models_<agent>.json` (add mode) and optionally
promotes it to the new default across all hardcoded default locations (promote
mode). It complements `aitask-refresh-code-models` (which does web research for
discovery). Opus 4.7 specifically is NOT added here — that's t579_3's
verification exercise.

## Key Files to Modify

1. **CREATE** `.claude/skills/aitask-add-model/SKILL.md` — the skill workflow
2. **CREATE** `.aitask-scripts/aitask_add_model.sh` — bash helper for JSON
   patching and atomic default promotion (if the design spec calls for it)
3. **CREATE** `tests/test_add_model.sh` — unit tests for the helper
4. Possibly update `.aitask-scripts/lib/task_utils.sh` if shared helpers are
   needed

No changes to `models_*.json`, `codeagent_config.json`, `aitask_codeagent.sh`,
`brainstorm_crew.py`, or `crew_meta_template.yaml` in this task — those are
touched only by invoking the skill in t579_3.

## Reference Files for Patterns

- `.claude/skills/aitask-refresh-code-models/SKILL.md` — structure template
  (sections: Workflow, Model Naming Convention, Notes)
- `.claude/skills/aitask-create/SKILL.md` + `.aitask-scripts/aitask_create.sh` —
  batch/interactive mode pattern (e.g., `--batch`, `--desc-file -`)
- `.aitask-scripts/aitask_verified_update.sh` — jq-based JSON manipulation
- `.aitask-scripts/aitask_opencode_models.sh` — how to integrate with OpenCode
  discovery for add-mode on opencode
- `.aitask-scripts/lib/terminal_compat.sh` — `sed_inplace`, `die`, `warn`, `info`
- `CLAUDE.md` — Shell Conventions section (sed/grep/wc/mktemp/base64 portability)

## Implementation Plan

### 1. SKILL.md structure

Follow the 9-step structure of `aitask-refresh-code-models/SKILL.md`:

```
Step 1: Parse inputs (or prompt interactively)
Step 2: Validate model details (cli_id matches naming convention? name not
        already present in the agent's models_*.json?)
Step 3: Compute proposed changes
  - Add-mode: one file change (+ seed sync)
  - Promote-mode: multiple file changes across JSON + bash + python + yaml
Step 4: Dry-run preview OR apply
  - If --dry-run: print per-file unified diff, exit without writing
  - Otherwise: apply each change
Step 5: Emit manual-review list (docs + tests to curate separately)
Step 6: Commit changes
  - ./ait git for aitasks/metadata/
  - git for seed/ and .aitask-scripts/
Step 7: Satisfaction Feedback
```

### 2. Bash helper `aitask_add_model.sh`

Responsibilities (driven by flags passed from SKILL.md):
- `--apply-add --agent <a> --name <n> --cli-id <id> --notes <s>`
  → patches `aitasks/metadata/models_<agent>.json` + `seed/models_<agent>.json`
- `--apply-promote-config --agent <a> --name <n> --ops <csv>`
  → patches `aitasks/metadata/codeagent_config.json` + `seed/codeagent_config.json`
- `--apply-promote-default-agent-string --agent <a> --name <n>`
  → patches `.aitask-scripts/aitask_codeagent.sh` DEFAULT_AGENT_STRING (claudecode only)
- `--apply-promote-brainstorm --agent <a> --name <n> --ops <csv>`
  → patches `.aitask-scripts/brainstorm/brainstorm_crew.py` BRAINSTORM_AGENT_TYPES
  + `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`
- `--dry-run` causes every flag to emit a diff instead of writing
- All JSON work uses `jq` (never `sed` on JSON)
- All Python/YAML work uses safe sed_inplace with anchored patterns

Each operation MUST be idempotent (running twice yields no further diffs).

### 3. Unit tests `tests/test_add_model.sh`

Cover (with isolated tmp copies of fixture files under TMPDIR):
- Add-mode inserts entry at the right position, preserves `verified` /
  `verifiedstats` on unchanged entries
- Add-mode is idempotent (second run = no-op)
- Promote-mode updates codeagent_config.json for specified ops only
- Promote-mode updates DEFAULT_AGENT_STRING only for agent=claudecode
- Promote-mode updates brainstorm entries for brainstorm-* ops
- Dry-run produces diff output AND leaves filesystem unchanged
- JSON validation: `jq . <file>` succeeds after every write
- Invalid inputs (unknown agent, duplicate name, malformed cli_id) fail with
  clear error messages and non-zero exit code

### 4. Register the skill

- If Claude Code auto-discovers skills from `.claude/skills/*/SKILL.md`,
  nothing else is needed
- Follow naming convention: directory `aitask-add-model` matches skill name

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_add_model.sh` passes
2. `bash tests/test_add_model.sh` passes
3. Manual exercise with `--dry-run`:
   ```
   /aitask-add-model --dry-run --agent claudecode --name opus4_7 \
     --cli-id claude-opus-4-7 --notes "test"
   ```
   confirms diff preview renders and no files change
4. Manual exercise with `--dry-run --promote`:
   ```
   /aitask-add-model --dry-run --promote --agent claudecode --name opus4_7 \
     --cli-id claude-opus-4-7 --notes "test" --promote-ops pick,explore
   ```
   shows diffs for all 4 target locations (config, default agent string,
   brainstorm py, crew_meta_template)
5. No actual opus4_7 entry is committed by this task. (`git status` at end
   should show only new skill files + helper script + test file.)
6. Commit: `feature: Add aitask-add-model skill for known-model registration and default promotion (t579_2)`

## Reference Files

- Parent task: `aitasks/t579_support_for_opus_4_7.md`
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Archived sibling plan: `aiplans/archived/p579/p579_1_*.md` (after t579_1 is done)
- Audit deliverable: `aidocs/model_reference_locations.md` (from t579_1)

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 579_2`. Once
archived, the plan file (with Final Implementation Notes) becomes the
reference for t579_3 to invoke the skill.
