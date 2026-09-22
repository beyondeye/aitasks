---
title: "Attachments"
linkTitle: "Attachments"
weight: 55
description: "Content-addressed files attached to a task — identified by their hash, never by a path."
depth: [intermediate]
---

## What it is

An **attachment** is a file — a screenshot, a log, a PDF — stored with a task
and identified by the SHA-256 of its bytes. The hash is the attachment's
identity; its name is only a label. The task file records each attachment in a
nested `attachments:` block in its frontmatter:

```yaml
attachments:
  - hash: sha256:1f8b034f74a1…
    name: crash-log.txt
    mime: text/plain
    size: 4821
    added_at: 2026-08-14 09:12
    backend: local
```

`ait attach` copies the file's bytes into the task data branch, so the
attachment stays retrievable after the original file is moved, edited or
deleted.

### Identity is the hash

A task never refers to an attachment by path or URL. It refers to it by
`hash`, whose `sha256:` prefix names the digest algorithm. Everything else
follows from that choice:

- **The source can go away.** Nothing about the reference depends on where the
  file came from, so moving or deleting the original cannot break it.
- **Identical bytes are stored once.** Attach the same screenshot to two tasks
  and there is one stored blob with two references. Each task can give it its
  own name, because the name lives in the task file, not with the blob.
- **Fetches are verified.** `ait attach get` hashes the bytes it is about to
  hand you and refuses them if they do not match the recorded hash, so a
  corrupted copy is an error rather than a silently wrong file.
- **The hash is the address.** The blob's storage path and its cache key are
  both derived from the hash, so no lookup table maps names to files.

An "edit" to an attachment is therefore a different attachment: different
bytes, different hash.

### The `attachments:` block

Each entry carries six fields. Two of them describe the attachment *on this
task*; the rest describe the blob itself:

| Field | Belongs to | Meaning |
|---|---|---|
| `hash` | blob | `sha256:<64 hex digits>` — the identity |
| `name` | this task | Display label; defaults to the file's basename, unique per task |
| `added_at` | this task | When it was attached (`YYYY-MM-DD HH:MM`) |
| `mime` | blob | Detected content type |
| `size` | blob | Size in bytes |
| `backend` | blob | Where the stored copy lives |

The block is written by `ait attach add` and `ait attach rm` and is never
hand-edited: the stored blob and its reference ledger are updated in the same
commit, and an entry edited by hand no longer matches them.

### Where blobs live

Blobs and their ledger live in the task data worktree, beside `aitasks/` and
`aiplans/`, sharded by the first two hex digits of the hash:

```text
.aitask-data/
  attachments/
    blobs/<first 2 hex>/<remaining 62 hex>        the file's bytes
    meta/<first 2 hex>/<remaining 62 hex>.json    reference ledger for that blob
    .attach.lock                                  serializes every change
```

`local` — this layout, committed on the task data branch — is the only backend
`ait attach add` accepts, and there is no command to move an attachment to
another backend. Each machine also keeps a cache under
`~/.cache/ait/artifacts/<hash>`; for the local backend a cache entry is a
link to the stored blob.

### One commit per change

`ait attach add` writes three things: the blob, the blob's ledger entry and the
task file. All three are committed together as one `ait:` commit, while the
attach lock is held, so they cannot drift apart. `ait attach rm` commits the
ledger entry and the task file the same way.

Because a commit stages each of those paths whole, a verb **refuses to start**
when the task file or a ledger file it would commit already has uncommitted
changes — otherwise your unrelated edit would be swept into the `ait:` commit.
Commit or revert the edit, then run the command again. Blobs are exempt from
the check: a blob's path is its hash, so there is no edit to absorb.

If a transaction fails part-way, it restores the paths it touched to their
pre-transaction contents, or reports exactly which ones it could not restore.

### Reference counting and gc

Each blob's ledger file lists the tasks that reference it (`refs`). The ledger
is one small file per blob rather than one shared index, so two unrelated
attachments never contend for the same file on the shared data branch.

How the references change over a task's life:

- **`ait attach add`** adds the task to the blob's `refs`.
- **`ait attach rm`** removes the task from `refs` and the entry from the task
  file. It **does not delete the blob**. When the last reference goes, the
  ledger records the time the blob became orphaned.
- **Archiving** changes nothing. An archived task is still a real referrer — its
  history stays browsable — so its attachments are kept indefinitely.
- **Folding** a task into another moves its references to the primary task
  (see [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})).
- **Deleting** a task from `ait board` releases its references, or hands them to
  any folded task the delete revives.

Blobs are only reclaimed by an explicit `ait attach gc`, which deletes a blob
only when nothing references it: no ledger reference, no active or archived
task listing its hash, and no artifact version pointing at it. A blob whose
orphan time is recorded is also kept until the grace window has passed
(`attachments_gc_grace`, 30 days by default). The command reference has the
exact rules.

## Why it exists

Files that explain a task — the screenshot of the bug, the log that shows it —
are usually somewhere temporary: a downloads folder, a scratch directory, a
chat upload. A task that points at them loses them. Attachments copy the bytes
into the task data branch, keyed by their hash, so they travel with the task
and stay fetchable for as long as it exists, active or archived.

Keying by content rather than by name is what keeps that cheap: re-attaching a
file costs nothing, a copy can always be checked against the task's record,
and a per-blob ledger keeps concurrent attach operations from colliding on the
shared data branch.

## How to use

```bash
ait attach add 42 screenshot.png         # attach a file to t42
ait attach ls 42                         # list t42's attachments
ait attach get 42 screenshot.png --out /tmp/shot.png
```

The full verb reference — flags, refusals and the gc rules — is on the
[`ait attach` command page]({{< relref "/docs/commands/attach" >}}).

## See also

- [`ait attach`]({{< relref "/docs/commands/attach" >}}) — the command reference.
- [Task file format]({{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments) — the `attachments:` field alongside the rest of the frontmatter.
- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — the files attachments belong to.
- [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}}) — how folding moves attachment references to the primary task.
