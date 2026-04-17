---
priority: high
effort: low
depends: [t579_2]
issue_type: feature
status: Done
labels: [codeagent, ait_settings, model_selection]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-16 23:26
updated_at: 2026-04-17 10:06
completed_at: 2026-04-17 10:06
---

## Context

This is child 3 of 4 for parent task t579 (adding Opus 4.7 support). Depends on
t579_2, which ships the new `aitask-add-model` skill.

Use the new skill in `--promote` mode to register Opus 4.7 AND make it the new
default for pick/explore/brainstorm-opus operations. This task is the
end-to-end validation that the skill from t579_2 works on a real vendor
model.

## Key Files to Modify

The skill modifies these automatically (do NOT edit them by hand — the whole
point is that the skill does it):

- `aitasks/metadata/models_claudecode.json` — adds opus4_7 entry
- `seed/models_claudecode.json` — synced
- `aitasks/metadata/codeagent_config.json` — updates defaults for promoted ops
- `seed/codeagent_config.json` — synced
- `.aitask-scripts/aitask_codeagent.sh` — updates `DEFAULT_AGENT_STRING`
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — updates `BRAINSTORM_AGENT_TYPES` opus entries
- `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml` — updates opus defaults

If any file does not get updated correctly by the skill, that is a BUG in the
skill (fix in a follow-up task or go back to t579_2) — do NOT patch manually.

## Reference Files for Patterns

- Parent task: `aitasks/t579_support_for_opus_4_7.md`
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Archived sibling plans: `aiplans/archived/p579/p579_1_*.md`, `p579_2_*.md`
- Skill directory: `.claude/skills/aitask-add-model/` (from t579_2)
- Helper script: `.aitask-scripts/aitask_add_model.sh` (from t579_2)
- Model naming convention: `aitask-refresh-code-models/SKILL.md` "Model Naming Convention"

## Implementation Plan

### 1. Verify the skill ships correctly
Before invoking, confirm `.claude/skills/aitask-add-model/SKILL.md` and
`.aitask-scripts/aitask_add_model.sh` exist and `tests/test_add_model.sh`
passes. If not, t579_2 is not really complete — surface the gap and stop.

### 2. Dry-run first
```
/aitask-add-model --dry-run --promote \
  --agent claudecode \
  --name opus4_7 \
  --cli-id claude-opus-4-7 \
  --notes "Most intelligent Claude model, successor to opus4_6" \
  --promote-ops pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer
```
Review the emitted diffs for all 7 target files. Confirm:
- No unexpected files are modified
- The new opus4_7 entry in `models_claudecode.json` follows the existing
  structure (`verified` + `verifiedstats` both initialized)
- `codeagent_config.json` changes affect exactly the 5 requested ops
- `DEFAULT_AGENT_STRING` goes from `claudecode/opus4_6` to `claudecode/opus4_7`
- `BRAINSTORM_AGENT_TYPES` in `brainstorm_crew.py` updates `explorer`,
  `synthesizer`, `detailer` (leave `comparator` and `patcher` on sonnet4_6)
- `crew_meta_template.yaml` mirrors the python change

### 3. Verify exact notes from official docs
Before applying, cross-check the `notes` string against Anthropic's official
docs for Opus 4.7. Update the invocation if Anthropic uses a different
canonical description. Candidate URLs (reuse from refresh-code-models):
- https://platform.claude.com/docs/en/about-claude/models/all-models
- https://platform.claude.com/docs/en/about-claude/models/overview

### 4. Apply for real
Drop `--dry-run` and re-run. The skill will commit changes per its commit
strategy (expect separate commits for metadata vs source).

### 5. Sanity checks
```
jq . aitasks/metadata/models_claudecode.json   # valid JSON
jq . aitasks/metadata/codeagent_config.json
jq . seed/models_claudecode.json
jq . seed/codeagent_config.json
bash tests/test_codeagent.sh                   # should still pass
bash tests/test_resolve_detected_agent.sh      # some assertions may need update in t579_4
bash tests/test_add_model.sh                   # should still pass
shellcheck .aitask-scripts/aitask_codeagent.sh
./ait codeagent --list-models claudecode | grep opus4_7  # confirm registered
```

Any FAIL in test_codeagent / test_resolve_detected_agent that references
`opus4_6` as the expected default is EXPECTED (resolved in t579_4). Document
failures in the plan's Final Implementation Notes for t579_4 to pick up.

### 6. Capture manual-review list
The skill emits a printed list of docs/tests that still reference the old
default. Copy that list verbatim into the plan file's Final Implementation
Notes section under "Manual review follow-ups for t579_4".

## Verification Steps

1. `aitasks/metadata/models_claudecode.json` contains opus4_7 with cli_id
   `claude-opus-4-7`
2. `aitasks/metadata/codeagent_config.json` shows `"pick": "claudecode/opus4_7"`
   and all other promoted ops
3. `.aitask-scripts/aitask_codeagent.sh` shows
   `DEFAULT_AGENT_STRING="claudecode/opus4_7"`
4. `seed/` files are in sync with `aitasks/metadata/`
5. `bash tests/test_add_model.sh` passes
6. No orphaned file changes beyond what the skill was expected to produce
7. Commit(s) follow the skill's commit strategy (documented in its SKILL.md)
   — expect at least 2 commits: one for metadata (`./ait git`) and one for
   source+seed (plain `git`). Task-aware commit messages all carry `(t579_3)`
   suffix per CLAUDE.md convention.

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 579_3`. Final
Implementation Notes MUST include:
- The manual-review list from the skill (for t579_4)
- Any test failures caused by the default change (expected for t579_4 fix)
- Exact `notes` string used for opus4_7 (for reference)
