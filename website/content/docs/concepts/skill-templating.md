---
title: "Skill templating and per-profile dispatch"
linkTitle: "Skill templating"
weight: 65
description: "How a profile-aware skill gets a ready-made variant for each execution profile and coding agent, created on demand."
depth: [intermediate]
---

## What it is

A **profile-aware** [skill]({{< relref "/docs/skills" >}}), such as
`/aitask-pick`, is written once and comes in several ready-made variants, one
for each [execution profile]({{< relref "/docs/concepts/execution-profiles" >}})
and coding agent you run it with. aitasks creates a variant the
first time you need it, and the agent then follows that variant as the skill.

## Why it exists

An agent re-reads a skill's file while it runs, not only when the skill starts.
If the file changed during a run, the agent would mix two versions of its
instructions, so each run follows a variant that stays fixed for the whole run.

Writing one template that produces the variants also keeps each variant plain.
The `fast` variant holds only the `fast` flow, and no variant carries passages
such as "if your profile sets X, skip this step".

## How to use

- Pass `--profile <name>` when you invoke the skill, for example
  `/aitask-pick --profile fast 42`.
- Set a default profile per skill under `default_profiles` in `userconfig.yaml`
  (yours alone) or `project_config.yaml` (your team's), or in `ait settings`.
  Without a default, the skill uses the `default` profile.
- From a shell, [`ait skillrun`]({{< relref "/docs/commands/skillrun" >}})
  `pick --profile fast 42` starts a coding agent with the skill already invoked.
- In the launch dialog of `ait board` and other TUIs, **(E)dit** on the
  **Profile** row changes the profile for one run or saves it for later runs.

The variant folders are created automatically next to the skill, with names
ending in `-` (such as `aitask-pick-fast-`). Never edit or commit them.

Skill authors will find how the variants are produced, and how to write a
profile-aware skill, on
[Skill Templating and Dispatch]({{< relref "/docs/development/skill-templating" >}}).

## See also

- [Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}}) — what a profile is and which ones ship.
- [Execution profiles reference]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}) — the `--profile` argument, default-profile resolution and the launch dialog's save modes.
- [Skill Templating and Dispatch]({{< relref "/docs/development/skill-templating" >}}) — how the stub renders and dispatches a variant, where each agent's files live, and the authoring guides.
- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}})

---

**Next:** [Verified scores]({{< relref "/docs/concepts/verified-scores" >}})
