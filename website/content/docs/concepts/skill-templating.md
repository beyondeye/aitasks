---
title: "Skill templating and per-profile dispatch"
linkTitle: "Skill templating"
weight: 65
description: "How profile-aware skills materialize per-(skill, profile, agent) variants on demand via templated dispatch."
depth: [intermediate]
---

## What it is

A **profile-aware skill** like `/aitask-pick` does not live in a single
`SKILL.md`. Instead it ships as two pieces:

- An authoring template at `.claude/skills/<skill>/SKILL.md.j2`.
- A small profile-agnostic **stub** at each agent's discovery surface.

When the user invokes the slash command, the stub resolves the active
[execution profile]({{< relref "/docs/concepts/execution-profiles" >}}),
renders a per-(skill, profile, agent) variant on demand into a stable
filesystem location, and reads it back to follow as the actual skill body.

## Why it exists

`SKILL.md` files are re-read by the agent throughout a skill's execution, not
just once at slash-command expansion. Mutating an in-use `SKILL.md`
mid-session produces torn reads and inconsistent behavior, so the body cannot
be rewritten in place per profile. The stub + render-on-invocation model
materializes a stable per-(skill, profile, agent) snapshot once per
invocation, then the agent reads that frozen file.

The template engine (minijinja) lets the same source `.j2` produce different
flows for the `default`, `fast`, and `remote` profiles — branches that
would otherwise be a tangle of "if your profile sets X, skip this step"
prose inside one shared body.

## Invocation paths

### From inside an agent session

```
/aitask-pick --profile fast 42
```

The stub parses `--profile <name>` out of the forwarded arguments (
`ARGUMENTS` in Claude / Codex, `{{args}}` in Gemini, `$ARGUMENTS` in OpenCode),
strips it before dispatch, and forwards the remaining args (`42`) to the
rendered body. If `--profile` is absent the stub falls back to:

1. `userconfig.yaml` → `default_profiles.<short_name>` (personal)
2. `project_config.yaml` → `default_profiles.<short_name>` (team)
3. Interactive selection.

### From the shell

```
ait skillrun pick --profile fast 42
```

`ait skillrun` launches the resolved code agent with the slash command
pre-loaded. The default agent comes from `$AIT_AGENT_STRING` or
`$DEFAULT_AGENT_STRING`; override with `--agent-string <agent>/<model>`.

`--profile-override <yaml|->` merges an ad-hoc YAML on top of the resolved
profile. In live mode the merged YAML is written to
`aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` (gitignored) and
the agent receives `--profile _skillrun_<unique>`; the tempfile is deleted
on exit. `--dry-run` previews the launch command without invoking the
agent.

### From the launch dialog (TUI)

In `ait board` or `ait codeagent`, the `AgentCommandScreen` carries a
**Profile** row with `(E)dit`. The editor opens the same
`ProfileEditScreen` used by `ait settings`, plus a second save mode for
one-shot overrides:

- **Save persistently** writes to
  `aitasks/metadata/profiles/local/<name>.yaml`. This is the user-layer
  override (gitignored), and it shadows any same-name project profile for
  future runs.
- **Save as one-shot** writes
  `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` and rewrites the
  launch command to `--profile _skillrun_<unique>`. Same mechanism as
  `ait skillrun --profile-override`; the file is best-effort pruned (≥1
  hour old) at TUI startup.

## How dispatch works

1. The user types `/aitask-pick`.
2. The agent reads `.claude/skills/aitask-pick/SKILL.md` — the committed
   profile-agnostic stub.
3. The stub runs `./.aitask-scripts/aitask_skill_resolve_profile.sh pick`
   (or honors `--profile <name>` from the forwarded arguments).
4. The stub runs
   `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile <p> --agent claude`.
   The render walks the template's full dep closure — every transitively
   reachable `.md` is rendered into a sibling per-(profile, agent)
   directory, with cross-references rewritten so the rendered body points at
   the rendered procedures, not the source ones. The whole step is a no-op
   when the rendered variant is already fresh.
5. The stub reads `.claude/skills/aitask-pick-<p>-/SKILL.md` and follows it
   exactly as if its instructions had been written inline.

The same flow runs on every supported code agent — only the stub's
discovery surface and the rendered-variant directory differ.

## Per-agent surfaces

| Agent | Stub location | Rendered variant location |
|-------|---------------|---------------------------|
| Claude | `.claude/skills/<skill>/SKILL.md` | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| Codex | `.agents/skills/<skill>/SKILL.md` | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| Gemini | `.gemini/commands/<skill>.toml` (`prompt` field) | `.gemini/skills/<skill>-<profile>-/SKILL.md` |
| OpenCode | `.opencode/commands/<skill>.md` | `.opencode/skills/<skill>-<profile>-/SKILL.md` |

Codex's rendered variants carry an extra `-codex-` segment because its
physical skills root (`.agents/skills/`) is shared with a future agent
(`agy`); the segment prevents collisions when two agents render into the
same root. Claude / Gemini / OpenCode keep the simpler `<skill>-<profile>-/`
form. The framework decides per agent via the `agent_shared_skills_root`
predicate.

## Rendered dirs and `.gitignore`

Rendered directory names always end with a single trailing hyphen
(`aitask-pick-fast-/`, `aitask-pick-fast-codex-/`). The hyphen is the
"generated" marker so every agent root has just one `.gitignore` glob:

```
.claude/skills/*-/
.agents/skills/*-/
.gemini/skills/*-/
.opencode/skills/*-/
```

Authoring directory names (`aitask-pick/`, `task-workflow/`) MUST NOT end
with `-` — that boundary is what keeps the single-glob `.gitignore` working.
Rendered files are autogenerated on demand; do not edit them by hand or
commit them. (Two skills currently ship pre-rendered remote variants for
headless agent runs, and those are intentionally negated in `.gitignore`.)

## Authoring (short pointer)

Skill authors write the `.md.j2` once, against the Claude surface, then add
profile-agnostic stubs at the other three agent surfaces. Two Jinja
conditional patterns:

- `{% if profile.<key> %}` — branch on profile keys (`default_email`,
  `create_worktree`, `plan_preference`, `post_plan_action`, …).
- `{% if agent == "<name>" %}` — gate per-agent content. Today this is used
  by `aitask-wrap` Step 1b (`~/.claude/plans` scanning, claude-only).

`{% raw %} … {% endraw %}` wraps literal `{{` / `{%` markers that must not
be evaluated.

Before committing any `.md.j2` or stub-surface change, run:

```
./.aitask-scripts/aitask_skill_verify.sh
```

It renders every committed `.j2` against every profile for all four agents,
walks the dep closure, and asserts the stub-pattern markers. If you edit a
`.md.j2` or any closure-`.md` file, regenerate the affected goldens in the
**same commit** — see "Regenerate goldens after any `.md.j2` or closure
edit" in the authoring reference below.

Authoring references (in-repo, on
[github](https://github.com/beyondeye/aitasks/tree/main/aidocs)):

- [`aidocs/framework/stub-skill-pattern.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/stub-skill-pattern.md)
  — canonical stub bodies, per-agent surface table, argument-forwarding
  contract, reference resolution rules, template-completeness checks.
- [`aidocs/framework/skill_authoring_conventions.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/skill_authoring_conventions.md)
  — Jinja conventions (comment markers, macros, `{% from %}` imports,
  whitespace control, minijinja caveats), golden regeneration, and the
  NON-SKIPPABLE banner rule.
- [`aidocs/framework/agent_runtime_guards_audit.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/agent_runtime_guards_audit.md)
  — inventory of remaining "If running in Claude Code" guards eligible to
  move to `{% if agent %}` gates.

## See also

- [Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}})
- [`/aitask-pick` execution-profiles reference]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}})
- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}})

---

**Next:** [Verified scores]({{< relref "/docs/concepts/verified-scores" >}})
