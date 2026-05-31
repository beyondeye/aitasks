---
title: "Cross-Project Dependencies"
linkTitle: "Cross-Project Deps"
weight: 49
description: "Block, read, update, and plan tasks across linked aitasks projects with cross-repo dependencies and the --project flag"
depth: [advanced]
---

The [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) page covers the **registry layer**: giving each project a logical name and resolving that name to a path with `ait projects`. This page builds directly on top of it. Once your projects are registered, you can make a task **depend on** work in another project, **read and update** another project's tasks from where you sit, see cross-repo links **on the board**, and **plan** a coordinated change that spans two repos.

> **Start with the registry layer.** Everything here assumes the linked projects are already registered and their logical names resolve. Cross-repo references use the `backend#42` task notation and `backend:path` file notation introduced on the [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) page.

## Cross-repo task dependencies

A task can declare that it is blocked by work in another project using two frontmatter fields:

```yaml
xdeprepo: backend        # the linked project (a logical name from the registry)
xdeps: [42, 16_2]        # task IDs in that project, written in its own local format
```

- `xdeprepo` is a single project name — one linked project per task. It must resolve through the registry.
- `xdeps` is a list of task IDs written the way `backend` numbers them locally: a parent (`42`) or a parent-child pair (`16_2`).

### How blocking works

A cross-repo dependency behaves like a local `depends:` entry, with one rule: it is satisfied **only when the linked task is `Done`**. Any other status — `Ready`, `Editing`, `Implementing`, `Postponed` — leaves your task blocked. `ait ls` and `/aitask-pick` skip a task whose cross-repo dependencies are not all `Done`, exactly as they skip a task with unmet local dependencies. The block is shown against the task:

```text
Blocked (by backend#42)
```

You can set `xdeprepo` **without** `xdeps`. That declares an intent to coordinate with `backend` without blocking on any specific task yet, and it is the flag that opts a task into [paired cross-repo planning](#planning-paired-work-across-two-repos). The reverse is not allowed: `xdeps` without `xdeprepo` is rejected when the task is created or updated, because task IDs are meaningless without a project to resolve them against.

### When the linked project can't be found

If `xdeprepo` names a project that is not registered, or whose registered path has gone stale, the dependency cannot be checked — so it stays **blocked** and is marked `UNREACHABLE`:

```text
Blocked (by backend#42 (UNREACHABLE))
```

Register or repoint the project to clear it — see [how a name resolves to a path]({{< relref "/docs/workflows/multi_project#how-a-name-resolves-to-a-path" >}}) (`ait projects add` from the project's current location, or `ait projects update` to move it).

## Seeing cross-repo references on the board

`ait board` understands cross-repo references in two places: the `xdeps` frontmatter, and any `backend#42` notation written in a task's body. A card with a cross-repo dependency shows a dedicated line, separate from its local-dependency line, with the linked task's live status in brackets:

```text
↗ backend#42 [Implementing]
```

When a cross-repo dependency is unmet, the card also shows a `🌐 blocked (cross-repo)` status chip — with `(UNREACHABLE)` inline if the project can't be resolved.

Press `#` on a card that has cross-repo references to open a read-only popup of the linked task. If the card points at more than one, a picker lists them; Tab cycles through the references and the Cancel button, and `Esc` closes the popup. The popup is strictly read-only — it shows the linked task's content without taking a lock or starting a pick.

## Reading another project's tasks and files

Read-side tooling takes a `--project <name>` flag so you can inspect a linked project without leaving the one you are in. The name resolves through the registry at call time, so the same command works on any machine where `backend` is registered — never a hardcoded `../backend/` path.

List another project's prioritized task table:

```bash
ait ls --project backend
```

Trace the task and plan history behind a file in another project with the cross-repo file notation `<name>:<path>` (repeat `--project` to span several projects in one report):

```bash
./.aitask-scripts/aitask_explain_context.sh --project backend:src/protocol.rs
```

## Updating a task in another project

`ait update --project <name>` makes an administrative edit to a task in a linked project — typically to set the other side of a cross-repo dependency, adjust priority, or move a card. Like cross-repo creation, it requires `--batch`:

```bash
# From frontend, point a backend task back at this side of the work
ait update --batch --project backend 42 --priority high --xdeps 7 --xdeprepo frontend
```

You can set administrative metadata this way — priority, effort, labels, board column and index, assignment, the `--xdeps` / `--xdeprepo` dependency fields, and a status of `Ready`, `Editing`, or `Postponed`. Workflow transitions and renames are deliberately refused across repos:

- `--status Implementing` and `--status Done` are rejected — those must go through the linked project's own `/aitask-pick`, where the lock and plan are handled.
- `--status Folded` is rejected — folding needs both task bodies and is not a cross-repo operation.
- `--name` (rename) is rejected — it would touch a filename and a parent's child list in the other repo.
- If the target task is **locked by a different host or user**, the update is refused so you don't stomp on someone mid-implementation. Pick the task there to release the lock, or wait.

## Declaring cross-repo links when creating a task

The interactive `ait create` (run with no flags) adds a **cross-repo project** step to its prompts. After the usual dependency and label questions, you can pick one linked project from the registry — only projects that currently resolve are offered. Choosing one writes `xdeprepo: <name>` to the new task.

Once a project is selected, the reference menu gains two extra entries:

- **Add cross-repo archived task reference** — browse the linked project's archived tasks and append a `backend#42` reference into the description.
- **Add cross-repo file reference** — browse the linked project's files and append a `backend:src/Login.kt` reference into the description.

The interactive flow only sets `xdeprepo` (the intent to coordinate). To attach explicit blocking `xdeps` at creation time, use batch mode — `--xdeps` requires `--xdeprepo`, and the IDs are validated against the linked project as the task is created:

```bash
ait create --batch \
    --name wire_new_protocol --type feature --priority high \
    --desc "Adopt the bumped wire protocol" \
    --xdeps 42,16_2 --xdeprepo backend --commit
```

See the [cross-repo notation]({{< relref "/docs/workflows/multi_project#referring-to-cross-project-tasks-and-files" >}}) section for the `backend#42` and `backend:path` reference forms.

## Planning paired work across two repos

When a change genuinely spans two repos, you do **not** make one parent task whose children straddle both. Each project's task hierarchy stays locally complete; only the edges between them cross. The rule is **two parents, one per repo**, joined by cross-repo dependency edges (`xdeps` + `xdeprepo`).

You opt a task into this by giving it an `xdeprepo` (with or without `xdeps`). When you `/aitask-pick` that task, the planning phase offers to design it as a paired cross-repo decomposition. If you accept, it:

- scans both repos and designs one coordinated set of children;
- creates a parent in each repo, with each child living under whichever repo it belongs to;
- hands out child numbers in lockstep so the cross-repo edges resolve as they are written;
- commits each side through that repo's own `./ait git`, and warns you if the linked repo's push fails so you can publish it manually.

The in-repo half of this — assessing complexity, splitting into children, and writing each child's plan — works exactly as described in [Parallel Planning]({{< relref "/docs/workflows/parallel-planning" >}}). Paired cross-repo planning adds the second parent and the cross-repo edges on top.

## See also

- [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) — the registry, `ait projects`, cross-repo task creation, and the reference notation this page builds on.
- [Parallel Planning]({{< relref "/docs/workflows/parallel-planning" >}}) — front-loading complex task decomposition, the in-repo foundation for paired cross-repo planning.
