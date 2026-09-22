---
title: "Attach"
linkTitle: "Attach"
weight: 34
description: "ait attach — manage a task's content-addressed file attachments"
depth: [intermediate]
---

`ait attach` manages a task's file attachments — content-addressed blobs stored
beside the task rather than inside it. For the conceptual model (content
addressing, where blobs live, reference counting), see the
[Attachments concept page]({{< relref "/docs/concepts/attachments" >}}).

## ait attach

```bash
ait attach add 42 screenshot.png                  # Attach a file to t42
ait attach add 42 out.log --name crash-log.txt    # Attach under a different name
ait attach ls 42                                  # List t42's attachments
ait attach get 42 crash-log.txt --out /tmp/c.txt  # Fetch an attachment to a file
ait attach get 42 crash-log.txt | less            # ...or to stdout
ait attach rm 42 crash-log.txt                    # Detach it from t42
ait attach gc                                     # Reclaim fully-orphaned blobs
```

| Verb | Description |
|------|-------------|
| `ls <task>` | List a task's attachments (alias `list`) |
| `add <task> <file> [--name <name>] [--backend local]` | Attach a file |
| `get <task> <name-or-hash> [--out <path>]` | Fetch an attachment's bytes |
| `rm <task> <name-or-hash>` | Detach an attachment from a task (alias `remove`) |
| `gc` | Delete blobs nothing references any more |
| `help` | Show the built-in help (also `--help`, `-h`) |

`<task>` accepts a parent id (`16`) or a child id (`16_2`), with or without the
leading `t`.

### ls

Prints one row per attachment:

```
NAME                          HASH            SIZE        BACKEND
crash-log.txt                 1f8b034f74a1    4821        local
```

The **HASH column is abbreviated** to the first 12 hex digits for display. It
is not accepted by `get` or `rm` — pass the attachment's name, or copy the full
`hash:` value from the task file's `attachments:` block.

A task with none prints `No attachments.` An entry whose `hash` is missing or
malformed makes `ls` exit with an error naming the entry.

### add

Hashes the file, stores it, adds the task to the blob's reference ledger,
appends an entry to the task's `attachments:` frontmatter and commits all three
as one `ait: Attach <name> to t<N>` commit.

| Option | Description |
|--------|-------------|
| `--name <name>` | Display name for the attachment. Defaults to the file's basename |
| `--backend <name>` | Storage backend. Only `local` is accepted; any other value is an error |

`add` refuses:

- a file larger than the size cap — `attachment_max_size_mb` in
  `aitasks/metadata/project_config.yaml`, 25 MB by default;
- a file whose bytes are already attached to the same task (the error names the
  existing attachment);
- a name already used by another attachment on the same task — pass `--name` to
  choose a different one.

Attaching the same bytes to a *different* task is allowed and stores nothing
new: the existing blob gains a second reference.

### get

Resolves `<name-or-hash>` against the task's `attachments:` entries, fetches the
blob, checks that its bytes hash back to the recorded hash, and writes them to
stdout — or to `<path>` with `--out`.

`<name-or-hash>` must be one of:

- the full hash, `sha256:<64 hex digits>`;
- the same 64 hex digits without the `sha256:` prefix;
- the attachment's exact name.

A hash match wins over a name match. There is **no prefix matching** — an
abbreviated hash, such as the one `ls` prints, matches nothing. A hash mismatch
on fetch is an error; the bytes are not written.

### rm

Removes the attachment's entry from the task file and the task from the blob's
reference ledger, committed together as one commit. `<name-or-hash>` resolves
exactly as for `get`.

`rm` **does not delete the blob.** When it removes the last reference, the
ledger records the time the blob became orphaned; the blob itself is reclaimed
only by a later `ait attach gc`.

### gc

Deletes blobs that nothing references any more, together with their ledger
files, in one commit. It takes no arguments, and nothing runs it automatically.

A blob is deleted only when **all** of these hold:

1. its reference ledger lists no task;
2. no active or archived task lists its hash in `attachments:` (tasks with
   status `Folded` are ignored — their references already moved to the primary
   task);
3. no version of any artifact references it;
4. if the ledger records when the blob became orphaned, at least
   `attachments_gc_grace` has passed since then.

A blob with no recorded orphan time is **not** protected by the grace window:
once conditions 1–3 hold it is deleted on the next run. `ait attach rm` and task
deletion from `ait board` always record the time, so this applies to blobs
orphaned some other way.

If an artifact manifest cannot be read, `gc` stops before deleting anything and
names the file. It finishes with a summary line:

```
gc: swept 2 orphaned attachment(s), retained 5 referenced/in-grace blob(s)
```

### Uncommitted changes

`add`, `rm` and `gc` commit whole files. So each one **refuses to start** when a
file it would commit — the task file, or a blob's ledger file — already has
uncommitted changes, because the commit would otherwise absorb your edit. The
error names the file; commit or revert it and run the command again. Blob files
are never checked: a blob's path is its hash, so there is no edit to absorb.

If a command fails part-way, it restores the files it touched to their
pre-command contents, or lists each one it could not restore together with how
to recover it.

### Not available

`ait attach help` lists `move <task> <name-or-hash> --to <backend>`, but it is
not implemented: it exits with an error. `decref-deleted` is internal to task
deletion in `ait board` and is not meant for manual use.

## Configuration

Both keys live in `aitasks/metadata/project_config.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `attachment_max_size_mb` | `25` | Largest file `ait attach add` accepts, in MB |
| `attachments_gc_grace` | `30d` | How long an orphaned blob with a recorded orphan time is kept before `ait attach gc` may delete it. A whole number with an `s`, `m`, `h` or `d` suffix (`30d`, `24h`, `90m`, `120s`), or a plain number of seconds |
