---
title: "Agent memory"
linkTitle: "Agent memory"
weight: 130
description: "How archived tasks and plans become long-term, queryable context for future agent sessions."
depth: [advanced]
---

## What it is

Once a task is archived, its task file moves to `aitasks/archived/` and its plan file — including the post-implementation notes — moves to `aiplans/archived/`. Together they form a structured, version-controlled record of every change ever made through the framework, linked back to the commits that implemented them. The framework treats this archive as **agent memory**: a queryable corpus that subsequent agent sessions read instead of re-deriving context from scratch.

Three integrations consume that memory:

1. **Sibling-context propagation.** When a child task is picked, the workflow gathers archived sibling plans (and task files as fallback) and feeds them into the planning agent as primary context — so later children inherit gotchas and patterns established by earlier ones.
2. **Code Browser line annotation.** The [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) surfaces a glyph next to changed lines pointing at the originating task, and a dedicated **completed tasks history** screen (press `h`) lets you browse archived tasks with their plans and commits.
3. **Code evolution explanation.** [`/aitask-explain`]({{< relref "/docs/skills/aitask-explain" >}}) traces how a file was built up over time by walking the archived tasks that touched it.

## Why it exists

The most expensive thing a long-lived codebase loses is the *why* — why a function was written this way, what the alternative was, what the prior reviewer flagged. Storing tasks and plans in git, then reading them back at the right moments, lets the framework give that context to whichever agent (or human) is touching the code next, without anyone having to remember to write it down somewhere external.

## How to use

The integrations are automatic — `/aitask-pick` gathers sibling context, the Code Browser annotates lines, and `/aitask-explain` walks evolution history. Sibling-context gathering is implemented in [`aitask_query_files.sh`](https://github.com/beyondeye/aitasks/blob/main/.aitask-scripts/aitask_query_files.sh) on GitHub.

## See also

- [Plans]({{< relref "/docs/concepts/plans" >}}) — the primary content of agent memory
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — sibling propagation in action
- [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) — line annotation and completed tasks history
- [`/aitask-explain`]({{< relref "/docs/skills/aitask-explain" >}}) — evolution walk
