---
title: "Cross-Repo References"
linkTitle: "Cross-repo references"
weight: 115
description: "Pointing at a task or file in another aitasks project by the project's name, which each machine maps to its own copy of that project."
depth: [intermediate]
---

## What it is

A **cross-repo reference** points at a task or a file in another aitasks project
by that project's **name**, not by where it sits on disk:

```text
backend#42               # task 42 in the backend project
backend:src/protocol.rs  # a file in the backend project
```

Each machine keeps its own list of projects, mapping each name to wherever that
project is checked out there, and the name is looked up only when the reference
is used. So the same reference, written once into a task, a plan or a commit
message, works on your machine, on a teammate's and inside a cloud agent,
wherever each of them keeps the project.

The project name is part of what identifies a task: every project has its own
task 42, so `42` alone means nothing outside its own project.

## Why it exists

The obvious way to point at another project is a path such as `../backend/`. A
path records one machine's folder layout in a file that every machine shares, so
it breaks as soon as a teammate, a cloud agent or a fresh clone puts the project
somewhere else — and a broken path looks just like a reference that was always
wrong.

A name that does not resolve is a clear problem you can fix: register the
project on this machine.

## How to use

- **Register** each project once per machine with `ait projects add`, and check
  what resolves with `ait projects list` — see
  [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}).
- **Write references** as `backend#42` and `backend:path` in tasks, plans and
  commit messages.
- **Work in another project from where you are**: commands such as `ait create`
  and `ait ls` take `--project backend`, and you can send one of its tasks a
  [task note]({{< relref "/docs/workflows/task-notes" >}}#a-task-in-another-repository).
- **Wait for its work**: mark a task as blocked until a task in the other
  project is done — see
  [Cross-Project Dependencies]({{< relref "/docs/workflows/cross_project_dependencies" >}}),
  which also covers planning a change across two repos.

## See also

- [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) — the registry, `ait projects`, how a name resolves, and the reference notation
- [Cross-Project Dependencies]({{< relref "/docs/workflows/cross_project_dependencies" >}}) — blocking on another project's work, and planning a change across two repos
- [Task format]({{< relref "/docs/development/task-format" >}}) — the task-file fields that record cross-repo links
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) — the hierarchy that stays inside one project
- [Task notes]({{< relref "/docs/concepts/task-notes" >}}) — sending context to a task in another project

---

**Next:** [The IDE model]({{< relref "/docs/concepts/ide-model" >}})
