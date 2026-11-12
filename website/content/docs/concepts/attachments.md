---
title: "Attachments"
linkTitle: "Attachments"
weight: 55
description: "Files copied into a task's own storage and identified by their content, so they outlive the original."
depth: [intermediate]
---

## What it is

An **attachment** is a file, such as a screenshot, a log or a PDF, that
`ait attach` copies into the task's own storage: it is stored with the task
data and committed to git like the task files. After the copy, the original can
be moved, edited or deleted and the attachment stays.

aitasks identifies an attachment by a hash of its content, so the same file attached to
two tasks is stored once, and changing a file's contents makes a different
attachment. On its task an attachment also has a name, by default the file's
name, which is what you type in commands; two tasks can give the same file
different names.

## Why it exists

Files that explain a task, such as the screenshot of the bug or the log that
shows it, usually sit somewhere temporary: a downloads folder, a scratch
directory, a chat upload. A task that points at them loses them. An attachment
keeps a copy with the task for as long as the task exists, active or archived.

Identifying the copy by its content keeps that cheap and safe. Attaching a file
to a second task adds no second copy, and every fetch is checked against the
hash the task recorded, so a damaged copy is reported as an error instead
of being handed to you.

## How to use

```bash
ait attach add 42 screenshot.png         # attach a file to t42
ait attach ls 42                         # list t42's attachments
ait attach get 42 screenshot.png --out /tmp/shot.png
```

`ait attach rm` takes an attachment off a task and keeps the stored copy; only
`ait attach gc`, which you run yourself, deletes copies that no task uses any
more. An archived task keeps its attachments, and you can still list and fetch
them, but you cannot add new ones to it. When a task is folded (merged into another task), its attachments move to that task.

## See also

- [`ait attach`]({{< relref "/docs/commands/attach" >}}) — the command reference, including which operations keep a stored copy referenced and when gc deletes it.
- [Task file format]({{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments) — the `attachments:` fields and where the stored copies live.
- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the files attachments belong to.
- [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}}) — what folding merges into the primary task.

---

**Next:** [Artifacts]({{< relref "/docs/concepts/artifacts" >}})
