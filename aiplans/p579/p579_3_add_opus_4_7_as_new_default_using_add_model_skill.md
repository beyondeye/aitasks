---
Task: t579_3_add_opus_4_7_as_new_default_using_add_model_skill.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_1_*.md, aitasks/t579/t579_2_*.md, aitasks/t579/t579_4_*.md
Archived Sibling Plans: aiplans/archived/p579/p579_*_*.md
Worktree: aiwork/t579_3_add_opus_4_7_as_new_default_using_add_model_skill
Branch: aitask/t579_3_add_opus_4_7_as_new_default_using_add_model_skill
Base branch: main
---

# Plan: t579_3 — Add Opus 4.7 as new default via aitask-add-model

## Context

Third of 4 children for t579. Exercises the `aitask-add-model --promote` skill
from t579_2 to register opus4_7 and promote it to default for pick/explore/
brainstorm-opus operations.

This task is the end-to-end validation that the skill works on a real vendor
model. Any file the skill leaves unchanged is (a) intentional (docs/tests go
to t579_4) or (b) a bug in the skill — do NOT hand-patch.

Read first:
- Parent plan: `aiplans/p579_support_for_opus_4_7.md`
- Archived sibling plans: `aiplans/archived/p579/p579_1_*.md`, `p579_2_*.md`
  — especially t579_2's Final Implementation Notes (exact skill API)

## Step 1 — Precondition check

Confirm t579_2 deliverables are in place:

```bash
test -f .claude/skills/aitask-add-model/SKILL.md || echo "MISSING SKILL"
test -x .aitask-scripts/aitask_add_model.sh || echo "MISSING HELPER"
bash tests/test_add_model.sh  # must pass
```

If any precondition fails, do NOT hand-patch — report the gap and pause until
t579_2 is fixed.

## Step 2 — Dry-run

```bash
/aitask-add-model --dry-run --promote \
  --agent claudecode \
  --name opus4_7 \
  --cli-id claude-opus-4-7 \
  --notes "Most intelligent Claude model, successor to opus4_6" \
  --promote-ops pick,explore,brainstorm-explorer,brainstorm-synthesizer,brainstorm-detailer
```

Review every diff. Expected file set:
- `aitasks/metadata/models_claudecode.json` — new `opus4_7` entry
- `seed/models_claudecode.json` — synced
- `aitasks/metadata/codeagent_config.json` — 5 ops updated
- `seed/codeagent_config.json` — synced
- `.aitask-scripts/aitask_codeagent.sh` — `DEFAULT_AGENT_STRING`
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — explorer/synthesizer/
  detailer updated, comparator/patcher unchanged
- `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml` — matching
  updates

If the diff contains unexpected files, stop and investigate (likely a skill
bug).

## Step 3 — Verify canonical notes

Before applying, cross-check the `notes` string against Anthropic's latest
official docs for Opus 4.7. Update the invocation if the canonical wording
differs. Candidate URLs:
- `https://platform.claude.com/docs/en/about-claude/models/all-models`
- `https://platform.claude.com/docs/en/about-claude/models/overview`

Record the chosen `notes` value in the plan's Final Implementation Notes.

## Step 4 — Apply

Drop `--dry-run` and re-run the same command. The skill commits changes per
its own strategy (expect at least 2 commits).

## Step 5 — Sanity checks

```bash
jq . aitasks/metadata/models_claudecode.json > /dev/null
jq . aitasks/metadata/codeagent_config.json > /dev/null
jq . seed/models_claudecode.json > /dev/null
jq . seed/codeagent_config.json > /dev/null

grep -n 'DEFAULT_AGENT_STRING=' .aitask-scripts/aitask_codeagent.sh
# expect: DEFAULT_AGENT_STRING="claudecode/opus4_7"

bash tests/test_add_model.sh                          # must pass
bash tests/test_codeagent.sh                          # may fail in t579_4 scope
bash tests/test_resolve_detected_agent.sh             # may fail in t579_4 scope
shellcheck .aitask-scripts/aitask_codeagent.sh .aitask-scripts/aitask_add_model.sh
./ait codeagent --list-models claudecode | grep -i opus4_7
```

## Step 6 — Capture manual-review list

Copy the manual-review list printed by the skill into the plan's Final
Implementation Notes, under a heading `Manual review follow-ups for t579_4`.
Also record:
- Exact `notes` string chosen for opus4_7
- Which tests failed (expected in t579_4) and how (exact assertion that broke)
- Commit hashes produced by the skill

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 579_3`. Final Implementation
Notes are critical — they drive t579_4.
