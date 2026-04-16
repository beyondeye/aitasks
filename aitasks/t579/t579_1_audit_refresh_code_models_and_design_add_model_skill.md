---
priority: high
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [codeagent, ait_settings, documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-16 23:25
updated_at: 2026-04-16 23:30
---

## Context

This is child 1 of 4 for parent task t579 (adding Opus 4.7 support). The parent
plan (see `aiplans/p579_support_for_opus_4_7.md`) established that the existing
`aitask-refresh-code-models` skill only updates `models_*.json` (via web research)
and does NOT touch operational defaults, hardcoded `DEFAULT_AGENT_STRING`,
`BRAINSTORM_AGENT_TYPES`, or the brainstorm crew meta template. A new skill
`aitask-add-model` will fill this gap.

This child produces the audit + design spec that the next child (t579_2)
implements against.

## Key Files to Modify

1. **CREATE** `aidocs/model_reference_locations.md` — the audit deliverable.

No other files are modified by this task.

## Reference Files for Patterns

Read these to inform the audit:
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — what it currently covers
- `aitasks/metadata/models_claudecode.json` — current model registry format
- `aitasks/metadata/codeagent_config.json` — operational defaults
- `.aitask-scripts/aitask_codeagent.sh` line 21 — `DEFAULT_AGENT_STRING`
- `.aitask-scripts/brainstorm/brainstorm_crew.py` lines 45-50 — `BRAINSTORM_AGENT_TYPES`
- `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`
- `.aitask-scripts/aitask_crew_init.sh`, `aitask_update.sh` (help-text examples)
- `website/content/docs/commands/codeagent.md`
- `website/content/docs/tuis/settings/reference.md`
- `aidocs/claudecode_tools.md` line 5
- `tests/test_codeagent.sh`, `tests/test_resolve_detected_agent.sh`,
  `tests/test_aitask_stats_py.py`, `tests/test_brainstorm_crew.py`,
  `tests/test_verified_update_flags.sh`

For skill-design conventions, look at:
- `.claude/skills/aitask-refresh-code-models/SKILL.md` (structure template)
- `.claude/skills/aitask-create/SKILL.md` + `.aitask-scripts/aitask_create.sh` (batch/interactive pattern)

## Implementation Plan

1. **Inventory section** of `aidocs/model_reference_locations.md`:
   For every file in the Reference list above (plus any others found via a
   `grep -rn "opus4\|opus_4\|claude-opus-4\|opus4_6\|sonnet4_6\|haiku4_5"`
   sweep), record:
   - File path
   - Line number(s)
   - What the reference is (live default, example in docs, test fixture, etc.)
   - Tag: one of `covered_by_refresh`, `needed_for_add`, `needed_for_promote`,
     `informational_only`
   - Notes on any agent-specific quirks

2. **Design spec section** — covers:
   - Skill directory: `.claude/skills/aitask-add-model/`
   - Two modes: **add** (default) and **promote** (`--promote`)
   - CLI surface:
     ```
     /aitask-add-model [--agent <a>] [--name <n>] [--cli-id <id>] [--notes <s>]
                       [--promote] [--promote-ops <csv>]
                       [--dry-run] [--batch]
     ```
   - Supported agents: claudecode, geminicli, codex, opencode (call out that
     opencode has CLI-based discovery — decide whether add-mode should still
     write the JSON entry manually or delegate to `aitask_opencode_models.sh`)
   - Interactive prompts: agent → name → cli_id → notes → promote?
     → promote-ops (multiSelect)
   - Auto-applied file list per mode (cross-reference the inventory's
     `needed_for_add` / `needed_for_promote` entries)
   - Manual-review output format (the list of docs/tests the skill prints for
     follow-up)
   - Dry-run semantics: print per-file diff (`diff -u original proposed`),
     no filesystem writes
   - Commit strategy: one commit per file group
     (`./ait git` for `aitasks/metadata/`, plain `git` for `seed/` and
     `.aitask-scripts/`)
   - Helper bash: whether to introduce `.aitask-scripts/aitask_add_model.sh`
     (recommended — keeps JSON patching testable)
   - Testing plan: unit tests in `tests/test_add_model.sh`

3. **Open questions / decisions** section: anything that requires user input
   at t579_2 implementation time (e.g., exact message format for the commit,
   whether to silence tests_* updates entirely).

## Verification Steps

1. `aidocs/model_reference_locations.md` exists and renders cleanly in markdown
2. Every file listed in the parent plan's "Coverage gap analysis" section is
   accounted for in the inventory
3. The design spec answers: "If I follow this spec, can I build the skill in
   t579_2 without needing further exploration?"
4. No code changes outside `aidocs/`
5. Commit: `documentation: Audit refresh-code-models and design add-model skill (t579_1)`

## Reference Files

- Parent task: `aitasks/t579_support_for_opus_4_7.md`
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Archived sibling plans: none yet (this is first child)

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 579_1`. No worktree
to clean up (profile `fast` works on current branch).
