---
Task: t579_3_add_opus_4_7_as_new_default_using_add_model_skill.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_4_update_tests_and_docs_for_opus_4_7.md
Archived Sibling Plans: aiplans/archived/p579/p579_1_audit_refresh_code_models_and_design_add_model_skill.md, aiplans/archived/p579/p579_2_implement_aitask_add_model_skill.md, aiplans/archived/p579/p579_5_externalize_model_defaults.md
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-17 09:23
---

# Plan: t579_3 — Add Opus 4.7 as new default via aitask-add-model (verified)

## Context

Third of 4 children for t579. Exercises the `aitask-add-model` helper
from t579_2 to register Opus 4.7 variants and promote the 1M context
variant to default for pick/explore/brainstorm-opus operations.

**Two variants to register:**
1. `opus4_7` / `claude-opus-4-7` — standard Opus 4.7
2. `opus4_7_1m` / `claude-opus-4-7[1m]` — 1M context variant (**promoted as default**)

The `[1m]` suffix is a Claude Code client-side signal for 1M token context.
The API model ID is always `claude-opus-4-7`; Claude Code strips `[1m]` before
sending to the provider.

## Verification findings

Existing plan checked against current codebase. Corrections:

1. **Two models instead of one:** Original plan registered only `opus4_7`.
   Updated to register both standard and 1M variants, with 1M promoted.

2. **Stale file expectations:** t579_5 externalized brainstorm defaults to
   config. `brainstorm_crew.py` and `crew_meta_template.yaml` (deleted) are
   NOT touched by the skill. Expected: 5 files per model operation.

3. **Invocation method:** Call `.aitask-scripts/aitask_add_model.sh`
   subcommands directly (not `/aitask-add-model`) since we're inside pick.

All other assumptions hold:
- All t579_2 deliverables in place (skill, helper, test)
- Neither `opus4_7` nor `opus4_7_1m` in `models_claudecode.json`
- `DEFAULT_AGENT_STRING="claudecode/opus4_6"` at line 21
- All 5 target ops point to `opus4_6`
- `validate_cli_id()` only checks non-empty — `[1m]` suffix passes
- `opus4_7_1m` matches name regex `^[a-z][a-z0-9_]*$`

## Step 1 — Precondition check

```bash
test -f .claude/skills/aitask-add-model/SKILL.md
test -x .aitask-scripts/aitask_add_model.sh
bash tests/test_add_model.sh   # must pass
```

## Step 2 — Register standard variant (opus4_7)

Add-only, no promotion:

```bash
# Dry-run first
./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
  --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 \
  --notes "<notes for standard variant>"

# Apply
./.aitask-scripts/aitask_add_model.sh add-json \
  --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 \
  --notes "<notes for standard variant>"
```

## Step 3 — Register 1M variant and promote (opus4_7_1m)

Add + promote as default:

```bash
# Dry-run all 3 subcommands
./.aitask-scripts/aitask_add_model.sh add-json --dry-run \
  --agent claudecode --name opus4_7_1m --cli-id "claude-opus-4-7[1m]" \
  --notes "<notes for 1M variant>"

./.aitask-scripts/aitask_add_model.sh promote-config --dry-run \
  --agent claudecode --name opus4_7_1m \
  --ops pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer

./.aitask-scripts/aitask_add_model.sh promote-default-agent-string --dry-run \
  --agent claudecode --name opus4_7_1m

# Apply all 3
./.aitask-scripts/aitask_add_model.sh add-json \
  --agent claudecode --name opus4_7_1m --cli-id "claude-opus-4-7[1m]" \
  --notes "<notes for 1M variant>"

./.aitask-scripts/aitask_add_model.sh promote-config \
  --agent claudecode --name opus4_7_1m \
  --ops pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer

./.aitask-scripts/aitask_add_model.sh promote-default-agent-string \
  --agent claudecode --name opus4_7_1m
```

Expected state after apply:
- `models_claudecode.json` has both `opus4_7` and `opus4_7_1m` entries
- `codeagent_config.json` defaults: 5 ops → `claudecode/opus4_7_1m`
- `DEFAULT_AGENT_STRING="claudecode/opus4_7_1m"`
- Seed files synced

## Step 4 — Verify notes from official docs

Cross-check notes against Anthropic's official docs before applying.
Candidates:
- opus4_7: "Most intelligent model, 200K context, adaptive thinking"
- opus4_7_1m: "Most intelligent model, 1M extended context, adaptive thinking"

## Step 5 — Sanity checks

```bash
jq . aitasks/metadata/models_claudecode.json > /dev/null
jq . aitasks/metadata/codeagent_config.json > /dev/null
jq . seed/models_claudecode.json > /dev/null
jq . seed/codeagent_config.json > /dev/null
grep -n 'DEFAULT_AGENT_STRING=' .aitask-scripts/aitask_codeagent.sh
bash tests/test_add_model.sh
bash tests/test_codeagent.sh            # may fail (t579_4 scope)
shellcheck .aitask-scripts/aitask_codeagent.sh
./ait codeagent --list-models claudecode | grep -i opus4_7
```

## Commit strategy (Step 8)

3 separate commits per SKILL.md convention:

1. **Metadata (./ait git):**
   ```bash
   ./ait git add aitasks/metadata/models_claudecode.json aitasks/metadata/codeagent_config.json
   ./ait git commit -m "ait: Register claudecode/opus4_7 + opus4_7_1m and promote 1m to default"
   ```

2. **Seed sync (git):**
   ```bash
   git add seed/models_claudecode.json seed/codeagent_config.json
   git commit -m "ait: Sync claudecode/opus4_7 registration to seed (t579_3)"
   ```

3. **DEFAULT_AGENT_STRING (git):**
   ```bash
   git add .aitask-scripts/aitask_codeagent.sh
   git commit -m "refactor: Promote claudecode/opus4_7_1m as hardcoded DEFAULT_AGENT_STRING (t579_3)"
   ```

## Step 6 — Capture manual-review list

Record in Final Implementation Notes:
- Manual-review list from SKILL.md Step 5
- Test failures (expected for t579_4)
- Exact notes strings used for both variants
- Commit hashes

## Final Implementation Notes

- **Actual work done:** Registered two Opus 4.7 variants in `models_claudecode.json` (+ seed sync): `opus4_7` (standard, `claude-opus-4-7`) and `opus4_7_1m` (1M context, `claude-opus-4-7[1m]`). Promoted `opus4_7_1m` to default for 5 ops (pick, explore, brainstorm-explorer, brainstorm-synthesizer, brainstorm-detailer) in `codeagent_config.json` and `DEFAULT_AGENT_STRING`.
- **Deviations from original plan:** Original task planned a single `opus4_7` model. Updated during verification to register two variants (standard + 1M) per user input. The `[1m]` suffix is a Claude Code client-side signal stripped before API calls. Also corrected stale file expectations — `brainstorm_crew.py` and `crew_meta_template.yaml` are NOT touched (t579_5 externalized those).
- **Issues encountered:**
  - `test_codeagent.sh` fails with a **pre-existing bug** (not caused by this task): `setup_test_env()` at line 73 doesn't copy `archive_utils.sh` which `task_utils.sh` now sources. This breaks the test even on clean main. t579_4 should fix this alongside the expected default-change assertion updates.
  - `./ait codeagent --list-models` syntax is wrong — correct syntax is `./ait codeagent list-models` (no `--` prefix on subcommand).
- **Key decisions:** Used `opus4_7_1m` as the promoted default (not `opus4_7`) because the 1M context variant is preferred for agentic workflows. Standard variant registered for users who want explicit non-1M context.
- **Exact notes strings used:**
  - `opus4_7`: "Most capable model, complex reasoning + agentic coding, 128K output, adaptive thinking"
  - `opus4_7_1m`: "Most capable model, 1M context, complex reasoning + agentic coding, 128K output, adaptive thinking"
- **Notes for sibling tasks:**
  - **t579_4** must fix `tests/test_codeagent.sh` setup: add `cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"` after line 75. Then update default-change assertions (opus4_6 → opus4_7_1m for promoted ops).
  - `tests/test_resolve_detected_agent.sh` needs a mapping test for `claude-opus-4-7 → claudecode/opus4_7` AND `claude-opus-4-7[1m] → claudecode/opus4_7_1m` (if the resolve script handles `[1m]` suffix).
  - Update `aidocs/claudecode_tools.md:5` to reference Opus 4.7.

### Manual review follow-ups for t579_4

```
Manual review needed — the following files reference the default model
string but are NOT patched by this skill:

  - aidocs/claudecode_tools.md:5         (display name + cli_id)
  - tests/test_codeagent.sh              (model-resolution assertions + setup bug)
  - tests/test_brainstorm_crew.py        (default agent_string fixtures)
  - website/content/docs/commands/codeagent.md  (user-facing docs)

Full audit: aidocs/model_reference_locations.md
```

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 579_3`.
