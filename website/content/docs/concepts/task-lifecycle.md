---
title: "Task lifecycle"
linkTitle: "Task lifecycle"
weight: 100
description: "The status transitions a task moves through from creation to archival."
depth: [main-concept]
---

## What it is

Every task carries a `status` field that captures where it is in its life:

| Status | Meaning |
|--------|---------|
| `Ready` | Ready to start work on; new tasks start here. |
| `Editing` | Still being written or revised; not ready to start yet. |
| `Implementing` | A coding agent has started work on it and holds its [task lock]({{< relref "/docs/concepts/locks" >}}). |
| `Postponed` | Put aside for later. It stays listed, but task selection skips it. |
| `Done` | Finished; archived tasks keep this status. |
| `Folded` | Merged into another task (see [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})). |

The workflow changes the status for you. Picking a task, which you do with `/aitask-pick` in your coding agent or from the board, starts work on it: it moves from `Ready` to `Implementing`, and the agent takes a [lock]({{< relref "/docs/concepts/locks" >}}) on it. When the work is finished and committed, archiving sets the status to `Done` and moves the file into the archive of finished tasks. Aborting puts it back to `Ready` (or `Editing`, if you choose) and releases the lock. `Folded` is final: a folded file is deleted, not archived, when the task it was merged into is archived.

## Why it exists

The status tells you, the board and task selection which tasks can be started, which are being worked on and which are finished. The set is kept small and fixed, so the board and task selection each handle only a handful of states. Each status change the workflow makes is committed to git, so the task file's git history is also its history.

## How to use

You rarely set `status` by hand: picking, archiving, aborting and folding set it. To put a task aside, set it to `Postponed` on the board's task detail screen or with `ait update`, and back to `Ready` when it should be picked again. The statuses and where archived files go are listed in the [Task File Format reference]({{< relref "/docs/development/task-format" >}}#status-workflow).

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — where the field lives
- [Locks]({{< relref "/docs/concepts/locks" >}}) — the lock state mirrors lifecycle transitions
- [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}}) — the `Folded` terminal state

---

**Next:** [Implementation trails]({{< relref "/docs/concepts/implementation-trails" >}})
