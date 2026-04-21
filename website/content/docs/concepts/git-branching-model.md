---
title: "Git branching model"
linkTitle: "Git branching model"
weight: 110
description: "The dedicated branches that hold task data, locks, and IDs, and the ./ait git wrapper that routes to them."
---

## What it is

aitasks splits the repository across several long-lived branches:

| Branch | Purpose |
|--------|---------|
| `main` (or your code branch) | Source code only — no `aitasks/` or `aiplans/` content. |
| `aitask-data` | All task and plan files. Checked out as a worktree at `.aitask-data/`. |
| `aitask-locks` | Atomic task locks (one commit per lock acquire / release). |
| `aitask-ids` | Reservation log used to allocate fresh task IDs without collisions. |

`aitasks/` and `aiplans/` at the project root are **symlinks** into the `.aitask-data/` worktree, so they appear in the usual places but actually live on `aitask-data`. The `./ait git` wrapper routes git commands to the correct worktree based on the paths you pass — `./ait git add aitasks/t42_foo.md` operates on `aitask-data`, `git add src/foo.py` operates on `main`, and the two are committed independently.

## Why it exists

Code review, branch protection, and CI rules are usually scoped to source code. Mixing rapidly-churning task files into the same branch causes noise (every `Ready → Implementing` transition would touch your code branch's history) and makes branch protection hard to tune. Separate branches keep `git log` for code clean, let `aitask-data` push freely without code-review overhead, and make `aitask-locks` an atomic primitive that any agent can read/write without disturbing source control.

## How to use

The architecture, symlink rules, and detection logic are documented in the [task-workflow repo-structure procedure](https://github.com/dario-elyasy/aitasks/blob/main/.claude/skills/task-workflow/repo-structure.md) on GitHub. In day-to-day use you only need two rules: use `./ait git` for anything in `aitasks/` or `aiplans/`, and use plain `git` for source code. (For older projects bootstrapped before separate branches existed, `./ait git` transparently falls back to plain `git`.)

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — what lives on `aitask-data`
- [Locks]({{< relref "/docs/concepts/locks" >}}) — what lives on `aitask-locks`
- [Parallel development workflow]({{< relref "/docs/workflows/parallel-development" >}}) — how the branching model enables concurrent agents

---

**Next:** [The IDE model]({{< relref "/docs/concepts/ide-model" >}})
