---
title: "Skill Templating and Dispatch"
linkTitle: "Skill Templating"
weight: 67
description: "How a profile-aware skill's stub renders and dispatches to its per-profile, per-agent variant, where stubs and variants live, and which variants are committed"
depth: [advanced]
---

A profile-aware skill is a stub that renders the variant of its template for the chosen execution profile and the running coding agent, then follows it; why skills work this way is on the [Skill templating]({{< relref "/docs/concepts/skill-templating" >}}) concept page, and how to choose the profile is in the [execution profiles reference]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}#profile-override-argument).

## The two pieces

A profile-aware skill such as `/aitask-pick` does not live in a single `SKILL.md`. It ships as two pieces:

- An authoring template at `.claude/skills/<skill>/SKILL.md.j2`, written in the minijinja template language.
- A small profile-agnostic **stub** on each agent's discovery surface, the place where that agent looks for the skills and commands it can run.

The template engine lets the same `.j2` source produce different flows for each execution profile, such as the shipped `default`, `fast` and `remote`.

## How dispatch works

1. The user types `/aitask-pick`.
2. The agent reads `.claude/skills/aitask-pick/SKILL.md`, the committed profile-agnostic stub.
3. The stub runs `./.aitask-scripts/aitask_skill_resolve_profile.sh pick`, or honors `--profile <name>` from the forwarded arguments. `pick` is the skill's short name, its name without the `aitask-` prefix.
4. The stub runs `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile <p> --agent claude`. The render walks the template's dependency closure: every `.md` procedure file the template reaches, directly or through other procedures. Each one is rendered into a sibling per-(profile, agent) directory, with cross-references rewritten so the rendered body points at the rendered procedures, not the source ones. The whole step does nothing when the rendered variant is already up to date.
5. The stub reads `.claude/skills/aitask-pick-<p>-/SKILL.md` and follows it exactly as if its instructions had been written inline.

The same flow runs on every supported coding agent; only the stub's discovery surface, the `--agent` value it passes and the rendered-variant directory differ.

The stub takes `--profile <name>` out of the forwarded arguments (`ARGUMENTS` in Claude Code and Codex, `$ARGUMENTS` in OpenCode) before dispatch, and forwards the remaining arguments to the rendered body.

## Per-agent surfaces

| Agent | Stub location | Rendered variant location |
|-------|---------------|---------------------------|
| Claude | `.claude/skills/<skill>/SKILL.md` | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| Codex | `.agents/skills/<skill>/SKILL.md` | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| OpenCode | `.opencode/commands/<skill>.md` | `.opencode/skills/<skill>-<profile>-/SKILL.md` |

Codex's rendered variants carry an extra `-codex-` segment because its skills root (`.agents/skills/`) can be read by more than one agent. The segment prevents collisions when two agents render into the same root. Claude and OpenCode keep the shorter `<skill>-<profile>-/` form.

## Rendered directories and `.gitignore`

Rendered directory names always end with a single trailing hyphen (`aitask-pick-fast-/`, `aitask-pick-fast-codex-/`). The hyphen marks a directory as generated, so every agent root needs only one `.gitignore` glob:

```
.claude/skills/*-/
.agents/skills/*-/
.opencode/skills/*-/
```

Authoring directory names (`aitask-pick/`, `task-workflow/`) must not end with `-`; that boundary is what keeps the single glob working. Rendered files are generated on demand; never edit them by hand or commit them. The exception is the `remote` variants of `aitask-pickrem` and `aitask-pickweb`, together with the `task-workflow` procedures they use: they ship pre-rendered for headless agent runs, and `.gitignore` negates them.

## Authoring

Profile-aware skills are authored in the framework repository; the authoring rules live in the engineering docs on [GitHub](https://github.com/beyondeye/aitasks/tree/main/aidocs):

- [`aidocs/framework/stub-skill-pattern.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/stub-skill-pattern.md): canonical stub bodies, the per-agent surface table, the argument-forwarding contract, reference resolution rules and template-completeness checks.
- [`aidocs/framework/skill_authoring_conventions.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/skill_authoring_conventions.md): Jinja conventions (comment markers, macros, `{% from %}` imports, whitespace control, minijinja caveats including `{% raw %}`), what the verify script checks, golden regeneration, and the NON-SKIPPABLE banner rule.
- [`aidocs/framework/agent_runtime_guards_audit.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/agent_runtime_guards_audit.md): where `{% if agent %}` gates are used today and the remaining "If running in Claude Code" guards that could move to them.
