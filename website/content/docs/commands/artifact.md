---
title: "Artifact"
linkTitle: "Artifact"
weight: 33
description: "ait artifact — create, version, fetch and move a task's handle-addressed artifacts"
depth: [intermediate]
---

`ait artifact` manages a task's artifacts — versioned outputs such as HTML
plans, implementation trails and reports, each reached through a stable
`art:<id>` handle. For the model (handle, manifest, backends) and when to pick
each backend, see the [Artifacts concept page]({{< relref "/docs/concepts/artifacts" >}}).

## ait artifact

```bash
ait artifact create 42 plan.html --kind html_plan    # Create v1 on t42 → art:t42-htmlplan
ait artifact update art:t42-htmlplan plan.html       # Store a new version
ait artifact versions art:t42-htmlplan               # List versions (* = current)
ait artifact get art:t42-htmlplan --out /tmp/p.html  # Fetch the current version
ait artifact ls 42                                   # List t42's artifacts
ait artifact ls                                      # List every artifact
ait artifact move art:t42-htmlplan --to gitbranch    # Move every version to another backend
ait artifact rm 42 art:t42-htmlplan                  # Remove it from t42
```

| Verb | Description |
|------|-------------|
| `create <task> <file> --kind <kind> [--name <label>] [--handle art:<id>] [--backend <n>]` | Create an artifact (v1) on a task |
| `update <handle> <file>` | Store a new version and make it current |
| `move <handle> --to <backend>` | Copy every version to a registered backend, then repoint the manifest |
| `rm <task> <handle-or-name>` | Remove an artifact reference from a task (alias `remove`) |
| `ls [<task>]` | List a task's artifacts, or every artifact (alias `list`) |
| `get <handle> [--out <path>] [--version <sha256:hash>]` | Fetch the current (or a specific) version |
| `versions <handle>` | List versions oldest first |
| `init-store <backend>` | Initialize a backend's store |
| `gitbranch-migrate --from <old> --to <new>` | Move the `gitbranch` store to another branch |
| `help` | Show the built-in help (also `--help`, `-h`) |

`<task>` accepts a parent id (`16`) or a child id (`16_2`), with or without the
leading `t`.

### create

Stores `<file>` as version 1, writes the artifact's manifest, adds an entry to
the task's `artifacts:` frontmatter and commits them together. It prints the
handle on its last line as `HANDLE:<handle>`.

| Option | Description |
|--------|-------------|
| `--kind <kind>` | **Required.** What the artifact is (`html_plan`, `mockup`, `report`, …): lowercase letters, digits and `_`, starting with a letter, at most 32 characters. An open set |
| `--handle art:<id>` | The handle to use (`art:` + lowercase letters, digits, `.`, `_`, `-`). Without it the handle is derived as `art:t<task>-<kind without underscores>`, and a child id's `_` becomes `.` — `ait artifact create 16_2 x.html --kind html_plan` creates `art:t16.2-htmlplan` |
| `--name <label>` | A display label stored in the frontmatter entry. Without it the entry has no name |
| `--backend <name>` | The backend to store the blobs on. Without it, `artifacts.default_backend` from the [configuration](#configuration) is used, or `local` when that is unset |

`create` refuses:

- a handle that already has a manifest;
- a file larger than the size cap — `artifact_max_size_mb`, 25 MB by default;
- an archived task, whether its file is still under `aitasks/archived/` or
  already packed into a numbered archive. A new artifact must attach to an
  active task; `ls` and `get` keep working on archived owners.

### update

Stores a new version, appends it to the manifest's version list and makes it
current. It **never touches the task file** — only the manifest and the blob
store. A file whose bytes equal the current version changes nothing. The size
cap applies as for `create`. The version is stored on the backend the manifest
names.

### move

Copies every version to the target backend, verifies each copy, then repoints
the manifest. The target must be registered in the
[configuration](#configuration). The source blobs are **not deleted**, so a move
can be repeated or undone by moving back. If it fails part-way, the copies it
made are removed and the manifest is unchanged; run it again to retry.

Moving to the backend the artifact is already on does nothing and reports that.
In particular, `move --to gitbranch` cannot change *which branch* the `gitbranch`
backend uses — that is [`gitbranch-migrate`](#gitbranch-migrate).

### rm

Removes the artifact's entry from the task file. `<handle-or-name>` is the
handle or the entry's name.

- When **another task** still lists the handle, only this task's entry goes; the
  manifest stays.
- Otherwise the manifest is deleted as well, and any copy of its versions on the
  **`local`** store that nothing else references (no other artifact, no
  attachment) is deleted in the same commit — recoverable from data-branch
  history. Blobs on a `dir` or `gitbranch` store are left in place, with a
  warning.
- An entry whose manifest is missing is still removed, so a stale reference can
  always be repaired with `rm`.

`rm` works on an archived task whose file is still under `aitasks/archived/`,
but not on one packed into a numbered archive.

### ls

With a task, prints one row per artifact:

```
HANDLE                                    KIND          CURRENT         VERS   BACKEND   NAME
art:t42-htmlplan                          html_plan     9c1f0a7d2e44    3      local
```

Without a task, prints every artifact in the project with its `HANDLE`,
`CURRENT` and `BACKEND` columns. **CURRENT is abbreviated** to the first 12 hex
digits; `get --version` needs the full value from `versions`. A reference whose
manifest is missing prints `?` columns and a warning that names the `rm`
command to repair it. A project or task with none prints `No artifacts.`

### get

Writes the current version — or the one named by `--version` — to stdout, or to
`<path>` with `--out`. The bytes come from the local cache when present and are
otherwise fetched from the backend; either way they are checked against the
version's hash, and a mismatch is an error. A cached version can be fetched
offline, on every backend.

`--version` takes a full `sha256:<64 hex>` value that `versions` lists for this
handle; anything else is refused.

### versions

Lists every version, oldest first. The current one is marked `*`:

```
  sha256:4b0e…
* sha256:9c1f…
```

### init-store

Initializes a registered backend's store once:

- **`dir`** — required. Run it with the share **mounted**: it writes a marker
  into the configured root, and every `dir` operation refuses a root without it,
  so an empty mountpoint or a wrong path is never mistaken for the store.
- **`gitbranch`** — optional. The first write creates the store anyway;
  `init-store gitbranch` creates it now, and also publishes to `origin` a store
  that so far exists only in your clone.
- **`local`** — reports that it needs no initialization.

Running it again on an initialized store changes nothing.

### gitbranch-migrate

Moves the `gitbranch` store from branch `<old>` to branch `<new>`, keeping its
identity. This is the only way to rename the branch once the store exists.

1. Every blob on `<old>` is copied to `<new>`.
2. `<old>` is **retired**: it stays readable, but every write to it is refused.
   Retirement is permanent.
3. Anything written to `<old>` before it was retired is copied too, and `<new>`
   is verified to hold every blob.
4. The project's store record (see [below](#the-gitbranch-backend)) is updated to
   `<new>` and committed.

It prints `MIGRATED:<store-id>:<new>`, or `ALREADY_MIGRATED:<store-id>:<new>`
when there was nothing left to do, so it is safe to run again. If a step fails,
it lists any effect that may already have happened on `origin` (a branch that
advanced, a branch that may have been retired) followed by
`Resume with: <the same command>`.

Then set `artifacts.backends.gitbranch.branch: <new>` in the configuration —
the command warns until you do, and until then every `gitbranch` operation
refuses. `project_config.yaml` lives on the task data branch with the store
record, so once you commit the new setting, teammates pick up both when they
pull it.

### The gitbranch backend

The store is a dedicated branch carrying only artifact blobs, written directly
with git plumbing — it is never checked out. Its marker file holds a random
store id, and the project records that id and the branch name in
`artifacts/gitbranch_store.json` on the task data branch, written by the first
`gitbranch` write. The branch itself is created by that first write, or by
`init-store gitbranch`.

**With an `origin`**, `origin` is the store of record. A write succeeds only
once the push is accepted; if `origin` cannot be reached the write fails rather
than storing blobs only this clone has. A push whose outcome cannot be confirmed
exits with status **75** and reports the outcome as unknown — `origin` may have
applied it — never as "nothing published". **Without an `origin`**, the local
branch is the store of record and nothing is pushed; a store created before
`origin` was added is published by the next write or by `init-store gitbranch`.

Reads need no network when the version is already cached, and `rm` and `ls`
never touch the store.

**What gets downloaded.** The store branch is an ordinary branch on the remote,
so a plain `git clone` downloads its whole history, and so does `ait sync`.
`git clone --single-branch` leaves it out. Reading a version that is not cached
fetches the **whole store branch**, not just that one blob; later reads of the
same version come from the cache. Removing an artifact never shrinks the store:
`rm` leaves the bytes in place, and a deleted blob stays in the branch history.

`artifacts.backends.gitbranch.branch` must:

- start with a letter or digit and use only letters, digits, `.`, `_`, `/` and
  `-`, with nothing git itself would refuse as a branch name;
- not be `main`, `master`, `aitask-data`, `aitask-locks`, `aitask-ids` or
  `HEAD`;
- name a branch that does not exist yet, or one that already is this store. An
  existing branch without the store marker is refused, and nothing is written
  to it.

The configured branch must match the project's store record. After a rename
every `gitbranch` operation refuses with a message naming the
[`gitbranch-migrate`](#gitbranch-migrate) command; when the record is missing
while `gitbranch` artifacts exist, they refuse and tell you to restore it from
data-branch history.

### Uncommitted changes

`create`, `update`, `move`, `rm` and `gitbranch-migrate` commit whole files —
the task file, the artifact's manifest, the store record. So each one **refuses
to start** when a file it would commit already has uncommitted changes, because
the commit would otherwise absorb your edit. The error names the file; commit or
revert it and run the command again. Blob files are never checked: a blob's path
is its hash, so there is no edit to absorb.

If a command fails part-way, it restores the files it touched to their
pre-command contents, or lists each one it could not restore together with how
to recover it.

## Configuration

Backends are registered in the `artifacts:` block of
`aitasks/metadata/project_config.yaml`, which is git-tracked and shared by the
team — never put credentials there. `local` is always available and needs no
entry; omit the block entirely to use it.

```yaml
artifacts:
  default_backend: gitbranch
  backends:
    gitbranch:
      branch: aitask-artifacts
```

| Key | Default | Description |
|-----|---------|-------------|
| `artifacts.default_backend` | `local` | The backend `create` uses when `--backend` is not given |
| `artifacts.backends.dir.path` | — | Absolute path of the shared directory; every teammate mounts it there. Initialize it once with `init-store dir` |
| `artifacts.backends.gitbranch.branch` | — | The store's branch. Change it only through [`gitbranch-migrate`](#gitbranch-migrate) once the store exists |
| `artifact_max_size_mb` | `25` | Largest file `create` and `update` accept, in MB |

The [Settings TUI]({{< relref "/docs/tuis/settings" >}}) edits the default
backend and the `gitbranch` branch in its **Artifacts** tab (`k`). A `dir`
backend is not configurable there — write its `path` by hand first. Saving from
the tab rewrites `project_config.yaml` without its comments.

[`ait attach`]({{< relref "/docs/commands/attach" >}}) shares the blob store and
local cache, but attachments always use the `local` backend.
