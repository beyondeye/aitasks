---
Task: t1076_1_storage_abstraction_generalization.md
Parent Task: aitasks/t1076_unified_artifact_implementation.md
Sibling Tasks: aitasks/t1076/t1076_2_artifact_pointer_version_model.md, aitasks/t1076/t1076_3_share_handle_resolution.md, aitasks/t1076/t1076_4_artifact_producing_gate_archetype.md
Base branch: main
plan_verified: []
---

# t1076_1 — Storage abstraction generalization (attachment → artifact substrate)

---
Task: t1076_1_storage_abstraction_generalization.md
Parent Task: aitasks/t1076_unified_artifact_implementation.md
Sibling Tasks: aitasks/t1076/t1076_2_artifact_pointer_version_model.md, aitasks/t1076/t1076_3_share_handle_resolution.md, aitasks/t1076/t1076_4_artifact_producing_gate_archetype.md
Archived Sibling Plans: (none yet — first child)
Worktree: (current branch, profile fast)
Branch: main
Base branch: main
---

## Context

First substrate piece of the unified artifact model (parent t1076, design spec
`aidocs/unified_artifact_design.md` §2 seam B, §4b, §5). t1030 shipped the
attachment storage: a 5-op backend seam (`attachment_backend.sh`, local-only),
pure hash/shard utils, a universal cache resolver, a global attach lock, and a
per-blob refcount ledger (`attachment_meta.{sh,py}`) — **no `index.json`**
(verified in t1030_4). This task promotes that seam to a shared
**`artifact_backend`** serving both attachments and artifacts, defines the
genuinely-new **artifact manifest** substrate (`art:<id> → {current, versions[],
backend}`), and generalizes the universal local cache — so t1076_2 (handle/
version model) and t1076_3 (share-handle resolution) can build on a settled
storage layer.

## Settled decisions (user-confirmed)

1. **On-disk blob store stays at `.aitask-data/attachments/{blobs,meta}`** — no
   data migration; the dir name is historical ("the shared blob store, named for
   its origin"). Manifests get a NEW `artifacts/manifests/` dir alongside.
2. **Manifest = committed per-artifact JSON files** at
   `<data-worktree>/artifacts/manifests/<id>.json` (design §4b shape 1, per-file
   granularity mirroring the per-blob meta ledger — avoids a write hotspot;
   travels with the data branch so any configured PC resolves the handle).
   Backend-resident manifests (shape 2) **explicitly deferred**; resolution
   already goes handle→manifest→backend, so the hybrid stays possible later.
3. **Full substrate rename**, no compat aliases (repo-internal seam):
   `artifact_utils.sh`, `artifact_backend.sh`, `artifact_backends/`,
   `artifact_cache.sh` + all functions + `ATTACHMENT_BACKEND`→`ARTIFACT_BACKEND`.
   `attachment_meta.{sh,py}`, `attachment_lock.sh`, `frontmatter_patch.py`, and
   the `ait attach` CLI keep their names (attachment-specific / shared infra).
4. Cache dir moves `~/.cache/ait/attachments/<hash>` → `~/.cache/ait/artifacts/<hash>`
   (pure perf layer; old entries go stale harmlessly — noted in docs).

## Blast radius (verified by grep, whole repo)

Fully contained in **13 files**: 6 scripts, 5 tests, 2 aidocs. Verified NOT
affected: `website/` (only generic `ait attach` semantics), `seed/` (only the
`attachments_gc_grace` knob — keeps its name), `.claude/` skills, `ait`
dispatcher, `aitask_fold_mark.sh` (sources only keeps-name libs),
`board/aitask_board.py` (CLI-level), `tests/test_attach_meta.sh`,
`test_attachment_meta_lib.sh`, `test_board_decref_doomed_attachments.py`.
Archived plans/tasks mention old names as historical record — do not edit.

## Implementation steps

### Step 1 — Rename the four substrate files (`git mv` + in-file symbol rename)

| Old | New |
|---|---|
| `lib/attachment_utils.sh` | `lib/artifact_utils.sh` |
| `lib/attachment_backend.sh` | `lib/artifact_backend.sh` |
| `lib/attachment_backends/` (+ `local.sh`) | `lib/artifact_backends/` |
| `lib/attachment_cache.sh` | `lib/artifact_cache.sh` |

Function/var renames: `attachment_sha256`→`artifact_sha256`,
`attachment_validate_hash`→`artifact_validate_hash`,
`attachment_shard_path`→`artifact_shard_path`,
`attachment_cache_path`→`artifact_cache_path`,
`attachment_backend_{put,get,head,delete,list}`→`artifact_backend_*`,
`_attachment_backend_call`→`_artifact_backend_call`,
`attachment_local_*`/`_attachment_local_root`→`artifact_local_*`/`_artifact_local_root`,
`attachment_resolve`→`artifact_resolve`, env `ATTACHMENT_BACKEND`→`ARTIFACT_BACKEND`,
`_AIT_ATTACHMENT_{UTILS,BACKEND,BACKEND_LOCAL,CACHE}_LOADED`→`_AIT_ARTIFACT_*`,
`_AIT_ATTACHMENT_BACKEND_DIR`→`_AIT_ARTIFACT_BACKEND_DIR`.

Critical **non**-renames inside renamed files:
- `artifact_local_blob_relpath` / `_artifact_local_root` keep emitting
  `attachments/blobs/...` / `<worktree>/attachments` (decision 1).
- `artifact_cache_path` emits `.../ait/artifacts/<hash>` (decision 4) with a
  comment noting old cache entries go stale harmlessly.
- Header comments in each renamed file gain one line: "generalized from
  attachment_* in t1076_1; serves both attachments and artifacts."
- Update `# shellcheck source=` directives to the new paths.

### Step 2 — Update consumers that keep their names

- `.aitask-scripts/lib/attachment_meta.sh`: lines 28–29 source
  `artifact_utils.sh` (+ shellcheck directive); `attachment_shard_path` calls
  (lines ~42, 47) → `artifact_shard_path`. Output paths (`attachments/meta/...`)
  unchanged. **Gotcha: this keeps-its-name file has hidden deps on renamed
  symbols — the one place a naive 4-file rename breaks `ait attach` and fold.**
- `.aitask-scripts/aitask_attach.sh`: source block (lines 31–36) → new lib names
  + shellcheck directives; all call sites; the three `export ATTACHMENT_BACKEND=`
  (lines 224, 316, 545) → `ARTIFACT_BACKEND` (easy to miss — they're writes, not
  reads); add `source "$SCRIPT_DIR/lib/artifact_manifest.sh"` (for Step 4);
  header STORAGE MODEL comment gains a line about the artifact substrate.
- `.aitask-scripts/lib/attachment_lock.sh`: code unchanged; header comment
  extended to state the lock now also guards **artifact-manifest mutations**
  (shared store + gc interplay).

### Step 3 — New manifest primitive (mirrors `attachment_meta.{py,sh}`)

**3a. `.aitask-scripts/lib/artifact_manifest.py`** (new, ~250 lines, stdlib-only,
`die()` to stderr, atomic temp+`os.replace` writes — reuse `attachment_meta.py`
`atomic_write` pattern verbatim). Lock-free primitive: callers own concurrency
(mutations run under `with_attach_lock`).

Handle validation (validation-not-transformation; no lossy sanitization):
```python
HANDLE_RE = re.compile(r"^art:[a-z0-9][a-z0-9._-]{0,127}$")  # lowercase-only:
# case-insensitive filesystems would collide art:Foo / art:foo
HASH_RE   = re.compile(r"^sha256:[0-9a-f]{64}$")
# manifest_path: die on HANDLE_RE mismatch; filename = handle[len("art:"):] + ".json"
# first char alnum forbids leading '.'; charset forbids '/', so no path traversal
```

Schema (invariants enforced on every load and before every write):
```json
{
  "handle":     "art:t774-htmlplan",
  "current":    "sha256:<64hex>",
  "versions":   ["sha256:<hexA>", "sha256:<hexB>"],
  "backend":    "local",
  "created_at": 1750000000,
  "updated_at": 1750000500
}
```
Invariants: `handle` matches regex AND filename; `versions` non-empty,
append-only, ordered oldest→newest, no duplicates, all match `HASH_RE`;
`current ∈ versions`; `backend` matches `BACKEND_RE =
^[a-z0-9][a-z0-9_-]{0,31}$` (conservative name-shape validation — registry
membership / configuration is t1076_3's; this just stops typos and junk from
persisting only to fail much later at resolution); timestamps integer epochs
(accept `now=<epoch>` kv for testability, like `attachment_meta.py decref`).

**Malformed-manifest policy (fail-closed, named):** any subcommand that reads a
manifest — including the tree-scanning `list` / `referenced-hashes` — `die`s on
invalid JSON or an invariant violation with an error that **names the offending
file path and the violated invariant** (e.g. `artifact_manifest.py: malformed
manifest artifacts/manifests/x.json: current not in versions — repair or remove
it`). No skip-and-continue: a collection scan with an unreadable member must not
silently produce a smaller set (consumed by gc as the blocking set — see Step 4).

Subcommands (`--manifest-dir <dir> <cmd> …`) — substrate only; t1076_2 owns
handle minting, frontmatter writes, and artifact-level ops built ON these:
- `create <handle> <hash> [backend=<n>] [now=<epoch>]` — die if exists; writes
  `{handle, current=hash, versions=[hash], backend, created_at=updated_at}`
- `get <handle>` — print full JSON; empty + exit 0 if absent
- `current <handle>` / `versions <handle>` — print hash / one-per-line oldest-first
- `set-current <handle> <hash> [now=]` — die if missing; append to `versions`
  iff not present, then move `current` (repoint-to-old moves without dup); bump
  `updated_at`
- `set-backend <handle> <backend> [now=]` — update backend, bump `updated_at`
- `list` — every handle, sorted (re-validated against file content)
- `referenced-hashes` — union of every hash in every manifest's **versions**
  (not just current — §9 version-awareness), sorted unique. GC's blocking input.

No `delete` — artifact removal/pruning semantics belong to t1076_2's lifecycle.

**3b. `.aitask-scripts/lib/artifact_manifest.sh`** (new, ~45 lines):
- `_AIT_ARTIFACT_MANIFEST_SH_LOADED` guard; sources `python_resolve.sh`;
  requires `task_utils.sh` caller-sourced (same pattern as `attachment_meta.sh`).
- `artifact_manifest_dir()` — `_ait_detect_data_worktree`;
  `printf '%s/artifacts/manifests' "$_AIT_DATA_WORKTREE"`
- `artifact_manifest()` — `"$(require_python)" .../artifact_manifest.py
  --manifest-dir "$(artifact_manifest_dir)" "$@"`. Header: MUTATING subcommands
  (create/set-current/set-backend) are lock-free here — caller MUST hold
  `with_attach_lock`.
- `artifact_manifest_relpath()` — validate handle via bash regex (die otherwise);
  `printf 'artifacts/manifests/%s.json' "${1#art:}"` (for `task_git` staging).

Locking soundness (verified): `cmd_gc` wraps the entire sweep in
`with_attach_lock` and re-confirms refs under the held lock; manifest mutations
taking the SAME lock means gc's `referenced-hashes` snapshot cannot race a
concurrent `set-current`, and a manifest `create` never interleaves inside an
add/rm transaction. `registry_lock.sh` allows one active lock per process and no
t1076_1 path nests a manifest mutation inside another attach transaction.

### Step 4 — GC reconciliation (the deliberate design piece)

Verified current behavior (`aitask_attach.sh`): `_attach_gc_txn` (517–563)
deletes a blob when (a) ledger refs empty under lock (531–532), (b) not in
`_attach_gc_blocking_hashes` (534–536, frontmatter scan of active+archived
non-Folded tasks at 497–509), (c) grace expired (539–541).

- **Safe already:** artifact-only blobs have no meta file → never appear in
  `zero-refcount` (iterates meta files only) → invisible to gc.
- **The hole:** a blob BOTH attached to a task AND referenced by a manifest:
  `ait attach rm` orphans it; after grace, gc deletes blob+meta while the
  manifest still points at it → dangling version.

**Fix:** extend `_attach_gc_blocking_hashes` (line 497) — after the task-file
loop, append `artifact_manifest referenced-hashes` so the blocking set is
"frontmatter refs ∪ manifest version refs". Lands at the exact choke point line
534 already greps; one blocking set, no second mechanism; version-aware per §9.
Comment notes: a manifest-blocked orphan keeps its zero-ref meta file
indefinitely — the block lifts when t1076_2's pruning removes the reference
(intentional, not a leak).

**Malformed-manifest interaction (deliberate fail-closed):** if any manifest is
malformed, `referenced-hashes` dies (Step 3 policy) → `blocking="$(...)"` fails
under `set -e` → **gc aborts before sweeping anything**, including unrelated
legacy attachments. This is the intended policy — never sweep with an
unreadable blocking set (sweeping could delete a still-referenced blob). The
user-visible error names the bad manifest file and says to repair/remove it, so
the failure is actionable, not a generic GC error. Tested in 6b.

### Step 5 — Mechanical test renames

`test_attach_scaffold.sh` (incl. line 205 syntax-check list → `artifact_utils.sh`
and lines 62–68 cache-path assertions → `/ait/artifacts/`),
`test_attach_local_backend.sh`, `test_attach_archive_gc.sh`,
`test_attach_fold_rebind.sh`, `test_attach_task_delete_decref.sh`.
No changes: `test_attach_meta.sh`, `test_attachment_meta_lib.sh`,
`test_board_decref_doomed_attachments.py`.

### Step 6 — New tests (follow `test_attach_local_backend.sh` scaffold pattern)

**6a. `tests/test_artifact_manifest_lib.sh`:**
- CRUD: create→get/current/versions/backend; create-on-existing dies; reads on
  missing handle print empty.
- Invariants: invalid handles die (`art:../x`, `Art:foo`, `art:Foo`, missing
  prefix, empty, >128 chars); invalid hash dies; set-current new hash
  appends+moves; set-current back to old version moves current WITHOUT
  duplicating; set-current on missing manifest dies.
- set-backend, list, referenced-hashes (union across ≥2 manifests, all
  versions, deduped on shared hash).
- **Backend name-shape validation:** `create ... backend=s3 compat!` /
  `set-backend <handle> "Bad Name"` die with a clear error; valid shapes
  (`local`, `s3-compat`, `gh_release`) accepted.
- **Malformed-manifest fail-closed:** hand-write an invalid manifest (bad JSON;
  separately, `current ∉ versions`); assert `list` and `referenced-hashes` die
  with an error **naming the offending file** and the violated invariant.
- Atomicity: no temp files left in `artifacts/manifests/`; file naming exactly
  `artifacts/manifests/<id>.json`; `artifact_manifest_relpath` shape.
- **AC assertion — manifest write touches no task file:** create+commit
  `aitasks/t5_demo.md`, capture bytes; run create + set-current + set-backend;
  assert task file byte-identical AND `git status --porcelain -- aitasks/` empty.
- **AC assertion — manifest travels through the data branch:** stage via
  `task_git add "$(artifact_manifest_relpath art:t5-demo)"` + commit; assert
  `git show HEAD:artifacts/manifests/t5-demo.json` parses and matches; then
  `git clone` the fixture repo to a second dir and assert `artifact_manifest
  get art:t5-demo` there returns the same record (proves any configured PC
  resolves the handle from the committed manifest, not just local state).

**6b. `tests/test_attach_gc_manifest_blocking.sh`** (modeled on
`test_attach_archive_gc.sh`, `attachments_gc_grace: 0` fixture):
- Guarded blob survives: attach A to t5; `artifact_manifest create art:t5-demo
  <hashA>`; `ait attach rm`; `ait attach gc`; blob + meta still exist.
- **Negative control (guard is load-bearing):** blob B identically
  attached-then-rm'd but in NO manifest IS swept in the same gc run.
- Version-awareness: manifest versions [C, D], current=D; orphaned old-version
  blob C survives gc.
- Artifact-only blob (put, no meta file) invisible to gc.
- **Malformed-manifest gc fail-closed:** with one hand-corrupted manifest
  present plus an otherwise-sweepable orphan blob, `ait attach gc` fails, the
  error names the bad manifest file, and **no blobs were swept** (fail-closed —
  never sweep with an unreadable blocking set).

**6c. Resolver integrity tests** (extend `test_attach_local_backend.sh` or a
small dedicated section):
- **Corrupted cache copy self-heals:** simulate the remote-fill case — place a
  wrong-bytes regular file at `~/.cache/ait/artifacts/<hash>` (fixture
  `XDG_CACHE_HOME`), resolve with a backend that has the correct blob; assert
  the resolver replaced the bad entry, returned the right bytes, and the
  re-resolved content hash-verifies.
- **Corrupted canonical blob dies:** overwrite the local-backend blob in
  `attachments/blobs/<2>/<62>` with wrong bytes, clear cache, resolve; assert
  loud `die` naming the blob (no silent wrong-bytes success — negative control
  for the verification being load-bearing).
- **Unknown backend name fails clearly:** `ARTIFACT_BACKEND=nosuch
  artifact_resolve <hash>` dies via the dispatcher's unknown-backend error.

### Step 7 — Docs

- `aidocs/unified_artifact_design.md` §4b: replace the "Open design point"
  block with the settled decision (committed per-artifact manifests, shape 1;
  shape 2 deferred; constraint held). Correct §4b's "generalizes t1030's
  `index.json`" phrasing (t1030 shipped per-blob meta, no index.json). Update §5
  names to `artifact_backend_*` / `~/.cache/ait/artifacts/`.
- `aidocs/task_attachments_design.md`: short pointer notes at §5 (renamed seam,
  `$ARTIFACT_BACKEND`), Universal-local-cache section (new cache path; old
  entries stale harmlessly), line 266 (`artifact_backend_delete`), line 299
  (`artifact_resolve`).
- No website/seed/.claude doc changes (verified none reference internals).

### Step 8 — Cache wrapper: in-resolver hash verification + t1076_3 boundary

`artifact_cache.sh::artifact_resolve` keeps the t1030 resolution order (cache
hit → local symlink-to-absolute-blob → backend head+get → loud die) but gains
**in-resolver content verification** — the resolver is becoming shared substrate
and future artifact consumers will call it directly, so integrity cannot depend
on each caller re-hashing (today only `cmd_get` does, at aitask_attach.sh:319-320):

- **Every successful resolution verifies the resolved bytes**:
  `artifact_sha256 <resolved-path>` must equal the requested hash before the
  path is printed.
- **Mismatch on a cached regular file** (a stale/corrupted cache copy — the
  remote-backend fill case): remove the bad cache entry, re-fetch from the
  backend **once**, re-verify; die if still wrong. Self-healing cache, single
  retry, no loop.
- **Mismatch on the local-backend blob** (symlink target — the canonical copy):
  `die` loudly naming the blob path — canonical corruption is never
  auto-repaired.
- `cmd_get`'s existing re-hash stays (cheap belt-and-suspenders at the CLI
  surface).
- Perf note: attachments are capped (`attachment_max_size_mb`, default 25), so
  per-resolve hashing is bounded; correctness of a content-addressed substrate
  wins over saving one hash pass.

**No put-side write-back helper in t1076_1**: put-side mechanics already exist
(`artifact_backend_put` then `artifact_resolve` warms the cache — exactly what
`_attach_add_txn` does). t1076_3 owns the *policy*: config-driven backend
selection, resolution across configured backends, put→remote write-back
orchestration. t1076_1 ships mechanics; t1076_3 composes them.

## Conventions

- `#!/usr/bin/env bash`, `set -euo pipefail` where applicable, `_AIT_*_LOADED`
  guards, `die`/`warn` (per `aidocs/framework/shell_conventions.md`).
- None of these libs are on `./ait`'s source-on-startup chain → no
  `test_scaffold.sh` registration. No new `ait` verb / dispatcher entry / skill
  helper → no allowlist edits (per `aidocs/framework/aitasks_extension_points.md`).
- `git mv` for the four renames so history follows.
- Run `shellcheck` on touched `.aitask-scripts/aitask_*.sh`.

## Verification (maps to the task's ACs)

1. **Backend round-trip** (put→head→get→byte-compare→hash-verify→list→delete→
   head-miss on local): `bash tests/test_attach_local_backend.sh`.
2. **Cache hit/miss paths per §5**: same test section B + scaffold cache-path
   tests against `~/.cache/ait/artifacts/` + resolver-integrity tests 6c
   (self-healing cache, corrupted-canonical die, unknown backend).
3. **Manifest read/write touches no task file** AND **manifest travels via the
   data branch** (task_git staging + committed readback + second-clone resolve):
   dedicated assertions in `test_artifact_manifest_lib.sh`.
4. **GC guard**: `test_attach_gc_manifest_blocking.sh` positive + negative
   control + malformed-manifest fail-closed (error names the bad file).
5. **No regression**: full attach suite (7 bash tests + board python test).
6. **Rename completeness**: repo grep for all old symbols returns zero hits
   (excluding keeps-name files' own content + historical docs); `bash -n` every
   touched script.

## Step 9 reference

Post-implementation: merge/cleanup per task-workflow Step 9 (current-branch
profile — no worktree), archive via `./.aitask-scripts/aitask_archive.sh 1076_1`,
push via `./ait git push`.

## Risk

### Code-health risk: medium
- A missed rename call-site breaks `ait attach`/fold at runtime (bash resolves
  function names at call time, not parse time) · severity: medium · → mitigation:
  in-plan (zero-hit grep sweep + `bash -n` + full attach test suite)
- `attachment_meta.sh` is a keeps-its-name file with hidden deps on renamed
  symbols (sources `artifact_utils.sh`, calls `artifact_shard_path`) · severity:
  medium · → mitigation: in-plan (explicit Step 2 edit + `test_attach_meta.sh` +
  fold tests)
- Omitting the GC manifest-guard would let gc delete blobs still referenced by
  manifest versions · severity: medium · → mitigation: in-plan (Step 4 guard +
  negative-control test 6b)
- A stale/corrupted cache entry could satisfy a `sha256:` handle with wrong
  bytes once consumers call the shared resolver directly · severity: medium ·
  → mitigation: in-plan (Step 8 in-resolver verification + self-heal/die tests 6c)
- A malformed manifest could abort gc for all attachments with a generic error ·
  severity: low · → mitigation: in-plan (deliberate fail-closed policy; error
  names the offending manifest; tested in 6b)

### Goal-achievement risk: low
- Manifest substrate API might need adjustment when t1076_2 builds artifact-level
  ops on it · severity: low · → mitigation: in-plan (subcommand set mirrors the
  proven `attachment_meta` pattern; design doc §3/§4b pins the semantics t1076_2
  consumes)

## Post-Review Changes

### Change Request 1 (2026-07-05 17:55)
- **Requested by user:** Malformed hashes reach path derivation in `artifact_resolve` before validation — `artifact_resolve "../bad/hash"` created `$XDG_CACHE_HOME/ait/bad` via `mkdir -p` and emitted a misleading "blob not found" error. Validate at resolver entry, and ideally in the path helper before command-substitution use.
- **Changes made:** (1) `artifact_resolve` now validates the hash as its FIRST action (`artifact_validate_hash || die`) — verified worse-than-reported: on the cache-hit path a traversal value resolving to an existing regular file would have been `rm -f`'d by the self-heal. (2) `artifact_cache_path` now dies on a malformed hash before deriving the path (same rule as `artifact_shard_path`); a validated hash contains no `/`, so traversal is impossible by construction. (3) Five regression assertions in `test_attach_local_backend.sh` §K: resolver dies with the validation error (not "blob not found"), no traversal dir is created, and `artifact_cache_path` dies in a subshell check.
- **Files affected:** `.aitask-scripts/lib/artifact_cache.sh`, `.aitask-scripts/lib/artifact_utils.sh`, `tests/test_attach_local_backend.sh`

## Final Implementation Notes
- **Actual work done:** Exactly per plan: (1) full substrate rename via `git mv` — `lib/artifact_{utils,backend,cache}.sh`, `lib/artifact_backends/local.sh`, all functions/guards, `ATTACHMENT_BACKEND`→`ARTIFACT_BACKEND`, cache dir → `~/.cache/ait/artifacts/`; on-disk `attachments/{blobs,meta}` unchanged (no data migration). (2) New manifest primitive `lib/artifact_manifest.py` (~300 lines; create/get/current/versions/set-current/set-backend/list/referenced-hashes; HANDLE_RE/HASH_RE/BACKEND_RE invariants; fail-closed malformed policy naming file + invariant) + `lib/artifact_manifest.sh` bash front. (3) GC blocking set unions `artifact_manifest referenced-hashes` (version-aware). (4) In-resolver hash verification in `artifact_resolve` (self-healing cache copy, die-on-canonical-corruption). (5) 5 tests mechanically renamed + `test_artifact_manifest_lib.sh` (46 asserts) + `test_attach_gc_manifest_blocking.sh` (18 asserts) + resolver-integrity §K (13 asserts incl. CR1 regressions). (6) Docs: §4b settled decision recorded in `unified_artifact_design.md`; pointer notes in `task_attachments_design.md`.
- **Deviations from plan:** One addition beyond plan: an explicit `|| die` guard on the gc blocking-set capture. Discovered during implementation that `_attach_gc_txn` runs with errexit suppressed (`with_attach_lock` invokes it via `"$@" || rc=$?`), so the planned "referenced-hashes dies → gc aborts under set -e" chain did NOT hold — a malformed manifest would have left a PARTIAL blocking set and the sweep would have continued. The guard makes fail-closed real; tested in `test_attach_gc_manifest_blocking.sh` §D.
- **Issues encountered:** (1) The errexit-suppression hazard above (the `shell_conventions.md` "silent set -e abort" family, in reverse). (2) `artifact_manifest_relpath` is a bash function whose `die` exits the caller shell — its negative test needed a subshell (same pattern as the scaffold's shard_path check). (3) CR1 (post-review): malformed hashes reached path derivation in `artifact_resolve` before validation — traversal `mkdir` side effect, and the self-heal `rm -f` was reachable with a traversal path; fixed by validating at resolver entry AND in `artifact_cache_path` (see Post-Review Changes).
- **Key decisions:** Committed per-artifact manifests at `artifacts/manifests/<id>.json` (§4b shape 1; backend-resident deferred — recorded in the design doc); lowercase-only HANDLE_RE (case-insensitive filesystem collision); `BACKEND_RE` shape-validation only (registry membership is t1076_3's); no `delete` subcommand (version pruning is t1076_2 lifecycle); manifest mutations share the global attach lock; no put-side write-back wrapper (t1076_3 owns the policy; `artifact_backend_put` + `artifact_resolve` are the mechanics).
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1076_2 builds artifact-level ops ON `artifact_manifest` (bash front auto-resolves the manifest dir; mutations must run under `with_attach_lock`; `set-current` handles both new-version append and repoint-to-old). `artifact_manifest_relpath <handle>` gives the `task_git add` staging path. The resolver verifies content itself — t1076_2/3 consumers need no caller-side re-hash. GC blocks on ALL manifest versions; a manifest-blocked orphan keeps its zero-ref meta file until version pruning (t1076_2) removes the reference. t1076_3's config-driven backend resolution plugs in at `ARTIFACT_BACKEND` + the `BACKEND-EXTENSION-POINT` markers in `artifact_backend.sh`.
