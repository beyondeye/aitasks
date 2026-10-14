---
title: "Cross-Project Dependencies"
linkTitle: "Cross-Project Deps"
weight: 49
description: "Block, read, update, and plan tasks across linked aitasks projects with cross-repo dependencies and the --project flag"
depth: [advanced]
---

The [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) page covers the **registry layer**: giving each project a logical name and resolving that name to a path with `ait projects`. This page builds directly on top of it. Once your projects are registered, you can make a task **depend on** work in another project, **read and update** another project's tasks from where you sit, see cross-repo links **on the board** and **in implementation trails**, jump between linked trails in different projects, and **plan** a coordinated change that spans two repos.

> **Start with the registry layer.** Everything here assumes the linked projects are already registered and their logical names resolve. Cross-repo references use the `backend#42` task notation and `backend:path` file notation introduced on the [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) page.

## Cross-repo task dependencies

A task can declare that it is blocked by work in another project using two frontmatter fields:

```yaml
xdeprepo: backend        # the linked project (a logical name from the registry)
xdeps: [42, 16_2]        # task IDs in that project, written in its own local format
```

- `xdeprepo` is a single project name — one linked project per task. It must resolve through the registry when the task is created or updated: an unregistered name, or one whose registered path is stale, is refused rather than recorded.
- `xdeps` is a list of task IDs written the way `backend` numbers them locally: a parent (`42`) or a parent-child pair (`16_2`).

### How blocking works

A cross-repo dependency behaves like a local `depends:` entry, with one rule: it is satisfied **only when the linked task is `Done`**. Any other status — `Ready`, `Editing`, `Implementing`, `Postponed` — leaves your task blocked. `ait ls` and `/aitask-pick` skip a task whose cross-repo dependencies are not all `Done`, exactly as they skip a task with unmet local dependencies. The block is shown against the task:

```text
Blocked (by backend#42)
```

You can set `xdeprepo` **without** `xdeps`. That declares an intent to coordinate with `backend` without blocking on any specific task yet, and it is the flag that opts a task into [paired cross-repo planning](#planning-paired-work-across-two-repos). The reverse is not allowed: `xdeps` without `xdeprepo` is rejected when the task is created or updated, because task IDs are meaningless without a project to resolve them against.

### When the linked project can't be found

If `xdeprepo` names a project that is not registered, or whose registered path has gone stale, the dependency cannot be checked — so it stays **blocked** and is marked `UNREACHABLE`. Not knowing whether the other project's work is done is treated as not done, so you never start on a prerequisite that may still be open:

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

## Cross-repo dependencies in implementation trails

An [implementation trail]({{< relref "/docs/workflows/implementation-trails" >}}) can hold tasks that are blocked by work in another project, and members that live in another project. Both show on the trail's cards, in the board's By-Trail view (`z`) and in [`ait trails`]({{< relref "/docs/tuis/trails" >}}) alike.

### Blocked members

A trail card for a local task with `xdeps` carries the same `↗` line as a board card, one entry per linked task:

```text
🌐 blocked (cross-repo)
↗ backend#42 [Implementing], backend#16_2
```

Each entry shows how far its check has got:

| Entry | Meaning |
|-------|---------|
| `backend#42` | Checked — the linked task is `Done` |
| `backend#42 [Implementing]` | Checked — the linked task is not done; its status is in brackets |
| `backend#42 (UNREACHABLE)` | Checked — the project can't be resolved, or the task doesn't exist there |
| `backend#42 (checking…)` | A check for it is running |
| `backend#42 (not checked)` | Nothing has checked it yet — typically an `xdeps` entry added on disk and picked up with `r` |

`🌐 blocked (cross-repo)` appears only when a **finished** check finds a linked task that is not `Done`; an unreachable one counts as not done, the same rule as in [How blocking works](#how-blocking-works). An entry that is still being checked, or has not been checked, never marks the member blocked — it reads as unknown instead.

### Members from another project

A trail member written as `backend#42` is a cross-repo member. It appears as a read-only ghost card, `👻 cross-repo member — read-only`, with a status line read live from its own project:

| Line | Meaning |
|------|---------|
| `📋 <Status>` | The task's current status in `backend` |
| `🌐 (UNREACHABLE)` | The project can't be resolved, or the task doesn't exist there |
| `🌐 (checking…)` | A check is running |
| `🌐 (not checked)` | Nothing has checked it yet |

The ghost is marked landed — `✔` and struck through — only when its own project reports it `Done`.

### When the checks run

The checks run in the background, alongside the trail's freshness check: when a trail is opened, on `d`, and in the board also on a sync and when you enter the By-Trail view. `r` and switching tabs in `ait trails` start no check and reuse the last results, which is why an entry added since reads `(not checked)` until the next `d`.

## Jumping to a linked trail in another project

When two projects coordinate, each usually has its own trail for its side of the work. From a trail in one project you can list the trails in other projects that are **linked** to it, and jump to one in that project's own `ait trails`.

### What makes two trails linked

Trail B in `backend` is linked to trail A in `frontend` when any of these holds:

- a member of A has `xdeprepo: backend` and an `xdeps` entry that is a member of B;
- A has a cross-repo member `backend#<id>` that is a member of B;
- a member of B has `xdeprepo: frontend` and an `xdeps` entry that is a member of A;
- B has a cross-repo member `frontend#<id>` that is a member of A.

Projects are compared by where they live on disk, not by name, so a trail that names its project through a registry alias still links. A task in a third project that both trails mention does not link them. The search covers every project in the [registry]({{< relref "/docs/workflows/multi_project" >}}), plus any project the trail's members name directly.

### Finding a linked trail

Press **`L`** while a loaded trail is on screen — in the board's By-Trail view or in `ait trails`. The search runs in the background and announces itself with `Searching for linked trails in other projects…`; it usually takes a second or two. Each project is searched in its own checkout, with 30 seconds per project.

If every project was searched and none holds a linked trail, the result is `No linked trails in other projects`. Otherwise the **Linked trails** dialog lists each one as `<project> · <handle> · <name>`, with up to three lines saying why it is linked:

```text
backend · art:trail-wire-protocol · Wire protocol rollout
  └ fwd-xdeps: frontend#7 xdeps backend#42
  └ rev-member: frontend#12
```

The prefixes name the four rules above, in order: `fwd-xdeps` and `fwd-member` come from the trail you started from, `rev-xdeps` and `rev-member` from the other one. Move with `↑`/`↓`, press `Enter` to jump, `Esc` to cancel.

When some project could not be searched completely, the dialog says so instead of claiming there is nothing to find — `Some projects could not be fully searched — the list may be incomplete:` above the links, or `No linked trails found — the search was incomplete:` when it found none — followed by one line per problem:

| Line | Meaning |
|------|---------|
| `<project>: could not search — stale path (…)` | The registered path moved, is missing, or was never recorded — repoint it with `ait projects update` |
| `<project>: could not search — not registered (…)` | A member names a project that is not in the registry — add it with `ait projects add` |
| `<project>: could not search — export failed (…)` | Listing that project's trails failed |
| `<project>: could not search — timed out (…)` | No answer within 30 seconds |
| `<project>: searched in part (…)` | Some of that project's tasks, archives or trails could not be read; the links found there are still listed |
| `project registry <path> could not be read (…)` | The registry file itself could not be read |
| `this trail (<project>): member(s) could not be read (…)` | A member of the trail you started from could not be read |

Pressing `L` again while a search is running does not start a second search alongside it: the newest request runs when the current one finishes. Switching tabs, closing the trail or leaving the view drops the result. If the trail you started from reloads with different content before the search finishes, you are told to press `L` again.

### What the jump does

Choosing a trail:

1. finds that project's tmux session — any running session that belongs to it, preferring its configured default session name — and starts one when none is running;
2. opens the trail in that project's `ait trails`: a running `ait trails` there switches to it, otherwise a new `trails` window starts with `ait trails --trail <handle>`;
3. switches your terminal to that session.

Anything you need to know about the jump is shown **before** the switch, because once your terminal is in the other session a message left behind would go unseen. A dialog lists it, with **Switch** and **Stay here**:

- the other project runs an older aitasks without trail jumps — run `ait upgrade` there; switching takes you to its session without the trail opened;
- the project's `tmux.default_session` setting was unusable, so its session was started under another name.

Outside the aitasks tmux server — not in tmux at all, or in a different tmux server — nothing is started or switched. The notice gives the command to run instead:

```bash
ait projects exec backend -- ./ait trails --trail art:trail-wire-protocol
```

If the project's session stopped or changed hands while the dialog was open, the jump stops with `The tmux session for <project> changed before the jump — press L to try again`.

A trail stays owned by its task in its own project: the jump opens the other project's own `ait trails`, and a trail from another project is never shown inside this one.

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

- [Cross-repo references]({{< relref "/docs/concepts/cross-repo-references" >}}) — the concept: what a cross-repo reference is, and why it names a project instead of a path.
- [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) — the registry, `ait projects`, cross-repo task creation, and the reference notation this page builds on.
- [Parallel Planning]({{< relref "/docs/workflows/parallel-planning" >}}) — front-loading complex task decomposition, the in-repo foundation for paired cross-repo planning.
- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}) — creating, reading and refreshing the trails whose cross-repo members and links this page describes.
- [Trails]({{< relref "/docs/tuis/trails" >}}) — the stand-alone `ait trails` reader, with its `L` key and its `--trail` launch flag.
