---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [framework, codeagent]
created_at: 2026-05-29 09:31
updated_at: 2026-05-29 09:31
---

## Problem

The `aitask-add-model` skill's promote mode is broken. The helper
`./.aitask-scripts/aitask_add_model.sh` subcommand
`promote-default-agent-string` patches `DEFAULT_AGENT_STRING` in
`.aitask-scripts/aitask_codeagent.sh`, anchored on `^DEFAULT_AGENT_STRING="..."`
(see `aitask_add_model.sh:239` `src_rel=".aitask-scripts/aitask_codeagent.sh"`
and the sed at lines 249-252).

That variable has since been **extracted into `.aitask-scripts/lib/agent_string.sh`**
(`DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7_1m}"` at
line 26). `aitask_codeagent.sh` now only *sources* it (lines 17-18). So the
anchor pattern `^DEFAULT_AGENT_STRING="..."` no longer matches in the targeted
file and the subcommand dies with "anchor pattern did not match".

This blocks promoting any newly-added model to the framework default — it must
be fixed before Opus 4.8 can be promoted.

## Scope

1. Retarget `promote-default-agent-string` in `aitask_add_model.sh` to patch
   `.aitask-scripts/lib/agent_string.sh`. Note the live form there uses the
   parameter-expansion default `DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-<value>}"`,
   so the sed anchor/replacement must match that shape (not a bare
   `DEFAULT_AGENT_STRING="..."`). Verify the post-write grep check is updated
   to match the new form.
2. Confirm the secondary sed for the resolution-chain note
   (`4. Hardcoded default: ...`) still has a valid anchor — that comment lives
   in `aitask_codeagent.sh` (around line 540), so it may need to stay targeting
   `aitask_codeagent.sh` while the variable patch moves. Handle the two files
   independently if needed.
3. Update the `aitask-add-model` SKILL.md (`.claude/skills/aitask-add-model/SKILL.md`)
   wherever it states the variable lives in `aitask_codeagent.sh`.
4. Update the audit doc `aidocs/model_reference_locations.md` (section 3,
   "Hardcoded source-code defaults") to point at `lib/agent_string.sh`.
5. Update `tests/test_add_model.sh` so the promote-default-agent-string group
   asserts against `lib/agent_string.sh`.

## Verification

- `bash tests/test_add_model.sh` passes.
- `./.aitask-scripts/aitask_add_model.sh promote-default-agent-string --dry-run --agent claudecode --name opus4_7_1m` produces a clean diff against `lib/agent_string.sh` instead of dying.
- `shellcheck .aitask-scripts/aitask_add_model.sh`.

This is framework-internal (lives on `main`); per CLAUDE.md, suggest follow-up
tasks to port the equivalent SKILL.md note to Codex/OpenCode skill trees if they
duplicate this guidance.
