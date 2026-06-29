---
Task: t1030_2_local_backend_cache_index.md
Parent Task: aitasks/t1030_task_attachments_support.md
Sibling Tasks: aitasks/t1030/t1030_1_frontmatter_cli_scaffold.md, aitasks/t1030/t1030_3_archive_gc_fold_rebind.md
Archived Sibling Plans: aiplans/archived/p1030/p1030_1_frontmatter_cli_scaffold.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-29 10:14 (verify path — re-confirmed + per-blob-meta redesign)
---

# Plan — t1030_2 Local backend + per-blob metadata ledger + cache + adapter seam

Make `ait attach add/get/rm` fully functional over `.aitask-data` with a
content-addressed local backend, a universal cache, a **per-attachment metadata
ledger** (one JSON file per blob — *not* a single global index), and a
**generalizable backend adapter seam**. Builds on t1030_1.

Design: `aidocs/task_attachments_design.md` §2/§4/§5/§8;
generalizability target `aidocs/unified_artifact_design.md` §5.
Full spec in the task file `aitasks/t1030/t1030_2_local_backend_cache_index.md`.

## Context

Second of three children of parent **t1030** (framework-managed file
attachments, content-addressed by SHA-256). t1030_1 landed the **pure, headless
primitives** and a read-only `ait attach ls`; this child builds the **storage
core** on top of them. The adapter seam is built **here, upfront** (not deferred)
so the design is clean from the start and t1076_1's generalization
(`attachment_backend` → `artifact_backend`) becomes a rename-and-widen, not a
re-plumb. This task establishes the **per-blob metadata schema** and backend
contract that t1030_3 (archive/gc/fold) and the S3/GDrive follow-ups consume.
Storage write-path (add/get/rm) is in scope; GC, archive-decref and fold-rebind
are explicitly **t1030_3**.

## Key design decision — per-attachment metadata files (supersedes index.json)

**The canonical lifecycle ledger is one metadata file per blob**, not a single
global `attachments/index.json`. Rationale (user-directed, 2026-06-29):

- A single `index.json` is a **global write hotspot** — every add/rm/rebind
  rewrites the whole file, manufacturing conflicts between *unrelated*
  attachments on the shared `.aitask-data` branch.
- It **scales poorly**: every mutation parses and rewrites the entire ledger.
- Per-blob files give **better concurrency** (lock per blob, not globally),
  **smaller diffs**, easier inspection, and **isolate corruption/conflict** to a
  single attachment.

> **Deviation from written design — recorded, not silent.** Design §4 specifies
> `attachments/<2>/<62>` blobs + a single `attachments/index.json` ledger. This
> plan supersedes that with the per-blob layout below. The **Coordination /
> doc-sync** step updates design §4 and t1030_3's task note so the spec and
> siblings do not drift. Any *future* aggregate index becomes a **generated
> cache / reporting artifact only — never the source of truth.**

### Storage layout (local backend)

```
.aitask-data/attachments/
  blobs/<2>/<62>            # content-addressed blob (canonical bytes)
  meta/<2>/<62>.json        # canonical per-blob metadata + refcount ledger
  .attach.lock             # single global attach-transaction mutex (registry_lock dir)
```

`<2>/<62>` is the existing `attachment_shard_path` fragment (t1030_1). Blobs and
metadata live in **sibling `blobs/`/`meta/` subtrees** — self-documenting and
collision-free (a 2-hex shard dir can never equal `blobs`/`meta`). No
`index.json` anywhere.

The per-blob layout is what delivers the concurrency/diff/conflict-isolation
win (each mutation rewrites only its own small file — no global-ledger
hotspot, no merge conflicts between *unrelated* attachments). **Mutual
exclusion is a separate, single global lock** (`.attach.lock`, see Step 3a):
attach mutations are brief and infrequent, and the shared `.aitask-data` Git
index is single-writer regardless, so one global transaction lock is the
simplest *correct* shape — it does **not** reintroduce the index.json
write-hotspot (that was a *shared-mutated-file* problem, not a lock-granularity
one).

### Per-blob metadata schema (`meta/<2>/<62>.json`)

Blob-intrinsic fields + the refcount set only. **Per-task display fields
(`name`, `added_at`) stay authoritative in the task frontmatter**, never here
(the same bytes can attach to two tasks under different names; the ledger must
not have to pick one):

```json
{
  "hash": "sha256:<hex>",
  "refs": ["1030_2", "42"],
  "mime": "image/png",
  "size": 12345,
  "backend": "local"
}
```

`refs` is the refcount source of truth. `mime`/`size` are byte-intrinsic (equal
for every ref); `backend` is where the canonical copy lives. A later ref
reporting a *different* `mime`/`size` for the same hash ⇒ collision or caller
bug ⇒ `die` loudly, never overwrite.

## Verification of assumptions (verify path — 2026-06-29)

Re-confirmed against the current tree:

- **t1030_1 surfaces landed (clean inputs):** `lib/attachment_utils.sh` exports
  `attachment_sha256` (`:26`), `attachment_validate_hash` (`:53`),
  `attachment_shard_path` (`:62`, returns the bare `<2>/<62>` fragment),
  `attachment_cache_path` (`:73`) — reuse these, do not re-derive. `lib/yaml_utils.sh`
  `read_yaml_mappings` (~`:169+`) output contract: one `key=value` per present
  field, records separated by a single blank line, split on the **first `=`**.
  `aitask_attach.sh` dispatcher has `cmd_stub` (`:102`) for `add/get/rm/move/gc`
  (`:109–113`) — replace `add/get/rm`, leave `move/gc` (t1030_3).
- **Infra reference points exist:** `_ait_detect_data_worktree()`
  (`task_utils.sh:35`) + `task_git()` (`:168`, runs `git -C .aitask-data`);
  `resolve_python`/`require_python` (`lib/python_resolve.sh`);
  `lib/gate_orchestrator.py` (Python-helper precedent: atomic write + hashlib);
  **`lib/registry_lock.sh`** fail-safe mutex
  (`registry_lock_acquire <lock_dir> [timeout]` → 0 held / 1 busy;
  `registry_lock_release`; owner-token, EXIT-trap auto-release);
  `setup_fake_aitask_repo()` (`tests/lib/test_scaffold.sh:13`).
  `project_config.yaml` scalar/list reads have precedent in
  `lib/gate_verifier_lib.sh` / `lib/tmux_bootstrap.sh`.
- **Data-branch mode active** (`.aitask-data` present); `attachments/` does not
  exist yet (this task creates it).
- **Risk-gated:** effective gate set = `risk_evaluated` (fast profile
  `default_gates`) → `## Risk` section authored here; fields written post-approval
  at Step 7.

## Step 1 — Adapter seam `lib/attachment_backend.sh` (NEW)
- Dispatcher: `case "${ATTACHMENT_BACKEND:-local}" in local) … ;; *) die ;; esac`
  with a `# BACKEND-EXTENSION-POINT` marker (mirror the platform-extensible
  dispatcher pattern in `aidocs/gitremoteproviderintegration.md`).
- Public contract (names/shape per design §5 so t1076_1 widens to
  `artifact_backend`): `attachment_backend_put <hash> <file>`,
  `…_get <hash> <dest>`, `…_head <hash>`, `…_delete <hash>`, `…_list`. Keep the
  dispatcher + cache layer **`local`-agnostic** — no local-only assumptions leak
  above the per-backend module. (The backend contract is about **blobs only**;
  the metadata ledger is a separate, backend-independent concern in Step 3.)

## Step 2 — `lib/attachment_backends/local.sh` (NEW)
- Resolve data worktree via `task_utils.sh` `_ait_detect_data_worktree`.
- Blobs at `attachments/blobs/<2>/<62>` (compose `attachments/blobs/` +
  `attachment_shard_path`). `put` = **idempotent atomic copy** (write to a temp
  file in the shard dir, `mv` into `<62>`; skip if `head` already true);
  `get` = copy to dest; `head` = `test -f`; `delete` = `rm`; `list` = enumerate
  `blobs/**` shard files.

## Step 3 — `lib/attachment_meta.py` (NEW — per-blob metadata ops, replaces the planned index.py)
- Run via `lib/python_resolve.sh` `resolve_python` (precedent:
  `gate_orchestrator.py`). Each subcommand resolves the per-blob file path from
  the hash: `attachments/meta/<2>/<62>.json`. Atomic write (temp + `os.replace`)
  of that single file — so a concurrent reader always sees a complete old-or-new
  file, never a torn write.
- **Pure mutation primitive — `attachment_meta.py` NEVER acquires a lock.**
  Locking is entirely the **caller's** responsibility (Step 3a): `add`/`rm` run
  the whole transaction under the single global attach lock and call these as
  plain mutations; standalone/administrative callers (t1030_3 `gc`/fold) MUST
  wrap any *mutation* subcommand in the same global attach lock. Keeping the
  primitive lock-free is what makes the single-lock transaction possible without
  nested-lock issues (mirrors the pure, stateless t1030_1 helpers).
- **Set-based, idempotent mutations (rebase-safe):**
  - `incref <hash> <task> [mime=… size=… backend=…]` — load-or-create the blob's
    meta file, **add task to the `refs` set** (no-op if present), set
    blob-intrinsic fields on first write (verify-don't-overwrite on later
    writes), atomic write.
  - `decref <hash> <task>` — **discard task from the `refs` set** (no-op if
    absent), atomic write. Leaves the file in place even at `refs:[]` (the file +
    blob are deleted by t1030_3 `gc`; `zero-refcount` lists them as candidates).
  - `refs <hash>` — print the refs of one blob.
  - `zero-refcount` — **scan `attachments/meta/**.json`**, print hashes whose
    `refs` is empty (GC candidates; consumed by t1030_3). Scan cost acceptable
    for v1.
  - `rebind <old_task> <new_task>` — **scan `attachments/meta/**.json`**, replace
    `old_task` with `new_task` in every `refs` set, atomic-write each touched file
    (fold support; consumed by t1030_3, which calls it under the global attach
    lock).
- Idempotency (set semantics) makes a re-applied op after a cross-host
  `task_sync` rebase safe — re-running `incref` for an already-listed task does
  not double-count.
- **Reads are lock-free; scan results are advisory (concern #6).** `refs` and
  `zero-refcount` take no lock (atomic writes guarantee untorn reads).
  `zero-refcount`'s output is a *candidate* list; a concurrent `incref` can make a
  candidate live between the scan and any action on it. Any **destructive**
  consumer (t1030_3 `gc`/`delete`) MUST run **under the global attach lock** and
  re-read `refs` to confirm it is still empty **before** deleting the blob+meta.
  State this contract in the helper's docstring so t1030_3 inherits it.

## Step 3a — Locking: ONE global attach-transaction lock for the whole add/rm body
Reuse `lib/registry_lock.sh` (`registry_lock_acquire <lock_dir> [timeout]` → 0
held / 1 busy; `registry_lock_release`; mkdir-based, owner-token, dead-PID steal,
EXIT-trap auto-release). Fail-safe: on busy/timeout **`die`** ("another `ait
attach` operation is in progress — retry"); never proceed unlocked.

**A single global attach lock `attachments/.attach.lock` wraps the *entire*
`add`/`rm` body as one indivisible transaction:** size-cap/duplicate checks →
`attachment_backend_put` → `attachment_meta.py` mutation → frontmatter mutation →
explicit stage → single commit → (on failure) rollback. The lock is acquired
once at the top of the verb and released once at the very end (success or
rollback).

**Why a single transaction lock, not split per-phase (concern this round).** If
the metadata mutation and the commit are under *different* locks (or the meta
lock is released before commit), the incref becomes **visible on disk and
committable by another same-hash operation before the matching frontmatter is
committed**. A second op could observe/commit those refs; if the first op then
rolls back, it would drop or overwrite the second op's valid ref. Holding **one**
lock across mutate→commit→rollback closes that window: no other operation can
observe or act on the intermediate state, and a rollback is invisible to others.

**Single-lock = no nesting (resolves the registry_lock limit).** `registry_lock.sh`
tracks exactly one active lock per process (`_registry_lock_dir`/`_registry_lock_token`
+ one EXIT trap). Because `add`/`rm` hold **only** `.attach.lock` for the whole
body — and `attachment_meta.py` is **lock-free** (Step 3, the caller owns the
lock) — there is never a second simultaneous acquire. No change to the shared
helper is needed.

**Standalone metadata commands.** Read-only subcommands (`refs`, `zero-refcount`,
`ls`) are lock-free (atomic writes ⇒ untorn reads). Any **mutation** invoked
outside an `add`/`rm` (the t1030_3 `gc`/fold/archive-decref surface) MUST take the
**same** `.attach.lock` — a per-blob lock would *not* exclude an in-flight
`add`/`rm` transaction (different lock dir → cross-race), so all metadata writers
serialize on the one global lock. (A finer-grained per-blob scheme is possible
later only if a provably non-overlapping partition is established; not in v1.)

A thin wrapper (e.g. `with_attach_lock` in `aitask_attach.sh`, or a small
`lib/attachment_lock.sh`) centralizes acquire→run→release so every entry point
uses the identical lock dir and timeout.

## Step 4 — `lib/attachment_cache.sh` (NEW)
- `attachment_resolve <hash>`: (1) cache hit (`attachment_cache_path`) → print
  path; (2) `attachment_backend_head`+`get` → populate `attachment_cache_path` →
  print; (3) miss both → **loud error** (design §5, never a silent placeholder).
- `local` backend: short-circuit by symlinking the cache entry to the
  `attachments/blobs/<2>/<62>` blob. (Cache is backend-agnostic; only the
  short-circuit knows the local blob path.)

## Step 5 — Frontmatter mutation (`attachments:` list-of-mappings)
- Add `append_yaml_mapping` / `remove_yaml_mapping`. Bash mutation of a block
  list-of-mappings is fiddly — a small Python frontmatter patcher (a sibling
  `lib/frontmatter_patch.py`, or extend `attachment_meta.py`) is acceptable and
  likely cleaner. **Record the choice** in Final Notes. Preserve the rest of the
  file untouched; bump `updated_at`. Round-trip the writer against t1030_1's
  `read_yaml_mappings` reader in tests (Step 7 matrix).

## Step 6 — Wire `aitask_attach.sh` verbs (replace the t1030_1 stubs)
- `add <task> <file> [--backend local] [--name <display>]` — **entire body inside
  one `with_attach_lock` (Step 3a)**: resolve task file → stat size → **enforce
  size cap (below)** → detect mime (`file --mime-type -b`) → `attachment_sha256` →
  **reject duplicate hash AND duplicate display name on this task (below)** →
  `attachment_backend_put` → populate cache → `attachment_meta.py incref <hash>
  <task> mime=… size=… backend=local` → `append_yaml_mapping` into `attachments:`
  → **single commit of the trio (Step 6a)** → release lock. Metadata mutation,
  frontmatter mutation, staging, commit, and rollback are all **within the same
  held lock** — no intermediate ref is ever visible to another operation.
- **Size cap.** Read `attachment_max_size_mb` from
  `aitasks/metadata/project_config.yaml` (the git-tracked shared project-config
  home — same file as `verify_build`/`test_command`; reuse the established
  scalar reader pattern). **Lookup order:** key present & positive integer → use
  it; absent/empty/unparseable/file-missing → **default 25**. Reject oversize
  with a `die` naming the actual size and the cap, suggesting a remote backend
  (t1030_3+) / `gh release upload` (design §10 Q3). *(Deviation note: design §10
  says "configurable in profile"; `ait attach` does not run inside an execution
  profile — `project_config.yaml` is the right shared home. Record in Final
  Notes.)*
- **Duplicate rejection — hash AND name, both per task (concern #2).** Scan the
  task's existing `attachments:` (via `read_yaml_mappings`) before writing and
  `die` on either:
  - **Duplicate hash** — the same `hash` already attached to this task. Allowing
    the same blob twice on one task (even under two names) would put **two
    frontmatter entries on one `(hash, task)`** while `refs` is a set of bare task
    IDs, so a later `rm` of one entry's `decref <hash> <task>` would drop the
    task's only ref even though the other entry still references the blob → GC
    would treat a **live** attachment as orphaned. Rejecting duplicate hashes
    keeps `(hash, task)` strictly **1:1**, which is exactly what a task-ID set in
    `refs` models. (`die`: "this file (sha256:…) is already attached to t<task> as
    '<existing-name>'".)
  - **Duplicate display name** — `name` (the `--name` value, else source
    basename) must be unique within the task, so `get`/`rm <name-or-hash>`
    resolves a name to exactly one entry (`die`: "attachment named '<name>'
    already exists on t<task> — pass --name to disambiguate").

  The same blob attached to *different* tasks is fully supported — that is the
  refcount case (`incref` set-adds the second task).
- `get <task> <name-or-hash> [--out]`: resolve name→hash from frontmatter (unique
  by the add guard) or accept a literal `sha256:…`/bare hash → `attachment_resolve`
  → **verify resolved bytes hash back to the expected hash** → copy to `--out`/
  stdout. Hash mismatch = loud failure (design §8).
- `rm <task> <name-or-hash>` — **entire body inside one `with_attach_lock`**:
  resolve to a single entry → `attachment_meta.py decref <hash> <task>` (blob
  **NOT** deleted — GC is t1030_3) → `remove_yaml_mapping` from frontmatter →
  commit the pair (task `.md` + `meta/<2>/<62>.json`) → release. Same single-lock
  transaction as `add`.
- Leave `move`/`gc` as stubs (t1030_3).

## Step 6a — Trio-commit transaction mechanics
`task_git()` runs `git -C "$_AIT_DATA_WORKTREE"` (`task_utils.sh:168`), so **every
staged path is relative to the data-worktree root** (`.aitask-data/`). The three
paths for `add`:
- blob: `attachments/blobs/<2>/<62>`
- meta: `attachments/meta/<2>/<62>.json`
- task: `aitasks/t1030/t1030_2_….md`

Staging + commit run **inside the single `.attach.lock` transaction** (Step 3a),
together with the metadata and frontmatter mutations — so two
different-task/different-hash ops never hit the Git index concurrently and no
intermediate state is observable. **Stage explicitly, never blanket**
(`./ait git add <those three>` — a blanket `add -A` would sweep concurrent
writers' edits on the shared data branch), then a **single**
`./ait git commit -m "ait: Attach <name> to t<task>"`.

**Ordering + rollback with preimages (concern #4 — `git checkout` alone is
insufficient because a brand-new meta/blob file is *untracked* and checkout
won't remove it). All of this is inside the held lock:**
1. **Record pre-existence up front** (before any mutation): `attachment_backend_head`
   for the blob, and `test -f` for `meta/<2>/<62>.json`; the task `.md` always
   pre-exists. This classifies each path as HEAD-restorable vs newly-created.
2. `attachment_backend_put` — idempotent atomic copy (temp + `mv`); a half-written
   blob never appears under its final name.
3. `attachment_meta.py incref` (meta RMW) → `append_yaml_mapping` (frontmatter).
4. Stage the explicit paths and commit **last**. **If the commit fails** (e.g.
   `assert_data_worktree_clean` rejects a dirty rebase), roll back deterministically
   by the pre-existence classification from step 1:
   - pre-existed in HEAD (always the task `.md`; the meta file iff the blob was
     already attached elsewhere) → `./ait git checkout -- <path>`;
   - newly created this op (the meta file on a first-ever attach; the blob) →
     `rm -f <path>` (and `git reset` any staged entry).
   Then `die` with the git error. Because the rollback is **inside the lock**, no
   other operation can ever observe the partial state; the worktree returns to its
   exact pre-op state.

## Step 7 — Tests
- `tests/test_attach_local_backend.sh`: backend round-trip `put→head→get→verify`,
  `delete`/`list`; add/get/rm e2e in a fixture data-branch repo
  (`setup_fake_aitask_repo`); **size-cap rejection** (oversize file +
  `project_config.yaml` override proving lookup, and the default-25 fallback);
  **exactly one commit per `add`** (count before/after); get verifies
  **identical bytes** + hash; rm decrefs without deleting the blob;
  **duplicate-hash `add` rejected** and **duplicate-name `add` rejected**
  (concern #2); same blob to a *second task* succeeds and refs has 2 entries;
  **staged-path scoping** — an unrelated dirty file in the data worktree is NOT
  swept into the attach commit; **rollback** — a forced commit failure on a
  first-ever attach leaves **no** untracked dirty meta/blob and the frontmatter
  unchanged (concern #4).
- `tests/test_attach_meta.sh` (renamed from the planned index test):
  incref/decref/refs/zero-refcount/rebind over the per-blob layout;
  **idempotency** — repeated `incref <h> <task>` keeps `refs` a size-1 set,
  repeated `decref` is a no-op; atomic write leaves no temp file; schema is
  blob-intrinsic + refs only (no `name`/`added_at`).
- **Concurrency proof (the user's explicit acceptance criterion):**
  - **Whole add/rm is one transaction** — a held `.attach.lock` makes a second
    `add`/`rm` `die` busy (proving the entire body, not just a phase, is
    serialized); after the holder finishes, the second proceeds and the final
    refs/frontmatter are consistent.
  - **No intermediate ref visibility** — drive a first `add` whose commit is
    forced to fail (rollback path) while a second same-hash `add` is queued on the
    lock; assert the second op (running *after* the lock is released) sees the
    rolled-back state, never the first op's uncommitted incref, and its own ref
    survives (the first op cannot drop/overwrite it). This is the exact failure
    the single-lock transaction prevents.
  - **Two *unrelated* attachments (different hashes)** still each rewrite only
    **their own** `meta/<a>/….json` / `meta/<b>/….json` (small, isolated diffs;
    the per-blob-file win), serialized by the one lock — assert both meta files
    are correct and no global ledger file exists.
  - **No lock leak** — assert no `.attach.lock` dir survives a completed or
    rolled-back op (EXIT-trap auto-release).
  - **Standalone metadata mutation excludes a transaction** — a held `.attach.lock`
    blocks a direct `attachment_meta.py`-via-`ait` mutation path (proving t1030_3's
    gc/rebind cannot race an `add`/`rm`).
- **Frontmatter-mutation matrix** — `append_yaml_mapping`/`remove_yaml_mapping`
  vs hostile inputs, asserting (a) round-trip through t1030_1 `read_yaml_mappings`,
  (b) unrelated frontmatter keys + markdown body **byte-preserved**, (c)
  `updated_at` bumped:
  - absent `attachments:` block → `add` creates a well-formed block;
  - empty list (`attachments: []`) → first append yields a valid block list;
  - multiple existing items → append/remove targets the right one, siblings intact;
  - values needing quoting — names with `:`, `#`, spaces, quotes, **unicode** →
    round-trip intact (writer quotes when needed so the reader's comment/quote
    rules reproduce the exact value);
  - newline-in-name → rejected loudly (out-of-scope per t1030_1 contract), never
    emit invalid YAML.

## Coordination / doc-sync (in-task)
Because this supersedes the written storage design, keep the spec + siblings in
sync **in this task**. **`aidocs/` is normal code-branch content; `aitasks/` lives
on the `.aitask-data` branch** — so the two edits go in **separate commits with
the right tool** (CLAUDE.md: never mix code and task-data in one commit, concern
#5):
- **`aidocs/task_attachments_design.md` §4** — replace the single-`index.json`
  storage-layout block + "index.json is the refcount ledger" prose with the
  per-blob `blobs/`+`meta/` model; note the aggregate index is now a
  generated-cache-only concept. Commit with **plain `git`** (alongside the
  implementation code commit, or its own `documentation:` commit).
- **t1030_3 task file** (`aitasks/t1030/t1030_3_archive_gc_fold_rebind.md`) —
  its "index.json schema is defined here" / decref-on-archive notes now consume
  **per-blob meta files** (`zero-refcount`/`rebind` scan `meta/**.json`; advisory
  scans re-checked under the **global `.attach.lock`** before any delete, and all
  metadata mutations run under that same lock). Update its
  Key-Files / Notes so the next picker inherits the right model. Commit with
  **`./ait git`** (it is task data).
- **t1076_1** — note (no edit required) that per-blob meta files are *closer* to
  the unified-artifact "manifest" model (`aidocs/unified_artifact_design.md` §5)
  than a global index was; the generalization stays a rename-and-widen.

## Risk

### Code-health risk: medium
- **Concurrent metadata / git mutation.** Racing `add`/`rm` could drop a ref →
  later GC deletes a live blob; or a ref made visible before its frontmatter
  commit could be clobbered by a rollback; or two ops could collide on the shared
  Git index · severity: medium · → mitigation: a **single global attach
  transaction lock** (`.attach.lock`, Step 3a) wraps the *entire* add/rm body
  (mutate→frontmatter→stage→commit→rollback) so no intermediate state is ever
  observable; `attachment_meta.py` is lock-free (caller owns the lock ⇒ no
  nesting, respects `registry_lock.sh`'s single-lock limit); set-based
  **idempotent** ops + fail-safe `die` on busy. Covered by the Step 7
  concurrency-proof (whole-transaction serialization, no intermediate-ref
  visibility, no lock leak) — in-task. *Per-blob files still shrink the blast
  radius: each op rewrites only its own small meta file, not a global hotspot.*
- **Duplicate-hash decref ambiguity.** Same blob twice on one task would make
  `decref` drop the sole task ref while a second entry still references it →
  live-as-dead GC · severity: medium · → mitigation: reject duplicate hash per
  task (Step 6) keeping `(hash, task)` 1:1; tested in Step 7 — in-task.
- **Commit-failure drift on first attach.** `git checkout` cannot remove an
  untracked new meta/blob on rollback · severity: medium · → mitigation:
  pre-existence-keyed rollback (checkout HEAD files, `rm` newly-created ones,
  Step 6a); rollback test in Step 7 — in-task.
- **Frontmatter mutation of live task files.** A buggy patcher could corrupt
  unrelated frontmatter/body or drop `updated_at` · severity: medium · →
  mitigation: Python frontmatter patcher, writer↔reader round-trip, byte-
  preservation asserted against the hostile-YAML matrix (Step 7) — in-task.
- **Trio-commit on the shared `.aitask-data` branch.** Non-atomic staging could
  let blob/meta/frontmatter drift or sweep others' edits · severity: medium · →
  mitigation: data-root-relative **explicit** staging, commit-last with
  HEAD-restore rollback (Step 6a), staged-path-scoping test (Step 7) — in-task.
- **Design deviation (index.json → per-blob meta).** Spec §4 and t1030_3 reference
  `index.json`; left unsynced they would mislead the next picker · severity:
  medium · → mitigation: the **Coordination / doc-sync** step updates design §4 +
  t1030_3 in this task — in-task.
- New surface (`attachment_backend.sh`, `attachment_backends/local.sh`,
  `attachment_cache.sh`, `attachment_meta.py`) is isolated and follows
  established patterns (dispatcher + extension marker, `gate_orchestrator.py`
  Python precedent, `registry_lock.sh` mutex) · severity: low · → mitigation: none.

### Goal-achievement risk: low
- **Generalizable seam correctness.** The `attachment_backend_*` contract must be
  shaped so t1076_1 renames→widens to `artifact_backend` without re-plumbing ·
  severity: low · → mitigation: contract names/shape pinned by design §5;
  dispatcher + cache kept `local`-agnostic; per-blob meta is *closer* to the
  artifact-manifest model — verified by review, no separate task.
- **`zero-refcount`/`rebind` whole-tree scan cost.** Scanning `meta/**.json` is
  O(attachments) per call · severity: low · → mitigation: explicitly accepted for
  v1 (user-directed); a generated aggregate index can be added later as a *cache*
  if needed, never as source of truth.
- Approach is design-backed and the dependency (t1030_1 reader + helpers) landed
  exactly as assumed; scope bounded (write-path only; GC/fold deferred to
  t1030_3) · severity: low · → mitigation: none.

**Planned mitigations:** None — every identified risk is mitigated **in-task**
(single global attach-transaction lock + idempotent lock-free ledger ops,
hostile-YAML test matrix, explicit staging + in-lock rollback, in-task doc-sync).
No before/after follow-up tasks warranted.

## Step 9 (Post-Implementation)
Standard per `task-workflow` Step 9. Final Notes MUST record, **explicitly**:
- **Per-attachment metadata files (`attachments/meta/<2>/<62>.json`) are the
  canonical lifecycle ledger**; any future aggregate index is a generated
  cache/reporting artifact only, **not** source of truth.
- the final per-blob schema (blob-intrinsic + refs; display fields authoritative
  in frontmatter);
- where frontmatter mutation lives (bash vs Python — the one open choice);
- the size-cap key + lookup (`attachment_max_size_mb` in `project_config.yaml`,
  default 25, + the design-§10 "profile" deviation rationale);
- the lock design (a **single global `.attach.lock`** wrapping the entire add/rm
  transaction; `attachment_meta.py` lock-free with the caller owning the lock;
  standalone metadata mutations take the same lock) and the duplicate-hash/name
  rejection that keeps `(hash, task)` 1:1;
- confirmation the `attachment_backend_*` contract + extension-point marker are
  `local`-agnostic (t1076_1 + S3/GDrive follow-ups depend on it);
- the doc-sync done to design §4 + t1030_3.

## Final Implementation Notes

- **Actual work done:** Implemented the full local storage core under
  `ait attach add/get/rm`:
  - `lib/attachment_backend.sh` (dispatcher seam, `# BACKEND-EXTENSION-POINT`
    markers) + `lib/attachment_backends/local.sh` (blobs at
    `attachments/blobs/<2>/<62>`; idempotent atomic `put`, `get`/`head`/`delete`/`list`).
  - `lib/attachment_meta.py` — the **lock-free** per-blob ledger primitive
    (`--meta-dir <dir>` + `incref|decref|refs|zero-refcount|rebind`); set-based
    idempotent mutations; atomic temp+`os.replace` writes.
  - `lib/attachment_cache.sh` — universal cache resolver (cache → backend
    head+get → loud miss); local backend short-circuits via an **absolute**
    symlink to the worktree blob.
  - `lib/frontmatter_patch.py` — surgical line-based `attachments:` block
    append/remove (no full-YAML round-trip → unrelated frontmatter/body
    byte-preserved); writer quotes exactly when the t1030_1 reader needs it.
  - `lib/attachment_lock.sh` — `with_attach_lock` global transaction mutex over
    `registry_lock.sh`.
  - `aitask_attach.sh` — `add`/`get`/`rm` wired; size cap; duplicate hash+name
    rejection; single-transaction commit + preimage rollback.
  - Tests: `test_attach_meta.sh` (33), `test_attach_local_backend.sh` (28);
    narrowed `test_attach_scaffold.sh` stub loop to `move`/`gc` (40→…; 41/41).
  - Doc-sync: `aidocs/task_attachments_design.md` §4/§5/§8/§10 and the t1030_3
    task file → per-blob model.
  All verification passed: meta 33/33, e2e 28/28, scaffold 41/41 (no regression),
  yaml_utils 28/28, shellcheck clean, `py_compile` OK, plus a manual e2e smoke
  (add/ls/get/rm/dup/rollback/lock-busy) in a scratch git repo.

- **Per-attachment metadata files are the canonical lifecycle ledger.** One JSON
  file per blob at `attachments/meta/<2>/<62>.json` — there is no global
  `index.json`. Any future aggregate index is a generated cache/reporting
  artifact only, NEVER source of truth. Schema is blob-intrinsic + refs only:
  `{hash, refs:[task_id…], mime, size, backend}` — per-task display fields
  (`name`, `added_at`) stay authoritative in the task frontmatter.

- **Where frontmatter mutation lives:** Python (`lib/frontmatter_patch.py`),
  chosen over bash (block list-of-mappings mutation is fiddly and error-prone in
  bash). It edits ONLY the target block line-range so unrelated frontmatter/body
  is byte-preserved; it bumps `updated_at` (overridable via `--now` for tests).

- **Size-cap key + lookup:** `attachment_max_size_mb` in
  `aitasks/metadata/project_config.yaml` (the shared, git-tracked project-config
  home — same file as `verify_build`/`test_command`), default **25** when
  absent/empty/unparseable. *Deviation note:* design §10 said "configurable in
  profile", but `ait attach` does not run inside an execution profile, so
  `project_config.yaml` is the correct home (design §10 Q3 updated to match).

- **Lock design:** a SINGLE global `attachments/.attach.lock` wraps the entire
  `add`/`rm` body (mutate meta → mutate frontmatter → stage → commit →
  rollback). `attachment_meta.py` is lock-free; the bash caller owns the lock, so
  at most one lock is ever held (respects `registry_lock.sh`'s single-active-lock
  limit — no nesting, no helper change). Standalone metadata MUTATIONS (t1030_3
  gc/fold) must take the same global lock; reads are lock-free (atomic writes ⇒
  untorn reads). `zero-refcount` is advisory — gc must re-check `refs` under the
  lock before deleting. Commit uses `git commit -- <explicit paths>` (partial
  commit) so a concurrent writer's staged index is never swept in. Rollback is
  pre-existence-keyed: HEAD-restore tracked files, `rm` newly-created ones.

- **Backend contract is `local`-agnostic:** the dispatcher (`_attachment_backend_call`)
  and the cache layer carry no local-only assumptions (the local symlink
  short-circuit is the only local-aware spot, gated on `ATTACHMENT_BACKEND==local`).
  The `# BACKEND-EXTENSION-POINT` markers + `attachment_backend_{put,get,head,delete,list}`
  names/shape are exactly what t1076_1 widens to `artifact_backend_*` and what
  the S3/GDrive follow-ups extend.

- **Key decisions / deviations:** (1) `git commit -- <paths>` partial-commit was
  added after a smoke test caught a bare `git commit` sweeping a pre-staged
  unrelated file into the attach commit (the shared-index hazard). (2) Reject
  duplicate HASH per task (not just name) so `(hash,task)` is strictly 1:1 and a
  task-ID set in `refs` is unambiguous for decref. (3) Frontmatter writer also
  quotes colon-space values (valid-YAML correctness) on top of the
  whitespace-`#` / leading-indicator cases the t1030_1 reader requires.

- **Upstream defects identified:** None that block. One observation (not a defect
  from this task): `aidocs/task_attachments_design.md` was **untracked in git on
  both branches** — authored during t1030 planning but never committed. This task
  commits it (it is the spec the code implements and the §4 doc-sync target). The
  unrelated `aidocs/slack/` directory remains untracked and was left untouched.

- **Notes for sibling tasks (t1030_3):** consume `lib/attachment_meta.py`
  (`--meta-dir attachments/meta`) for decref/zero-refcount/rebind, ALWAYS under
  `with_attach_lock` (lib/attachment_lock.sh). `zero-refcount` is advisory →
  re-check `refs` under the lock before `attachment_backend_delete`. Stage the
  touched per-blob meta files in the archival/fold commit. The t1030_3 task file
  has a design-update banner with the full contract. For t1076_1: per-blob meta
  files are already close to the per-artifact manifest shape.
