---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [gates, claudeskills]
anchor: 635
followup_kind: risk_mitigation
created_at: 2026-08-07 15:50
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t635_23, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement "pointer stubs prove resolution, not agent behavior":

> The port's *purpose* is that a Codex or OpenCode agent can actually complete
> `aitask-gate-docs-updated` end-to-end. Pointer stubs make the file resolve, but
> nothing here proves the tool mapping carries the `AskUserQuestion` confirmation
> step or that the new whitelist entries are honoured in a live session — this is
> agent-driven behavior, not unit-testable · severity: medium

## Goal

t635_23 shipped the wrapper surfaces and verified them **statically only**
(existence, cross-tree parity, generated body content, policy strings,
golden/prerender freshness). Nothing was executed in Codex CLI or OpenCode.
**This MV is the acceptance condition for t635_23's end-to-end claim** — until it
passes, the verified claim is only "the wrapper surfaces exist, agree across
trees, and the helpers they invoke are permitted."

Drive `aitask-gate-docs-updated` end-to-end from a **live Codex CLI** session and
a **live OpenCode** session, on a scratch task declaring `gates: [docs_updated]`
(the gate ships dormant — declare it explicitly, do not add it to a profile's
`default_gates`). For each agent verify:

1. **Wrapper resolves.** The Step-8 dispatch's "resolve the gate's registry
   `verifier` to its `SKILL.md` in your agent's skill tree" finds
   `.agents/skills/aitask-gate-docs-updated/SKILL.md` (Codex) /
   `.opencode/skills/aitask-gate-docs-updated/SKILL.md` (OpenCode), and the agent
   follows the pointer through to the canonical Claude body.
2. **Tool mapping carries the confirmation step.** The skill's `AskUserQuestion`
   (apply / adjust / not-needed / reject) surfaces as a real prompt —
   `functions.request_user_input` under Codex, `ask` under OpenCode — per
   `.agents/skills/codex_tool_mapping.md` / `.opencode/skills/opencode_tool_mapping.md`.
   A silently-skipped confirmation is a FAIL: the gate's whole value rests on it.
3. **Helpers run unprompted.** `aitask_resolve_config_path.sh` (spec lookup) and
   `aitask_gate.sh` (begin-procedure / append) execute without a permission
   interruption under the entries t635_23 added to `.codex/rules/default.rules`
   and the OpenCode config. Note that touchpoint 7 is `seed/opencode_config.seed.json`
   — confirm the *installed* OpenCode config actually carries the entry, and if it
   does not, that is a finding worth its own follow-up.
4. **Terminal block lands.** `aitask_gate.sh append --only-if-running <run-id>`
   closes the running block with exactly one terminal entry, and
   `aitask_gate.sh archive-ready <id>` flips from `BLOCKED:docs_updated` to
   `ALL_PASS`.
5. **The skip path.** A change needing no docs records `skip` (not `pass`) and
   `archive-ready` is still `ALL_PASS`.

Also verify the `.opencode/commands/aitask-gate-docs-updated.md` slash-command
surface loads (it `@`-includes the canonical body), even though the gate is
normally reached via task-workflow dispatch rather than by the user typing it.

Record per-agent PASS/FAIL. A failure here means the wrapper layer is present but
the port is not functionally complete — file the gap as a follow-up rather than
loosening this checklist.
