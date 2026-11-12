---
title: "Repository Maintenance"
linkTitle: "Repository Maintenance"
weight: 85
description: "Periodic upkeep for a repository integrated with the aitasks framework"
depth: [intermediate]
---

A repository that has used aitasks for a while accumulates state worth tending
to from time to time: hundreds of archived task and plan files, stale explain
caches, an out-of-date changelog, and a framework version that drifts behind
upstream. None of this is urgent. Each section below is one job you can run
when it is due.

## Archiving completed work

As tasks complete and archive, the archive folders fill with one file per task
and plan. [`ait zip-old`]({{< relref "/docs/commands/issue-integration#ait-zip-old" >}})
bundles old completed task and plan files into numbered `tar.zst` archives,
keeping the most recent files uncompressed so task numbering stays intact.

```bash
ait zip-old --dry-run    # Preview what would be archived
ait zip-old              # Archive and commit
```

Run it periodically. A natural cadence is right after a release (see
[Releases]({{< relref "/docs/workflows/releases" >}})), once the just-shipped tasks are unlikely to need
hand inspection.

## Pruning explain caches

The [`/aitask-explain`]({{< relref "/docs/skills/aitask-explain" >}}) skill writes
reference data into the explain cache, which grows over time. Clean it up with
[`ait explain-runs` and `ait explain-cleanup`]({{< relref "/docs/commands/explain" >}}):

```bash
ait explain-runs --list            # See accumulated run directories
ait explain-runs --cleanup-stale   # Remove stale runs
ait explain-cleanup --dry-run --all
```

## Changelog and release prep

Before cutting a release, gather what changed since the last tag with
[`ait changelog`]({{< relref "/docs/commands/issue-integration#ait-changelog" >}}) (or the
[`/aitask-changelog`]({{< relref "/docs/skills/aitask-changelog" >}}) skill, which generates a
categorized entry). The end-to-end release pipeline is documented in
[Releases]({{< relref "/docs/workflows/releases" >}}).

## Diagnosing the task-data worktree

When task data lives on its own branch,
[`ait git-health`]({{< relref "/docs/commands/sync#ait-git-health" >}}) reports the
state of the task-data worktree: its branch and commit, and any detached HEAD or
unfinished rebase or merge that would leave `ait git` stuck. Run it when a fresh
clone or a moved checkout looks like it is missing tasks.

```bash
ait git-health
```

## Upgrading the framework

To move the installed framework to a newer version, run
[`ait upgrade`]({{< relref "/docs/commands/setup-install#ait-upgrade" >}}):

```bash
ait upgrade          # Move to the latest released version
ait upgrade 0.2.1    # Move to a specific version
ait setup            # Then populate any newly added files and dependencies
```

After an upgrade, also run
[`ait setup`]({{< relref "/docs/commands/setup-install#ait-setup" >}}): a newer version may ship
new scripts, skills, or dependencies, and `ait setup` installs or restores anything
the upgrade introduced without touching your existing configuration.

## See also

- [Releases]({{< relref "/docs/workflows/releases" >}}) — the full release pipeline this maintenance work feeds into.
- [Multi-Project]({{< relref "/docs/workflows/multi_project" >}}) — managing several aitasks-integrated repositories at once.

---

**Next:** [Revert Changes]({{< relref "/docs/workflows/revert-changes" >}})
