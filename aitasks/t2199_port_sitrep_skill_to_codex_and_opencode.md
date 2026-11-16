---
priority: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [sitrep, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
created_at: 2026-11-04 15:26
updated_at: 2026-11-12 19:46
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2211_5** id=2026-11-10T13:59:33Z.101526605ec34cb5f70a079e from=t2211_5 from_verified=yes at=2026-11-10T13:59:33Z base=82f5351bc2f8459ec865315fcc4801818a47bc8d base_branch=main dirty=yes host=omg16
>
> | Advisory (a claim from t2211_5, code commit 82f5351bc, tree-relative): the sitrep skill surface your port verifies has changed.
> | 
> | - Step 0 no longer harvests or refreshes: the skill runs `aitask_sitrep.sh root`, then `aitask_sitrep_todo.sh list` + `read todo`, then greets. The sitrep TUI owns harvest/refresh (and dismiss/restore). Exit 4 now points the user to the TUI's `R` instead of running `restore`.
> | - Removed codes: `>s`, `>r`, `>x`. A non-code section "Done in the sitrep TUI, not here" names the TUI keys (`r`/`x`/`R`). The writing-verb list no longer has `dismiss` or `restore`.
> | - Kept codes, now with optional arguments in their headings: `>t [c<N>]`, `>w [<theme>]`, `>q [c<N>]`, `>tr [c<N>]`, `>p`, `>c`, `>?`. `>t c<N>` triages only that item (`aitask_sitrep.sh triage c<N>`) and still asks one confirmation.
> | - New section "Requests from the sitrep TUI": the TUI types `>t c<N>`, `>q c<N> <question>`, `>w <theme>`, `>tr c<N>`, `>p` into the agent; same authority as typed input; the agent re-reads `list` (+ `context c<N>`, or `read context` / `read todo` for `>w`) before each request.
> | - The skill no longer names `aitask_sitrep_harvest.sh` or `aitask_sitrep_refresh.sh`. Their entries in the 5 permission files were deliberately left in place (contract test (a) checks only the helpers the skill names), so your permission check needs no change for them.
> | - Your manual run's `>t` / `>q` steps still apply; the nested `/aitask-trail --refresh` (`>tr`) and `/aitask-backlog-roadmap --show` (`>p`) calls are unchanged.

> **👁 note:read** id=2026-11-12T17:46:10Z.75c59fc48ddda5140c2cdd16 by=t2199 at=2026-11-12T17:46:10Z mode=explicit ids=2026-11-10T13:59:33Z.101526605ec34cb5f70a079e

> **✉ note:t2299_4** id=2026-11-16T13:37:20Z.fc390967fa7da6b386739ae6 from=t2299_4 from_verified=yes at=2026-11-16T13:37:20Z base=5dada42e459e3fe0d6e7a1ae0621ba7a621a8a36 base_branch=main dirty=yes host=omg16
>
> | Advisory from t2299_4. Not an instruction. t2299_4 added crash-recovery sections to the Claude Code sitrep skill (.claude/skills/aitask-sitrep/SKILL.md.j2). The codex/opencode port of that skill should carry the same sections:
> | 
> | - "The list": a paragraph on crash-recovery items. They are kind=task with ref recover:t<N>. The outcome's leading word is the category (crashed / orphan / stale_lock). Each context has a SITREP_RECOVERY_SURVEY v1 capture, read like any other capture. Unknown liveness and other-host locks are never items. checked_at means "evidence last changed".
> | - "Writing": recovery items are written only by the crash detector and refresh, through recovery-apply, which is not an agent verb. The agent never runs add / set-state / upsert-context on a recover: item. A dismissal reopens only for a new claim.
> | - ">w": crashed-agents is a virtual theme, derived from recover: refs, because the detector writes no context theme. The "Requests from the sitrep TUI" >w check has a matching exception, and the TUI's w never types it.
> | - ">q": the one-hour age rule does not apply to recovery items.
> | - ">p": the resume-order tiers from the survey, the post_impl pending_gates, and the cleanup commands (ait lock --unlock <N> for stale locks, /aitask-pick <N>).
> | - "Guardrail": never reclaim, unlock or pick. Never suggest git restore / stash / checkout when the survey's warning: line is not none. Call out overlaps.
> | - Greeting and "Done in the sitrep TUI": the recovery-item count, and the crash check as part of the TUI's r.
> | 
> | The contract test (tests/test_sitrep_skill_contract.sh) forbids naming aitask_sitrep_harvest.sh or aitask_sitrep_refresh.sh in the skill, so the ported text must keep saying "the crash detector" rather than giving a script path.
