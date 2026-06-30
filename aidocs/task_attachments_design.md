# Task Attachments — Initial Design

Framework-managed file attachments for aitasks (screenshots, PDFs, logs,
small binaries) with **guaranteed long-term storage** that does not rely on
the original source location remaining reachable.

Status: **initial design / RFC**. Surfaces the concept model, the chosen
storage shape, the backend adapter seam, and the decomposition into
implementable child tasks. Open questions are called out inline.

## 1. Goals & non-goals

### Goals

- Let a user **attach a file to a task** (screenshot, PDF, log excerpt) via a
  single CLI call, and have the framework guarantee it stays retrievable for
  the life of the task — even after the original file is moved or deleted.
- Make attachments **first-class metadata** in the task file's frontmatter,
  so downstream consumers (TUIs, the mobile app, the website) can discover
  them without parsing prose.
- Keep the **default backend zero-config**: no cloud account, no API keys,
  works on a fresh `ait setup`.
- Leave a **clean adapter seam** so additional backends (S3-compatible, GCS,
  GitHub release assets, GDrive) can land later without re-plumbing the rest
  of the framework.

### Non-goals (for v1)

- Editing attachments in place / collaborative diffing — attachments are
  immutable blobs keyed by content hash; an "edit" is a new attachment.
- Large-blob streaming (GB-scale media). Target is screenshots and small
  artefacts; we cap a per-attachment size and reject above it.
- Multi-backend per single attachment — each attachment lives in exactly
  one backend at rest, even though the local cache layer is universal.
- Sharing or public hosting — attachments are owned by the task and travel
  with it; "share this attachment" is a separate problem.

## 2. Core concept: content-addressed attachments

Every attachment is identified by the **SHA-256 of its bytes**. The task
file references the attachment by hash, never by raw URL or filesystem
path. This is the single decision that all other parts of the design hang
off:

- **Backend-agnostic references** — switching a task from local-only to
  S3-backed storage does not rewrite the task `.md`; only the resolution
  step changes.
- **Cheap deduplication** — re-attaching the same screenshot to a second
  task is free.
- **Verification on fetch** — the consumer can confirm the bytes match the
  hash, catching corruption or tampering.
- **Cache-coherent** — the local cache key (`<sha256>`) is identical to the
  remote object name in any backend that supports content-addressed naming.

## 3. Frontmatter schema

Tasks gain a new optional `attachments:` list field, parsed by the existing
`lib/yaml_utils.sh` helpers (with the small extension that the value is a
list of mappings rather than a list of scalars).

```yaml
---
priority: medium
effort: medium
issue_type: feature
status: Ready
attachments:
  - hash: sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
    name: login-screen-bug.png
    mime: image/png
    size: 184320
    added_at: 2026-06-18T12:34:56Z
    backend: local         # one of: local | s3 | gcs | gh-release | gdrive
    # backend-specific resolution hints (optional, advisory only):
    url: null
---
```

### Field rules

- `hash` is canonical and **required**; the prefix names the digest
  algorithm (`sha256:` for v1; future-proofs against algorithm migration).
- `name`, `mime`, `size` are advisory metadata for display and quota.
- `backend` records where the canonical copy currently lives. Changing
  backend is a planned operation (`ait attach move`), not a routine edit.
- `url` is an **opaque hint** for the backend resolver. Backends MUST be
  able to locate the blob from `hash` alone if `url` is missing or stale —
  the URL is a fast-path, never authoritative.

### Why hash-first, not URL-first

A URL-first scheme couples the task `.md` to the backend forever: any
backend migration rewrites history on the `aitask-data` branch. A
hash-first scheme means a future "move all attachments from local to R2"
operation never touches a single task file.

## 4. Storage layout

### Default (local) backend

Lives in the existing `.aitask-data` worktree on the `aitask-data` branch,
under a new top-level directory:

```
.aitask-data/
  aitasks/
  aiplans/
  attachments/
    blobs/<first-2-hex>/<remaining-62-hex>     # content-addressed blob
    meta/<first-2-hex>/<remaining-62-hex>.json # per-blob refcount ledger
    .attach.lock                               # global attach-transaction mutex
```

The 2-char prefix sharding keeps any single directory under a few thousand
entries even at scale.

The **refcount ledger is one metadata file per blob** (`meta/<2>/<62>.json`),
not a single global `index.json`. Each file records the blob-intrinsic fields
plus the set of tasks that reference the blob:

```json
{ "hash": "sha256:<hex>", "refs": ["130", "42_2"],
  "mime": "image/png", "size": 12345, "backend": "local" }
```

Per-blob files avoid a global write-hotspot: an `add`/`rm` rewrites only the
one blob's small file, so unrelated attachments never conflict on the shared
`aitask-data` branch. Per-task display fields (`name`, `added_at`) are **not**
stored here — they stay authoritative in the task frontmatter (the same bytes
can be attached to two tasks under different names). `refs` is the authoritative
input to archive-time garbage collection. The blob, its meta file, and the task
`.md` change are committed together in a single `ait git` commit (the whole
`add`/`rm` body runs under `.attach.lock`), so the three never drift. Any future
*aggregate* index is a generated cache / reporting artifact only — never the
source of truth.

### Remote backends (S3-compatible, GCS native, GitHub release assets, etc.)

Same content-addressed naming scheme, mapped to backend-native paths:

| Backend | Object name |
|---|---|
| Local | `.aitask-data/attachments/blobs/<2>/<62>` |
| S3-compat (R2, GCS-via-HMAC, B2, MinIO) | `s3://<bucket>/aitasks/attachments/<2>/<62>` |
| GCS native | `gs://<bucket>/aitasks/attachments/<2>/<62>` |
| GitHub release asset | `release tag = "attachments"`, asset name `<hash>` |

## 5. Backend adapter interface

A new `.aitask-scripts/lib/attachment_backend.sh` defines the contract,
implemented by per-backend modules in `.aitask-scripts/lib/attachment_backends/`:

```sh
attachment_backend_put    <hash> <file>          # upload, idempotent
attachment_backend_get    <hash> <dest>          # download to dest
attachment_backend_head   <hash>                 # exit 0 if present
attachment_backend_delete <hash>                 # remove from backend
attachment_backend_list                          # enumerate hashes
```

Dispatch follows the same **platform-extensible dispatcher pattern** as
`gitremoteproviderintegration.md` — a `case` on `$ATTACHMENT_BACKEND`
routes to the per-backend implementation. Backends register themselves by
dropping a file in `attachment_backends/` and adding a `case` arm to the
dispatcher.

### Universal local cache

Independently of the chosen backend, every machine maintains a local cache
at `~/.cache/ait/attachments/<hash>`. Resolution order:

1. Local cache hit → return path.
2. Backend `head` + `get` → populate cache → return path.
3. Miss in both → loud error, never silent placeholder.

The cache is purely a performance layer; the **canonical copy lives in the
backend**. A `local` backend short-circuits the cache by symlinking from
`.aitask-data/attachments/blobs/...`.

## 6. CLI surface

New top-level `ait attach` subcommand, dispatched from the existing flat
case in `ait`:

```
ait attach add  <task> <file> [--backend <name>] [--name <display>]
ait attach ls   <task>
ait attach get  <task> <name-or-hash> [--out <path>]
ait attach rm   <task> <name-or-hash>
ait attach move <task> <name-or-hash> --to <backend>
ait attach gc                          # orphan sweep using the per-blob meta files
```

`add` is the hot path: it hashes the file, writes the blob to the
configured backend, populates the local cache, updates `attachments:` in
the task frontmatter, `incref`s the blob's per-blob meta file, and commits
the trio under a single `./ait git` commit (the whole body under `.attach.lock`).

## 7. Backend options — comparison

The framework ships with **local** as v1. The shortlist for follow-on
backends:

| Backend | Setup cost | Auth UX | Storage cost (10 GB cold) | Notes |
|---|---|---|---|---|
| **Local (`.aitask-data` branch)** | none | none | free, but bloats the data repo | v1 default; perfect for small artefacts |
| **S3-compatible** (R2, S3, B2, MinIO, GCS via HMAC) | bucket + HMAC key | env vars / config file | $0.02–0.03/mo + egress | one adapter covers many providers; Cloudflare R2's zero egress is the standout |
| **GCS native** | bucket + ADC | `gcloud auth application-default login` | $0.02/mo (Archive) | best end-user auth UX; locks code to one provider |
| **GitHub release assets** | none beyond `gh` | `gh auth` | free for public repos | clumsy for granular per-task management; nice for "publish once" |
| **GDrive** | OAuth + token refresh | browser flow | free with Google account | heaviest auth, weakest IAM, share-link friendly |

Recommended order to implement:
1. **Local** (v1, blocking).
2. **S3-compatible** (fast-follow). One adapter, five providers.
3. **GCS native** (only if ADC UX is requested by a real user; the S3-compat
   adapter already covers GCS via HMAC).
4. Everything else as user demand surfaces.

## 8. Lifecycle

### Adding
`ait attach add` hashes → uploads via backend → caches locally → patches
frontmatter → `incref`s the blob's per-blob meta file → single commit.

### Fetching (on-demand by a consumer)
Cache → backend `get` → verify hash → serve. Never fabricate; missing
blobs are loud failures.

### Archival
**Resolved (t1030_3): archiving never decrefs.** Archiving a task is a status
change, not a dereference — an archived task is still a real referrer of its
attachments (browsable history), so `aitask_archive.sh` makes **no** change to
the ledger. A blob keeps a non-empty `refs` for as long as any task that
references it (active **or** archived) exists on disk, so it is never a GC
candidate. A blob becomes reclaimable only when it is **fully orphaned** —
every referrer dropped it via `ait attach rm`, or the referencing task file was
deleted (e.g. a folded task at archival, or a bundled archive). `ait attach rm`
stamps an `orphaned_at` epoch on the blob's meta when its `refs` empties; that
committed field (not filesystem mtime, which git does not preserve across
checkout) is the grace clock.

### Garbage collection
`ait attach gc` (opt-in) scans `attachments/meta/**.json`, finds zero-refcount
hashes, then under the global attach lock re-confirms each is still empty and,
as a belt-and-suspenders cross-check, that **no active or archived task**
frontmatter still lists it (Folded tasks are excluded — they are pending
deletion and their refs were rebound to the primary). Candidates older than
`attachments_gc_grace` are removed via `attachment_backend_delete` + meta-file
deletion. Archival never deletes blobs synchronously, because folded /
superseded tasks may resurrect.

### Archive retention — resolved (t1030_3)
A freshly archived task **keeps** its attachments indefinitely (archive is
browsable history) — its references block GC. The
`attachments_gc_grace` knob (project config `aitasks/metadata/project_config.yaml`,
default `30d`) governs only **fully-orphaned** blobs (the `ait attach rm` /
deleted-task case), not archived ones.

## 9. Cross-repo consumers

### Mobile app (`aitasks_mobile`)

The mobile app consumes tasks over the monitor-port WebSocket — it never
parses `.md` directly. Attachment support there is a separate, **paired**
child task:

- Wire-protocol extension: `TaskInfo.attachments: List<AttachmentRef>`
  (hash, name, mime, size).
- New control verb: `attachment_fetch(taskId, hash) → binary frame`.
- DBO + Room cache mirroring the framework's `attachments/<hash>` layout.
- Image-display in the task detail sheet (Coil or equivalent).

The framework parent task should carry `xdeprepo: aitasks_mobile` once
the framework side has a stable wire contract, signalling planning to
spawn the paired mobile work.

### Other consumers

The website renderer and `ait codebrowser` TUI should follow the same
"hash → cache → backend" resolution, factored out of the bash script
into a shared helper (Python `attachment_resolve.py`?).

## 10. Open questions

1. **Per-task vs per-blob backend.** v1 lets every attachment choose its
   own backend independently. Is that worth the complexity vs. "one
   backend per project"?
2. **Encryption at rest.** Do we need an `encrypted: true` flag with
   per-task or per-project keys, for sensitive screenshots? Probably not
   for v1; flag for v2 if a user asks.
3. **Size cap.** reject > 25 MB at `attach add` time. **Resolved (t1030_2):**
   configured via `attachment_max_size_mb` in `aitasks/metadata/project_config.yaml`
   (default 25), not the execution profile — `ait attach` does not run inside an
   execution profile. Above the cap, suggest a remote backend / `gh release upload`.
4. **Ledger format.** **Resolved (t1030_2):** one JSON file **per blob**
   (`attachments/meta/<2>/<62>.json`), not a single global `index.json`. Per-blob
   files win on git-diffability *and* concurrency (no global write-hotspot; an
   `add`/`rm` rewrites only one small file). All mutations serialize on the global
   `.attach.lock`; the JSON ops are set-based and idempotent (rebase-safe). Any
   future aggregate index would be a generated cache only.
5. **Hash algorithm migration.** The `sha256:` prefix is the escape
   hatch. Document the migration recipe before we ever need it.
6. **`fold` semantics.** When task A is folded into task B, do A's
   attachments transfer to B? Yes — they should re-bind to B (the `rebind`
   subcommand updates every per-blob meta file's `refs`) at fold time.

## 11. Suggested decomposition

Parent: `tNNN_task_attachments` in this repo. Proposed children, in
implementation order:

1. **Frontmatter + CLI scaffold** — `attachments:` field parsing, `ait
   attach ls`, hash computation, no actual storage yet.
2. **Local backend + cache + per-blob ledger** — `attach add/get/rm` over the
   `aitask-data` worktree; single-transaction commit flow; per-blob meta-file
   refcount.
3. **Archive integration** — decref on archive, `ait attach gc`, grace
   knob.
4. **Adapter seam refactor** — extract `attachment_backend.sh`, prove the
   contract holds against the local backend.
5. **S3-compatible backend** — first remote backend; bucket setup docs;
   profile config for endpoint / bucket / HMAC creds.
6. *(fast-follow, optional)* **GCS-native backend** — ADC auth path.
7. *(fast-follow, optional)* **GitHub release assets backend**.

Sister task in `aitasks_mobile` (paired via `xdeprepo`, blocked on
step 4 being stable):

- **Wire-protocol attachment refs** — extend `TaskInfo`, add
  `attachment_fetch` verb, DBO + cache mirror, UI in the task detail
  sheet.

## 12. Cross-references

- Existing platform-extensible dispatcher pattern (the model for the
  backend adapter): [`gitremoteproviderintegration.md`](gitremoteproviderintegration.md).
- Documentation conventions for any user-facing prose generated from
  this design: [`framework/documentation_conventions.md`](framework/documentation_conventions.md).
- Extension points reference for slot-in mechanics:
  [`framework/aitasks_extension_points.md`](framework/aitasks_extension_points.md).
- Cross-repo notation used to pair the mobile follow-up:
  [`framework/cross_repo_references.md`](framework/cross_repo_references.md).
