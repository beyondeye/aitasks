---
Task: t1868_fix_add_model_manual_review_block.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1868 — Fix aitask-add-model Step 5 "Manual review needed" block

## Context

t1865 (promote `claudecode/opus5_5`) found that the promote-mode reminder block in
`.claude/skills/aitask-add-model/SKILL.md` (Step 5, lines ~117-128) has drifted:

- It names `tests/test_brainstorm_crew.py`, which writes its own fixture config
  into a tmpdir and never reads the shipped defaults — not promote-sensitive.
- It omits `.aitask-scripts/lib/roadmap_run.py` (hardcoded `agent_string=` default
  at the `run()` signature and the `--agent-string` argparse default — not patched
  by `promote-default-agent-string`), and
  `website/content/docs/tuis/syncer/_index.md` (matrix-cell examples literally
  showing the current default model).
- `tests/test_codeagent.sh` now derives its default expectations from
  `seed/codeagent_config.json` (t1865, t1318 idiom), so it should pass unedited
  after a promotion; its entry should say "re-run", not "edit assertions".

Scope decisions:
- `aidocs/framework/model_reference_locations.md` is owned by **t1341** (Ready,
  already noted with these findings) — not touched here.
- Replacing the block with a pure pointer is **not** chosen: the audit doc it
  would point at is itself stale (still tags `test_brainstorm_crew.py`, lists
  `aitask_brainstorm_init.sh`), so a pointer-only block would currently be worse.
  Keep the short list + pointer line. Revisit once t1341 lands (the task body's
  Coordination section already says so).
- Codex/OpenCode trees (`.agents/skills/aitask-add-model/SKILL.md`,
  `.opencode/skills/aitask-add-model/SKILL.md`) are pointer wrappers that defer to
  the Claude file — no port tasks needed. No `.j2`/golden/test copies of the
  block exist (grep for "Manual review needed" hits only this file).

## Change — `.claude/skills/aitask-add-model/SKILL.md` Step 5 block

Replace the fenced block body with an agent-split list. Promote mode accepts any
agent, but `promote-default-agent-string` is claudecode-only (Step 4), and the
Claude-specific files track the claudecode default/fallback — a Codex/OpenCode
promotion changes none of them.

```
Manual review needed — the following files reference the default model
string but are NOT patched by this skill:

  Any promoted agent:
  - website/content/docs/commands/codeagent.md  (operational-defaults table)
  - website/content/docs/tuis/codebrowser/how-to.md  (states the qa default —
                                                 only when qa is promoted)

  claudecode promotions only:
  - aidocs/codeagents/claudecode_tools.md:5     (display name + cli_id)
  - .aitask-scripts/lib/roadmap_run.py          (run() agent_string default
                                                 + --agent-string argparse default)
  - website/content/docs/tuis/syncer/_index.md  (matrix-cell examples of the
                                                 built-in fallback)

Re-run (should pass unedited — both derive defaults from seed/codeagent_config.json):
  - tests/test_codeagent.sh
  - tests/test_codeagent_work_report.sh

Broader audit: aidocs/framework/model_reference_locations.md — currently
stale; where it disagrees with this list, this list is authoritative.
```

**Single printing rule** — replace the intro sentence "print the following block
verbatim" with one rule that covers both conditions:

> After a successful promote-mode apply, print the block below, dropping lines
> that do not apply to this promotion:
> - drop the whole `claudecode promotions only` group unless the promoted agent
>   is `claudecode`;
> - drop the `codebrowser/how-to.md` line unless `qa` is among the promote-ops.
>
> Print everything else verbatim.

This is the only statement of the rule; the block itself carries only the
`(only when qa is promoted)` hint inline as a label, not as a second rule.

After committing, send an `ait note` to t1341: when its doc refresh lands, drop
the "currently stale" qualifier on the audit line in
`.claude/skills/aitask-add-model/SKILL.md` Step 5 and re-check the list against
the refreshed `needed_for_promote` set. (t1341 is the owner of that doc; this
does not take over its work.)

**Completeness basis for the "authoritative" claim** — full-repo `git grep` for
the current default literals (`opus5_5`, `opus-5-5`, `sonnet5`, `claude-sonnet-5`),
excluding task/plan files, classified:
- patched by the skill: `seed/codeagent_config.json`, `seed/models_claudecode.json`,
  `lib/agent_string.sh`, `aitask_codeagent.sh`
- listed above: `codeagent.md`, `codebrowser/how-to.md`, `syncer/_index.md`,
  `claudecode_tools.md`, `roadmap_run.py`, `test_codeagent.sh`,
  `test_codeagent_work_report.sh`
- not promote-sensitive (registered model names used as fixtures, or their own
  tmpdir config): `test_brainstorm_crew.py`, `test_agent_freeze.py`,
  `test_cross_repo_*.py`, `test_launch_agent_string_env.py`,
  `test_pick_launch_argv.py`, `tests/lib/branch_mode_repo.py`,
  `claudecode_builtin_prompts.md` (no default claim)
- older illustrative examples (`opus4_6`/`sonnet4_6` in crew.md and the
  agentcrew/brainstorm design docs) are not claims about the current default.

## Verification

- `grep -n "test_brainstorm_crew" .claude/skills/aitask-add-model/SKILL.md` → no hits.
- `grep -n "roadmap_run.py\|syncer/_index.md\|test_codeagent.sh" .claude/skills/aitask-add-model/SKILL.md` → hits in the block.
- Read the edited Step 5 and walk the single rule through four cases, confirming
  the printed set for each:
  - claudecode + qa in promote-ops → all lines
  - claudecode, no qa → everything except `how-to.md`
  - codex + qa → the any-agent group (with `how-to.md`), re-run group, audit line; no claudecode group
  - codex, no qa → `codeagent.md`, re-run group, audit line only
- `grep -c "verbatim" ` on the Step 5 section: the intro states one rule, and no
  second contradicting "verbatim" instruction remains.
- The audit line carries the stale qualifier.
- `bash tests/test_codeagent_work_report.sh` passes
- `bash tests/test_codeagent.sh` passes (confirms the "unedited" claim).
- No `.j2` edited → `aitask_skill_verify.sh` not required; run it anyway as a cheap check.

## Step 9

Post-implementation: commit (`bug: ... (t1868)`), archive via Step 9.

## Risk

### Code-health risk: low
None identified. Single prose block in one skill file; no code, template, golden, or test consumer.

### Goal-achievement risk: low
- The block remains a hand-maintained copy of the audit doc's promote set and can drift again · severity: low · → mitigation: none spawned — t1341 owns the doc refresh; the ait note sent after commit tells it to remove the stale qualifier and re-check the list.
- The "stale" qualifier outlives t1341 if the note is ignored · severity: low · → mitigation: the note itself (durable, surfaced on t1341's pick).

## Post-Review Changes

### Change Request 1 (2026-09-23 17:10)
- **Requested by user:** the "should pass unedited" wording is false today — `tests/test_codeagent.sh` exits 1 at Test 11e for an unrelated reason. Say promotion-specific default assertions should need no edits, but ask users to re-run and inspect failures.
- **Changes made:** reworded the re-run group header in the Step 5 block accordingly.
- **Files affected:** `.claude/skills/aitask-add-model/SKILL.md`

## Final Implementation Notes
- **Actual work done:** Rewrote Step 5 of `.claude/skills/aitask-add-model/SKILL.md`: one printing rule (drop the claudecode-only group unless `--agent claudecode`; drop the `codebrowser/how-to.md` line unless `qa` is promoted); agent-split list (any-agent: `codeagent.md`, `codebrowser/how-to.md`; claudecode-only: `claudecode_tools.md:5`, `roadmap_run.py`, `syncer/_index.md`); `test_brainstorm_crew.py` removed; re-run group for `test_codeagent.sh` + `test_codeagent_work_report.sh`; audit pointer qualified as stale with this list authoritative.
- **Deviations from plan:** Dropped the inline "(only when qa is promoted)" label from the `how-to.md` line — the single printing rule already governs it, so the label would be a second copy of the rule. Re-run wording softened after review (Change Request 1).
- **Issues encountered:** `tests/test_codeagent.sh` exits 1 at Test 11e (unrelated to this prose change; see upstream defects). `test_codeagent_work_report.sh` 28/28; `aitask_skill_verify.sh` OK.
- **Key decisions:** Kept a short hand-maintained list plus a qualified pointer rather than a pointer-only block, because the audit doc (owned by t1341) is itself stale. t1341 to be noted to drop the "currently stale" qualifier when its refresh lands. Codex/OpenCode `aitask-add-model` skills are pointer wrappers — no port tasks.
- **Upstream defects identified:**
  - `tests/test_codeagent.sh:353` — Test 11e loops over `opencode/openai_gpt_5_2`, which commit 2d9db16ab (t1867) flipped to `"status": "unavailable"` in `seed/models_opencode.json`; `aitask_codeagent.sh` now refuses it and the file aborts under `set -e` before its remaining tests run.
