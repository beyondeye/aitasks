---
priority: low
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [sitrep, codeagent]
gates: [risk_evaluated]
anchor: 2175
created_at: 2026-11-04 15:26
updated_at: 2026-11-04 15:26
---

## Context

t2175_4 (commit bdef300b0) added the sitrep skill `/aitask-sitrep` and `ait sitrep`, Claude Code first per CLAUDE.md. The skill already RENDERS for every agent: the template `.claude/skills/aitask-sitrep/SKILL.md.j2` has no agent gate, and the codex / opencode stubs exist (`.agents/skills/aitask-sitrep/SKILL.md`, `.opencode/skills/aitask-sitrep/SKILL.md`, `.opencode/commands/aitask-sitrep.md`), because `aitask_skill_verify.sh` requires all four surfaces. What is NOT done is verifying and enabling the skill's run on codex and opencode: the `sitrep` codeagent operation fails closed for them.

## Scope

1. `.aitask-scripts/aitask_codeagent.sh`: lift the `sitrep` Claude-only gate (beside `explore-relay`'s), add the codex arm (`build_skill_prompt "\$aitask-sitrep"`) and the opencode arm (`--prompt "/aitask-sitrep"`), like `explore` (no arguments).
2. `tests/test_codeagent_op_wiring.sh`: drop `sitrep` from `EXEMPT_OPS`; `tests/test_codeagent.sh` Test 11d5: replace the refusal checks with the composed prompts (and add sitrep to the 11d3 codex matrix if it carries an argument shape there).
3. Verify the rendered skill on each agent, end to end in a scratch repo:
   - nested skill calls: `/aitask-trail --refresh <handle>` and `/aitask-backlog-roadmap --show` (codex uses `$aitask-…` invocations; check how a skill invokes another skill there, and adapt the template only through the existing per-agent tool-mapping files — keep the entry template agent-invariant, Test 1b of `tests/test_skill_render_aitask_sitrep.sh`);
   - the one-confirmation triage prompt (AskUserQuestion equivalent: `.opencode/skills/opencode_tool_mapping.md`, codex `default_mode_request_user_input`);
   - quoted-heredoc writer calls and the permission entries (`.codex/rules/default.rules`, `seed/opencode_config.seed.json` already carry the sitrep helpers).
4. Docs: `website/content/docs/commands/codeagent.md` Operations row (drop "Claude Code only"), `website/content/docs/workflows/sitrep.md` and `skills/aitask-sitrep.md` ("currently runs on Claude Code"), `aidocs/framework/sitrep.md` "Code agents" section.

## Reference

- `aidocs/framework/sitrep.md` (whole feature), `aidocs/framework/adding_a_new_codeagent.md`, `aidocs/framework/skill_authoring_conventions.md`.
- Harvest heuristics are already tuned for Claude Code captures; t2182 covers other agents' captures.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_op_wiring.sh`, `bash tests/test_skill_render_aitask_sitrep.sh`, `bash tests/test_sitrep_skill_contract.sh`, `./.aitask-scripts/aitask_skill_verify.sh`.
- A manual run of `ait codeagent --agent-string <codex|opencode agent> invoke sitrep` in a scratch repo with a harvested wrap-up: greeting, `>t` with one confirmation, a written watch, `>q` with a logged Q&A.
