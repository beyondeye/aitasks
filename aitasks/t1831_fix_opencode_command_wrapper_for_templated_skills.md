---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [skills, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1823
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-17 15:25
updated_at: 2026-09-17 22:19
---

## Origin

Spawned from t1823_2 during Step 8b review.

## Upstream defect

- .aitask-scripts/aitask_audit_wrappers.sh:357 (render_opencode_command) — `apply-wrapper opencode-command` generates the legacy static `@`-include command instead of the profile-aware stub (unlike the agents/opencode-skill renderers, it has no `_skill_is_templated` branch), so a new profile-aware skill gets a non-dispatching OpenCode command unless hand-fixed

## Diagnostic context

While adding the profile-aware `aitask-brainstorm-discuss` skill (stub + `SKILL.md.j2`), the three non-Claude surfaces were generated with
`./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper {agents,opencode-skill,opencode-command} aitask-brainstorm-discuss`.
The `agents` and `opencode-skill` outputs were correct profile-aware stubs: `render_agents_skill` and the OpenCode skill renderer branch on `_skill_is_templated` (`aitask_audit_wrappers.sh:245`, a `SKILL.md.j2` exists). `render_opencode_command` (:357-372) has no such branch and always emits:

```
@.opencode/skills/opencode_tool_mapping.md
Execute the following Claude Code skill. ...
Arguments: $ARGUMENTS
@.claude/skills/<skill>/SKILL.md
```

For a templated skill that `@`-includes the *Claude* stub, which tells the agent to render with `--agent claude` and read `.claude/skills/<skill>-<profile>-/SKILL.md` — the wrong agent's variant. The committed profile-aware commands (`.opencode/commands/aitask-shadow.md`, `aitask-trail.md`) have a different shape: `@.opencode/skills/opencode_planmode_prereqs.md` + `@.opencode/skills/opencode_tool_mapping.md`, a 3-step stub resolving `aitask_skill_resolve_profile.sh <key>`, rendering with `--agent opencode`, and reading `.opencode/skills/<skill>-<profile>-/SKILL.md` with `$ARGUMENTS`. t1823_2 hand-wrote `.opencode/commands/aitask-brainstorm-discuss.md` to that shape (pinned by Test 5 of `tests/test_skill_render_aitask_brainstorm_discuss.sh`).

`aitask_skill_verify.sh` and `test_opencode_skill_legacy_pointers.sh` both passed with the hand-written file; whether either would have caught the generated legacy form was not checked.

## Suggested fix

Add a `_skill_is_templated` branch to `render_opencode_command` emitting the shadow/trail command-stub shape (resolver key `${skill#aitask-}`), and a test that renders `render-wrapper opencode-command <templated skill>` and diffs it against a committed profile-aware command (e.g. aitask-shadow). Also check whether `aitask_skill_verify.sh`'s stub-surface check rejects the legacy form for a templated skill.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T19:19:30Z status=pass attempt=1 type=human
