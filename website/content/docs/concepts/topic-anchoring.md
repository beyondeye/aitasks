---
title: "Topic anchoring"
linkTitle: "Topic anchoring"
weight: 35
description: "How loose follow-up work is grouped around a shared task topic without forcing a parent-child tree."
depth: [main-concept]
---

## What it is

Topic anchoring is a lightweight way to group related tasks around the same
subject. A task can carry an `anchor` frontmatter field whose value is the task
id of the topic root. On the board, tasks with the same topic key are clustered
together in the By-Topic view.

An anchor is not a dependency, a label, or a parent-child relationship. It is a
grouping key for work that belongs near the same subject but does not need the
strict lifecycle of a decomposed parent task.

## How the key is stored

A topic root omits the `anchor:` line. Its own task id is its topic key.
Follow-up and related tasks store the root id in `anchor`, using the bare id
form:

```yaml
---
priority: medium
effort: low
status: Ready
anchor: 130
---
```

Task ids are normalized when they are written. `--anchor t130` and
`--anchor 130` both store `anchor: 130`; child ids use the same bare form, such
as `130_2`. Anchor targets are validated to exist, and completed or archived
tasks remain valid roots. That lets a long-running topic keep collecting
follow-ups even after the original root has been archived.

## Creating anchored tasks

Use `--anchor <id>` when you already know the topic root:

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name polish_search_errors \
  --issue-type enhancement \
  --anchor 130 \
  --desc "Improve the search error messages discovered while working on t130."
```

Use `--followup-of <source_id>` when the new task comes from another task and
should inherit that task's topic:

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name add_search_latency_metrics \
  --issue-type enhancement \
  --followup-of 130_2 \
  --desc "Track latency for the search path touched by t130_2."
```

`--followup-of` flattens to the root. If the source has `anchor: 130`, the new
task also gets `anchor: 130`. If the source is an anchorless child like
`130_2`, the new task anchors to `130`. If the source is an anchorless parent,
the new task anchors to that parent. Follow-ups never form anchor chains.

`--anchor` and `--followup-of` are mutually exclusive. Both are rejected when
creating a child with `--parent`, because children derive their topic from the
parent.

## Children and re-anchoring

A child created with `--parent P` inherits `anchor = P.anchor` when the parent
has one; otherwise it inherits `anchor = P`. This makes a topic lane span the
parent, its children, and loose follow-up work.

To move an existing task to another topic, edit the anchor directly:

```bash
./.aitask-scripts/aitask_update.sh --batch 180 --anchor 130
```

To make a task its own topic root again, clear the field:

```bash
./.aitask-scripts/aitask_update.sh --batch 180 --anchor ""
```

## When to use it

Use a topic anchor when tasks should be near each other for triage and review,
but can be planned, picked, implemented, and archived independently.

Use a parent-child task when one larger piece of work needs to be decomposed
into ordered child tasks that share a parent lifecycle.

Use `depends` when one task cannot be implemented until another task lands.

Use labels when you need broad filtering across many unrelated topics, such as
`ui`, `docs`, or `performance`.

These relationships can be combined. For example, a follow-up can be anchored
to a feature topic and also depend on a bug fix that must land first.

## Board view

Press `y` in the board TUI to switch to the By-Topic base view. The board builds
topic lanes from each task's topic key: `anchor` when present, else a child's
parent topic, else the task's own id. Topics with two or more visible tasks get
their own lane, labelled by the root task when available. Single-task topics are
collapsed into the trailing `Ungrouped` lane.

If the root task is archived or otherwise not loaded in the current task set,
the anchor id still remains the stable lane key. The lane label falls back to
that id, so follow-ups anchored to an archived root continue to cluster
together.

The task detail screen also exposes the anchor field for edits, which is useful
when a task starts as standalone and later becomes part of a broader topic.

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) - the base task file model
- [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}) - the stricter decomposition relationship
- [Task File Format]({{< relref "/docs/development/task-format" >}}) - the frontmatter schema
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}) - By-Topic view details
