---
title: "Folded tasks"
linkTitle: "Folded tasks"
weight: 40
description: "How related tasks are merged into a single primary task."
depth: [intermediate]
---

## What it is

A **folded task** is a task whose content has been **merged into** another (the *primary* task). Folding sets the folded task's `status` to `Folded` and writes a `folded_into` field pointing at the primary; the primary in turn lists every folded child in its `folded_tasks` frontmatter field. At fold time the folded task's body is incorporated into the primary's description under a `## Merged from t<N>` header — the folded file remains on disk only as a reference for archival cleanup, and it is deleted (not archived) when the primary is archived.

## Why it exists

When two or more pending tasks turn out to describe the same underlying work, splitting them across separate plans wastes context and produces redundant commits. Folding consolidates them into a single coherent unit while still preserving each original task's framing inside the primary's description. Folded tasks are **merged**, not superseded or replaced — the original wording remains visible in the primary's body so reviewers can see what was rolled in. This wording matters: code, commit messages, and procedures all use "merged" / "incorporated" rather than "superseded" / "replaced".

## How to use

Use [`/aitask-fold`]({{< relref "/docs/skills/aitask-fold" >}}) to interactively merge two or more existing tasks. Folding can also happen ad-hoc during planning — if a plan in [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) names additional tasks to fold in, the workflow runs the fold inline before continuing. Both parent-level and child-level tasks can be folded.

## See also

- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — the alternative pattern: split instead of merge
- [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}}) — `Folded` is a terminal status
- [Task consolidation workflow]({{< relref "/docs/workflows/task-consolidation" >}}) — when and why to fold

---

**Next:** [Review guides]({{< relref "/docs/concepts/review-guides" >}})
