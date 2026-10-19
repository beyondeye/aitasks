---
title: "Artifacts"
linkTitle: "Artifacts"
weight: 57
description: "Versioned task outputs behind a stable art:<id> handle — new versions and backend moves never rewrite the task file."
depth: [advanced]
---

## What it is

An **artifact** is a versioned output that belongs to a task — an HTML plan, an implementation trail, a report, a mockup. The task's `artifacts:` frontmatter records only a stable **handle** such as `art:t42-htmlplan`, plus a kind and an optional name. Everything that changes over time lives in a separate **manifest**: which version is current, the list of every version, and which backend stores them. Each version is an immutable blob identified by the SHA-256 of its bytes, so every fetch is checked against its hash and each machine keeps a local cache under `~/.cache/ait/artifacts/`.

Resolving a handle therefore goes handle → manifest → backend → local cache. The backend is where the blobs actually live:

| Backend | Where blobs live | Pick it when |
|---------|------------------|--------------|
| `local` | Committed on the task data branch, beside the task files. The default; needs no configuration | You are getting started, the artifacts are small, or you work offline |
| `dir` | A directory every teammate mounts at the same absolute path (NAS, network share) | Your team already shares a mounted store |
| `gitbranch` | A dedicated git branch (by default `aitask-artifacts`), pushed to `origin` when the repository has one | You want blobs in git without growing the task data branch — no mount and no credentials |

Three `gitbranch` rules are easy to trip over:

- **A write is pushed before it counts.** When the repository has an `origin`, a write succeeds only once `origin` has accepted it, so `origin` must be reachable. In a repository with no `origin`, the local branch is the store and nothing is pushed.
- **The branch belongs to the store.** Pointing the backend at an existing ordinary branch, or at a reserved name such as `main` or `aitask-data`, is refused.
- **A rename is a migration.** Changing the configured branch once the store exists needs `ait artifact gitbranch-migrate`, not `ait artifact move`.

The exact rules and messages are on the [`ait artifact` command page]({{< relref "/docs/commands/artifact" >}}).

## Why it exists

Some outputs are too large, or change too often, to live inside a task file — and a task file that is rewritten on every revision makes a noisy history. Artifacts keep the task file stable: it records the handle once, and a new version or a move to another backend touches only the manifest. Because the handle never changes, links to it stay valid, and any machine with the project's configuration can fetch the same artifact.

The backend choice is what lets large blobs stay off the task data branch: start on `local`, then move artifacts to `dir` or `gitbranch` when the data branch should stay small.

## How to use

```bash
ait artifact create 42 plan.html --kind html_plan   # store v1 on t42 → art:t42-htmlplan
ait artifact update art:t42-htmlplan plan.html      # store a new version
ait artifact get art:t42-htmlplan --out /tmp/p.html # fetch the current version
ait artifact ls 42                                  # list t42's artifacts
```

The [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) skill stores implementation trails as artifacts, so you may already have some. Choose the default backend in [`ait settings`]({{< relref "/docs/tuis/settings" >}}) → **Artifacts** (`k`), or in the `artifacts:` block of `aitasks/metadata/project_config.yaml`.

## See also

- [`ait artifact`]({{< relref "/docs/commands/artifact" >}}) — every verb, the backend rules and the configuration keys
- [Attachments]({{< relref "/docs/concepts/attachments" >}}) — the immutable, single-version sibling for files such as screenshots and logs
- [Task file format]({{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments) — the `artifacts:` field alongside the rest of the frontmatter
- [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}) — the optional `aitask-artifacts` branch next to the other framework branches
- [Implementation trails]({{< relref "/docs/workflows/implementation-trails" >}}#where-a-trail-is-stored) — how a trail is stored and owned

---

**Next:** [Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}})
