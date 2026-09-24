---
title: "Cross-Repo References"
linkTitle: "Cross-repo references"
weight: 115
description: "Why a logical project name resolved at call time is the identity of cross-repo work, and a path never is."
depth: [intermediate]
---

## What it is

A **cross-repo reference** points at a task or a file in another aitasks project
by that project's **logical name** — `backend#42`, `backend:src/protocol.rs` —
and resolves the name to a directory at the moment the reference is used.

The registry, the `ait projects` command, the resolution order and the notation
are documented in
[Multi-Project]({{< relref "/docs/workflows/multi_project" >}}). This page is
about what those pieces assume: that the identity of cross-repo work is a
**pair**, and that a path is only ever a binding of one half of it.

### Identity is the pair; the path is a binding

A task id is local by construction. `42` is a complete identity *inside* one
project and means nothing outside it — every registered project has its own `42`.
So the identity of a cross-repo reference is the pair: which project, and which
id within it. `backend#42` is that pair written down.

What a project name maps to is deliberately **not** part of the identity. The
mapping lives in a per-user, gitignored registry, it is resolved when the
reference is used rather than when it is written, and it may differ on every
machine. That separation is the whole point: the same reference, committed once,
keeps working on a teammate's checkout, inside a cloud agent, and after the
project is re-cloned somewhere else — none of which a recorded path survives.

It also means a reference can be perfectly valid and still not resolve *here*.
That is a property of this machine's registry, not a defect in the reference, and
the framework treats the two as different things.

### The name is checked when it is written, and again when it is read

Both moments are strict, in different directions.

At **write** time the framework refuses rather than records: creating or updating
a task with a linked project that is not registered, or whose registered path no
longer holds an aitasks project, fails outright — as does naming a dependency id
that does not exist in that project. A cross-repo edge is never written on the
assumption that it will resolve later. The rule that dependency ids cannot be
declared without a project to resolve them against is
[the same principle stated for the fields]({{< relref "/docs/workflows/cross_project_dependencies" >}}#cross-repo-task-dependencies).

At **read** time it fails closed: if the linked project stops resolving, the
dependency is not quietly dropped and not treated as met — the task stays
blocked and is marked `UNREACHABLE`. An unanswerable question about whether work
elsewhere is finished is answered as "not finished", because the alternative is
starting work whose prerequisite may still be open.

Declaring the linked project **without** any dependency ids is meaningful on its
own: it is an intent to coordinate that blocks nothing, and it is what opts a
task into paired cross-repo planning.

### Hierarchies never cross a repo boundary

A parent and its children always live in one project. There is no such thing as a
child in another repo, which is why a change spanning two repos is modelled as
**two parents — one per repo — joined by cross-repo dependency edges** rather
than one hierarchy that straddles both. Each project's task tree stays locally
complete and locally meaningful; only the edges between them cross.

The command-level consequence of that rule — what `--parent` means when creating
a task in another project — is stated with the command, in
[creating a task in a sibling project]({{< relref "/docs/workflows/multi_project" >}}#creating-a-task-in-a-sibling-project).

### A command that writes elsewhere never picks between bindings

A name can be bound in more than one place at once — a live tmux session, the
registry, an environment variable. For reading a reference, taking the first
binding that answers is fine. A command that **writes into** the other
repository — [sending a note to one of its
tasks]({{< relref "/docs/commands/note" >}}#sending-to-another-repository) —
holds itself to more: it checks every binding, and refuses if two of them point
at different checkouts or if one of them could not be read. Writing into the
wrong repository cannot be undone by resolving the name correctly later, so
"could not rule out a conflict" is treated as a conflict.

### Why an unresolvable name is never auto-cloned

When a name does not resolve, the framework prints how to register the project
and stops; it never clones the repository to make the reference work. The user
named that project deliberately and is the authority on which checkout it means —
guessing from a recorded remote URL would silently bind the identity to a
directory nobody chose, which is the failure this whole layer exists to avoid.

## Why it exists

The alternative to a logical name is a
[relative path to a sibling directory]({{< relref "/docs/workflows/multi_project" >}}#why-logical-project-names),
which encodes one machine's layout into a file shared by all of them.

Resolving a name late does not merely make a reference portable — it changes what a
failure *is*. A path that no longer exists is indistinguishable from a reference
that was always wrong, and nothing can tell you which. A name that does not
resolve is a specific, reportable state of this machine's registry, which is why
the tooling can say `STALE` rather than guess, keep a dependency blocked rather
than drop it, and tell you exactly which project to register.

## How to use

Register projects and write references with
[Multi-Project]({{< relref "/docs/workflows/multi_project" >}}); declare and
consume blocking edges with
[Cross-Project Dependencies]({{< relref "/docs/workflows/cross_project_dependencies" >}}).

## See also

- [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) — the registry, `ait projects`, and the reference notation
- [Cross-Project Dependencies]({{< relref "/docs/workflows/cross_project_dependencies" >}}) — blocking on another project's work, and paired planning
- [Task format]({{< relref "/docs/development/task-format" >}}) — the frontmatter fields that carry cross-repo edges
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — the hierarchy that stays inside one project
- [Task notes]({{< relref "/docs/concepts/task-notes" >}}) — why a note from another project records a qualified sender, and what it can prove

---

**Next:** [The IDE model]({{< relref "/docs/concepts/ide-model" >}})
