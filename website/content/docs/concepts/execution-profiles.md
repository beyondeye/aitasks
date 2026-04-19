---
title: "Execution profiles"
linkTitle: "Execution profiles"
weight: 60
description: "Pre-answered workflow questions that switch a skill from interactive to automated."
---

## What it is

An **execution profile** is a YAML file in `aitasks/metadata/profiles/` that pre-answers the questions a skill would otherwise ask interactively. Each profile sets a handful of named keys — for example `skip_task_confirmation`, `default_email`, `create_worktree`, `plan_preference`, `post_plan_action`, `qa_mode` — that the skill then consults at each decision point. Profiles are picked at the start of a skill run (with `--profile <name>` or interactively from a list) and remain in effect for that session.

Three profiles ship by default:

| Profile | Behavior |
|---------|----------|
| `default` | Standard interactive workflow — every question is asked. |
| `fast` | Minimal prompts — skip confirmations, use the existing plan when present, stop after plan approval. |
| `remote` | Fully autonomous — no interactive prompts, suitable for Claude Code Web. |

Per-skill defaults can be set in `userconfig.yaml` or `project_config.yaml` so that, for example, `/aitask-pick` always loads `fast` for you without having to pass `--profile`.

## Why it exists

The interactive workflow is the right default — confirmations and choices keep humans in the loop on irreversible decisions — but it becomes friction once you have established preferences or are running an agent unattended on a remote runner. Profiles let you express those preferences declaratively and version them, instead of re-typing the same answers every session.

## How to use

The full key reference and customization guide live in the [`/aitask-pick` execution profiles page]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}).

## See also

- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) — the primary consumer of profiles
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — view and edit profiles interactively
