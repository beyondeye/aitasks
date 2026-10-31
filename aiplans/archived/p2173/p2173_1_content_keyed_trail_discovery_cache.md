---
Task: t2173_1_content_keyed_trail_discovery_cache.md
Parent Task: aitasks/t2173_trail_select_two_pane_dialog_and_discovery_cache.md
Sibling Tasks: aitasks/t2173/t2173_2_*.md
Archived Sibling Plans: aiplans/archived/p2173/p2173_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-31 21:57
---

# t2173_1 — Content-keyed discovery cache

Child of t2173 (parent plan: `aiplans/p2173_trail_select_two_pane_dialog_and_discovery_cache.md`,
approved 2026-10-31 after a review round). The parent's Context section explains the
measured costs (~3.3s per scan, 13 trails) and why the dialog is hard to scan.

### Verification notes (2026-10-31, verify pass before implementation)

Re-checked against `main` @ 8655e7334. Every assumption still holds:
- `archive_iter.py` (352 lines): `iter_all_archived_markdown`, `iter_numbered_archives`,
  `iter_archived_frontmatter`, `_iter_single_archive` (zstd drain + exit check only
  when `errors is not None`), `_note` dedupe — exactly as described below.
- `trail_discovery.py`: `_iter_active_task_frontmatter(unreadable, scan_errors)`,
  `_iter_trail_frontmatter_records`, `load_trail_blob` (tempfile + `artifact get
  --out`), `sequenced_trail_read`, serial `discover_trails` — unchanged.
- `artifact_manifest.py`: `validate`/`load` die via `bad()`; `manifest_path` dies on a
  bad handle; `HANDLE_RE` is imported by `trails_app.py` and `agent_launch_utils.py`
  (must stay). `cmd_get` in `aitask_artifact.sh` goes manifest get → current →
  `artifact_resolve` (hash-verified) → `cp` to `--out`.
- `trail_schema.load_trail(source)` already accepts `bytes`.
- `_ait_detect_data_worktree` rung 1 / legacy behaviour as stated; `_AIT_DATA_WORKTREE`
  is reset to `""` at source time (no env override to mirror).
- `board_trail_screen.py:990` `action_trail_select` still `rescan=not tabbed or not
  self._trail_infos`; `_open_trail_select` :1341.
- `setup_scratchpad_gitignore` :3101, call :5405; `tests/test_setup_git.sh` HELPERS
  block :834–842 with "all seven" prose at :846. `.gitignore` has no `.aitask-cache/`.
- Test updates needed under always-rescan (`tests/test_trails_app.py`): :1365
  (`"s re-scanned"` → now expects 2) and :1739–1743 ("reopen from the cache: still
  rev2" → `s` now scans; assert newest-wins keeps rev2 because the stub's infos carry
  `read_seq=0`). `test_an_empty_scan_is_not_a_dead_end` (:1620) stays valid.
- Plan review (2026-10-31) raised two blocking concerns, both confirmed and folded
  in below: identities were refreshed from disk rather than bound to the loaded
  code (and `trail_schema.load_schema()` re-reads the schema file on every
  `load_trail` call, so the schema had to be frozen as well); and
  `ThreadPoolExecutor(max_workers=min(4, n))` raises `ValueError` for `n == 0`.

### Design decisions

- **New module `.aitask-scripts/lib/trail_discovery_cache.py`** (pure, no
  Textual). Two independent layers, two files, so each loads/saves on its own
  and the existing test stub of `_iter_trail_frontmatter_records(unreadable,
  scan_errors=None)` (tests/test_trail_discovery_sequencing.py:179) keeps its
  signature:
  - `owners.json` — owner-record layer, used inside
    `trail_discovery._iter_trail_frontmatter_records`.
  - `docs.json` — document layer, used inside `discover_trails`.
- **Location**: `${AIT_TRAIL_CACHE_DIR:-.aitask-cache/trail_discovery}`
  (cwd-relative; cwd is the project root per the module's invocation contract).
  `AIT_TRAIL_CACHE=0` disables both layers (no reads, no writes). New gitignored
  dir `.aitask-cache/`.
- **File format** (JSON, `format: 1`, plus a layer `identity`):
  - owners: `{"format":1,"identity":"<hex>","entries":{"<key>":{"sha":"<hex>","records":[[handle, owner_id, archived, folded, name], …]}}}`.
    Key = `active:<path rel. to tasks dir>` / `archived:<path rel. to archived dir>`
    — the path is in the key because `owner_id` comes from the filename;
    `sha` is sha256 of the file's (or bundle's) bytes. Entries not seen in this
    scan are pruned on save (a vanished file drops out). Lookup returns **fresh**
    `TrailInfo` objects every time (discovery mutates them).
  - docs: `{"format":1,"identity":"<hex>","entries":{"<handle>":{"blob":"sha256:<hex>","doc":{…}}}}`
    — one entry per handle (latest), so the file stays bounded.
- **Identities** (mismatch ⇒ the whole layer is discarded):
  - owner layer: sha256 over the source bytes of `trail_discovery.py`,
    `archive_iter.py`, `task_yaml.py`, `topic_semantics.py` + a
    `OWNER_LAYER_VERSION` constant. (PyYAML's version is deliberately not part
    of it: the board can run on PyPy and `ait trails` on CPython with different
    PyYAML builds, and including it would make the two hosts thrash the cache.)
  - doc layer: sha256 of `lib/implementation_trail.schema.json` + the source of
    `trail_schema.py` + new constant `trail_schema.VALIDATOR_REVISION = 1`
    (comment: bump when validation semantics change without a change to this
    file).
- **Identities are bound to the loaded producer generation, frozen at import
  (review concern 1).** Hashing producer sources from disk on each `open()`
  would let a board / `ait trails` left running across an upgrade compute the
  *new* identity while its *old* imported parser/validator produces the
  results — a freshly launched process would then accept those entries
  without reparsing. So:
  - `trail_discovery_cache` computes `OWNER_IDENTITY` and `DOC_IDENTITY`
    **eagerly at module import** (module-level constants, never recomputed;
    `owner_identity()` / `doc_identity()` just return them). It is imported
    by `trail_discovery` right after `archive_iter` / `task_yaml` /
    `topic_semantics` / `trail_schema`, so the hash is taken in the same
    import chain that loaded the code. Each source path comes from the loaded
    module's own `__file__` (`sys.modules[...]`), not from a reconstructed
    path, so it names exactly the file that was imported.
  - **The schema is frozen too.** `trail_schema.load_schema()` re-reads
    `implementation_trail.schema.json` on every `load_trail` call, so an old
    process would otherwise validate with the *new* schema and its *old*
    code. At import the cache module reads the schema bytes once, hashes them
    into `DOC_IDENTITY`, and parses them with a new
    `trail_schema.parse_schema(raw, origin)` (the sanity checks factored out
    of `load_schema`, which now calls it). `load_trail_blob` validates with
    that frozen schema via a new keyword `load_trail(source, ..., schema=None)`
    (`None` ⇒ today's `load_schema(schema_path)`; every other caller is
    unchanged). The identity therefore describes exactly what discovery
    validates with.
  - Consequence: an old process can only write entries under its *own*
    import-time identity, which a new process (different sources/schema) sees
    as a mismatch and discards — it cannot populate entries the new
    implementation accepts. Residual boundary, stated in the docstring: an
    upgrade landing *during* the import chain itself (milliseconds) is not
    covered; PyYAML is deliberately excluded (see above).
  - Owner-layer producers (`task_yaml`, `topic_semantics`, `archive_iter`,
    `trail_discovery`) read no data files (checked), so freezing their source
    hash covers their whole behaviour.
- **Torn/corrupt cache is a miss, never an error**: any exception loading a file
  (bad JSON, wrong types, wrong format/identity) → empty layer; each entry is
  type-checked at lookup (malformed entry → miss). Saves are atomic
  (`lib/atomic_write.py` `atomic_write_text` after `mkdir -p`), only when the
  layer changed, and an `OSError` on save is swallowed (cache is optional;
  board and `ait trails` may both write — last writer wins, both are valid).
- **Only clean units are cached — and "clean" is decided from unit-local
  diagnostics that are collected on EVERY scan, whatever the caller passed.**
  The board calls `discover_trails()` with no `scan_errors`, and in that mode
  `archive_iter._note` drops every failure; deciding eligibility from the
  caller's lists would let a best-effort scan cache an empty/partial result for
  a corrupt bundle or an unparseable archived member, and a later diagnostic
  scan (`discover_trails(scan_errors=[])`, e.g. `trail_links.build_export`)
  would then hit that entry and never report the failure. So each unit is read
  with a **private** `unit_errors: list` passed to every `archive_iter` call
  (`iter_archive_file`, `parse_archived_frontmatter`, the loose-file read) and a
  private `unit_unreadable: bool` for active files. Eligibility to store =
  `not unit_errors and not unit_unreadable`. Only afterwards are they forwarded:
  `unit_errors` entries into the caller's `scan_errors` (deduped exactly as
  `_note` does) **only if** `scan_errors is not None`; the unreadable name into
  the caller's `unreadable` **only if** it is a list (and the name is
  task-named, as today). Consequence, stated in the docstring: with a private
  list `_iter_single_archive` always drains and checks the `zstd` exit status,
  so best-effort scans detect a truncated bundle too (they still report it to
  nobody — they just refuse to cache it). Directory listing still runs every
  scan through `checked_glob` with the caller's `scan_errors`, uncached, so a
  listing failure is reported by a diagnostic scan exactly as today.
- **No TOCTOU between hash and parse**: active/loose files are read once as
  bytes, hashed, then decoded with `io.TextIOWrapper(BytesIO(data),
  encoding="utf-8", errors="replace").read()` — the exact semantics of the
  current `Path.read_text(errors="replace")` (universal newlines). A bundle is
  opened once; the hash is taken from that fd, then the same fd (seek 0) feeds
  `zstd -dc` stdin / `tarfile` — a rename-replacement cannot slip in between.
- **Doc layer keyed by the fetched bytes' content address, read through the
  manifest.** `load_trail_blob` keeps its signature and 3-tuple unpacking but
  returns a `_BlobLoad(tuple)` subclass carrying `.blob_hash`
  (`"sha256:" + sha256(bytes written by artifact get)`; `artifact_resolve`
  already verifies blobs by exactly this hash, `lib/artifact_cache.sh:36`).
  Storing uses that attribute, so a stubbed loader returning a plain tuple
  (every existing test stub) is never cached. Lookup reads the manifest's
  `current`; hit iff `entry.blob == current` and the layer identity matches.
- **Manifest location without reimplementing the data-worktree ladder**:
  `proven_manifest_dir()` returns a directory only for the two layouts Python
  can prove cheaply, mirroring `_ait_detect_data_worktree`
  (`lib/task_utils.sh:77`): rung 1 (`.aitask-data/.git` is a dir or file in cwd
  → `.aitask-data/artifacts/manifests`), and a primary legacy checkout (`.git`
  is a directory in cwd, no `.aitask-data` → `artifacts/manifests`; for a
  primary its own toplevel is the main worktree, so rungs 2–3 also fail and
  rung 4 answers `.`). Every other layout (unlinked linked worktree,
  `--separate-git-dir`, no repo) → `None` → doc layer off (correct, just
  uncached).
- **Full manifest validation, through a non-exiting interface.** `get` accepts
  a manifest only after `artifact_manifest get` → `load` → `validate` (every
  invariant: required fields, handle shape + filename match, non-empty
  duplicate-free `versions` of valid hashes, `current ∈ versions`, backend
  shape, integer timestamps). A hand-rolled subset would let a warmed cache
  serve a document for a manifest `get` rejects (e.g. `backend: "bad/name"`
  passes a handle/current/versions check and fails `validate`). So
  `lib/artifact_manifest.py` is refactored, CLI behaviour and messages
  unchanged: `class ManifestError(ValueError)`; `manifest_violation(rec, path)
  -> str | None` holds today's checks verbatim (each `bad(reason)` becomes
  `return "malformed manifest %s: %s -- repair or remove it" % (path, reason)`);
  `read_manifest(path)` → `None` when absent, the record when valid, raises
  `ManifestError` (same message text) on invalid JSON, `OSError` or a violation;
  `validate()` / `load()` become thin wrappers that `die()` on that error. The
  cache's `manifest_current(handle)` = `HANDLE_RE` check → `manifest_path` →
  `read_manifest` → `rec["current"]`; `None` / `ManifestError` → miss, and the
  real `artifact get` then fails closed and reports.
- **Stated boundary of the doc layer** (in the module docstring): a hit
  re-proves the manifest exactly as `get` does, but not blob *availability*
  (backend activation, `artifact_resolve`'s store/cache lookup). That is
  deliberate: the entry is keyed by the content address of bytes `get` already
  hash-verified, so the document served is exactly the one `get` would return
  whenever it can resolve the blob; making a hit depend on the store being
  reachable would mean re-implementing `artifact_resolve` in Python.
- **Contracts kept**: `discover_trails()` → `(infos, unreadable)`; `TASK_DIR`
  per call; only `artifact get` / `artifact versions` are spawned (hits spawn
  nothing); **`read_seq`**: the doc-layer lookup runs inside the loader passed
  to `sequenced_trail_read`, i.e. inside the per-handle lock, manifest read
  first, and `read_seq` is still drawn after it — a hit is a read like any other,
  so `_reconcile_discovered_trails` keeps newest-wins. Failures (`load_error`)
  are never cached (keep the versions fallback and a real `get` each time).
- **Cold-path parallelism**: blob loads run through a
  `ThreadPoolExecutor(max_workers=min(4, n))` over `sequenced_trail_read`
  (distinct handles never share a lock); results assigned back in info order.
  **Only when `n >= 2`** (review concern 2): `ThreadPoolExecutor(max_workers=0)`
  raises `ValueError`, and `n == 0` is reachable (fresh project, last owner
  removed, every owner unreadable). `n == 0` skips the load loop entirely and
  `n == 1` loads inline; both still return `(infos, unreadable)` with
  `unreadable` and `scan_errors` filled exactly as today (they are produced by
  the owner scan, before the load step), and the doc cache is still saved —
  like the owner layer, `DocCache.save()` drops entries for handles this scan
  did not discover, so with `n == 0` it simply empties the layer.
- **Hosts revalidate on every open.** `TrailScreenMixin.action_trail_select`
  (`board/board_trail_screen.py:990`) always calls
  `_open_trail_select(rescan=True)` — the tabbed host no longer serves its
  in-memory list on `s` (that was the stale-list problem). `TrailsApp` keeps
  `_trail_infos` as the last scan (needed by `_open_trail_by_handle`,
  reconciliation, `_activate_trail`), it is just no longer what `s` shows.
  The `LoadingOverlay("Scanning for trails…")` stays on every scan: it is what
  holds input while the scan runs (the gen guard and `_modal_is_active()` rely
  on it); a warm scan only flashes it. A delayed overlay would reopen the
  key-during-scan window — not worth it.

### Pre-phase (risk mitigations)

1. [characterize_archive_iter] Before touching `archive_iter.py`, add
   `tests/test_archive_iter_characterization.py`: a fixture archived dir with
   loose parent + loose child files, a `_b0/old0.tar.zst` bundle, a
   `_b0/old1.tar.gz` (no zst twin) and a `.tar.gz` that has a zst twin, a legacy
   `old.tar.zst`, a corrupt bundle, and a task-named member with unparseable
   frontmatter. Pin, for `iter_all_archived_markdown`,
   `iter_archived_frontmatter`, `iter_numbered_archives` and
   `find_archived_markdown_by_id`: the exact `(name, text)` sequence (order
   included) and the `errors` list, both with `errors=None` and `errors=[]`.
   Run it green against the pre-refactor code, keep it green after.

### Steps

1. **`lib/archive_iter.py` — expose the unit partition (one partition, shared):**
   - `archived_markdown_sources(archived_dir, *, errors=None) -> list[tuple[str, Path]]`
     — ordered `("loose", path)` / `("bundle", path)` units exactly as
     `iter_all_archived_markdown` reads them (loose parents — skipping child
     names —, loose children, zst bundles, gz bundles without a zst twin; loose
     globs only when `errors is not None or archived_dir.exists()`). Factor the
     zst/gz selection out of `iter_numbered_archives` into
     `_numbered_archive_paths()` used by both.
   - `iter_archive_file(archive_path, fileobj=None, *, errors=None)` — public
     wrapper of `_iter_single_archive` with an optional already-open binary
     `fileobj` (zstd: `Popen(["zstd","-dc"], stdin=fileobj, …)`; gz:
     `tarfile.open(fileobj=fileobj, mode="r:gz")`); error notes keep naming
     `archive_path`.
   - `parse_archived_frontmatter(name, text, parse_fn, *, errors=None)` — the
     per-file step of `iter_archived_frontmatter` (parse, note an unparseable
     task-named file, return metadata or None).
   - Rewrite `iter_all_archived_markdown` / `iter_archived_frontmatter` on top
     of these three (behaviour identical — the characterization test proves it).
2. **`lib/trail_schema.py`** — add `VALIDATOR_REVISION = 1` with its comment;
   factor `parse_schema(raw, origin)` (JSON parse + the two sanity checks) out
   of `load_schema`, which keeps its signature and messages and calls it; add
   keyword `schema=None` to `load_trail` (given ⇒ used instead of
   `load_schema(schema_path)`). CLI and other callers unchanged.
   **`lib/artifact_manifest.py`** — the `ManifestError` / `manifest_violation`
   / `read_manifest` refactor above; `validate` / `load` keep their CLI-facing
   die behaviour and messages (existing artifact-manifest tests must pass
   unchanged).
3. **`lib/trail_discovery_cache.py`** (new) — module-level, computed once at
   import: `OWNER_IDENTITY`, `DOC_IDENTITY`, `FROZEN_SCHEMA` (see "Identities
   are bound to the loaded producer generation"); `cache_dir()` (env override /
   disabled), `owner_identity()` / `doc_identity()` (return the frozen
   constants), `proven_manifest_dir()`,
   `manifest_current(handle)`, `class OwnerCache` (`open()`, `lookup(key, sha)`
   → list of fresh `TrailInfo` or None, `store(key, sha, records)`, `seen(key)`,
   `save()`), `class DocCache` (`open()`, `lookup(handle)` → fresh doc copy or
   None, `store(handle, blob_hash, doc)` under a `threading.Lock`, `save()`).
   Disabled ⇒ both classes are no-ops that always miss. Module docstring states
   the keying rules, the clean-units-only rule and the proven-layout rule.
4. **`lib/trail_discovery.py`**:
   - `_BlobLoad(tuple)` with `.blob_hash`; `load_trail_blob` hashes the
     `--out` file bytes after a successful get and validates via
     `trail_schema.load_trail(raw_bytes, schema=trail_discovery_cache.FROZEN_SCHEMA)`
     (same validation, one read, the schema the doc identity hashed).
   - Replace `_iter_active_task_frontmatter` + the archived half of
     `_iter_trail_frontmatter_records` with per-unit readers that consult
     `OwnerCache` (keeping the long t1365/t1371/t1379 rationale docstring on the
     active-file reader and the `unreadable` / `scan_errors` semantics exactly).
     Signature `_iter_trail_frontmatter_records(unreadable=None, scan_errors=None)`
     unchanged; it opens/saves the owner cache itself (save after exhaustion).
     `_iter_active_task_frontmatter` stays as a function with its current
     `(filename, metadata)` contract — `aitask_board.py:71` re-exports it.
   - `discover_trails`: open `DocCache`; loader `_cached_blob_loader(handle)` =
     lookup → hit `(doc, "", [])`; miss → `load_trail_blob(handle)` (module
     namespace, so test stubs still apply) → store when
     `getattr(result, "blob_hash", "")` and no error; `sequenced_trail_read`
     over the infos — no load for `n == 0`, inline for `n == 1`, the executor
     only for `n >= 2`; `DocCache.save()`. Docstrings updated
     (module docstring: the cache, and that the read-only contract still holds).
5. **Hosts**: `board_trail_screen.py` `action_trail_select` → always
   `rescan=True`, docstring rewritten (both hosts revalidate; t1895's
   dead-end concern is moot); review `_open_trail_select`'s and `trails_app.py`'s
   module/class docstrings for "serves the cache" wording.
6. **Setup for `.aitask-cache/`** (`aidocs/framework/aitasks_extension_points.md`,
   "Test the full install flow for setup helpers"): `.gitignore` entry
   (`# Discovery caches (per-checkout, content-keyed, safe to delete)` +
   `.aitask-cache/`); `setup_cache_gitignore` in `aitask_setup.sh` modelled on
   `setup_scratchpad_gitignore` (:3101) and called next to it (:5405);
   `tests/test_setup_git.sh` HELPERS row `setup_cache_gitignore|.aitask-cache/`
   (+ update the "all seven" prose count). No seed file carries gitignore rules
   (checked: `seed/` has none), so nothing to seed.
7. **Benchmark** `tests/perf/trail_discovery_bench.py` (manual, not collected):
   in this repo, with a temp `AIT_TRAIL_CACHE_DIR`, report `--no-cache`
   baseline, cold (empty dir) and warm (median of N) `discover_trails()` times,
   and the count of `artifact get` spawns per phase. Update
   `tests/perf/trails_pilot_bench.py` only if it breaks.
8. **Tests** `tests/test_trail_discovery_cache.py` (synthetic trees in temp
   cwd, `AIT_TRAIL_CACHE_DIR` per test):
   - owner layer table — unchanged (0 parses, counted via a wrapper patched on
     `trail_discovery.parse_frontmatter`; 0 bundle decompressions, counted on
     `archive_iter.iter_archive_file`), edited, new, removed (records gone,
     entry pruned), renamed-same-content (owner_id follows the name), bundle
     unchanged vs changed, folded/archived state change;
   - unreadable active file and corrupt bundle are reported on **every** scan
     (not cached);
   - **best-effort then diagnostic over the same faulty input**: a tree with a
     corrupt bundle, a truncated bundle that ends on a tar boundary (bad `zstd`
     exit) and a task-named archived member with unparseable frontmatter; scan
     once with `discover_trails()` (no `scan_errors`), then with
     `discover_trails(scan_errors=errs)` — `errs` must name all three, and the
     faulty units must have no owners-cache entry after either scan. Same for an
     unreadable active file: an ordinary
     `_iter_trail_frontmatter_records(None)` followed by `discover_trails()`
     still reports it in `unreadable`;
   - doc layer table (legacy fixture: `git init`, `artifacts/manifests/<id>.json`,
     `subprocess.run` faked to write fixture bytes): first scan spawns `get`,
     second spawns nothing and returns an equal doc; changed manifest `current`
     → miss; doc identity change (patch `VALIDATOR_REVISION`) → miss; failing
     `get` → not cached, `versions` fallback each time; plain-tuple stub loader →
     never stored; unproven layout → doc layer off;
   - **warmed cache, then a malformed manifest with `current` unchanged** — one
     case per `validate` invariant (`backend: "bad/name"`, a missing
     `updated_at`, a string `created_at`, a duplicate `versions` entry, an
     invalid version hash, a handle/filename mismatch, invalid JSON): each is a
     miss, the real `get` is spawned and the result carries its `load_error`;
   - `artifact_manifest.py` parity: for each invariant above,
     `manifest_violation` returns a reason exactly when `validate` dies, and the
     CLI (`artifact_manifest.py --manifest-dir … get <handle>`) still exits 1
     with the unchanged message;
   - parity: `proven_manifest_dir()` equals bash `artifact_manifest_dir` (sourced
     `task_utils.sh` + `lib/artifact_manifest.sh`) in a branch-mode-shaped and a
     legacy fixture;
   - corrupt cache files (garbage, truncated, wrong types, wrong identity) → miss,
     correct result, file rewritten; `AIT_TRAIL_CACHE=0` → no files written;
   - `read_seq`: hits get distinct positive `read_seq`; the manifest read
     happens while `_trail_read_lock(handle)` is held (assert `locked()` from a
     patched `manifest_current`);
   - read-only: across cold+warm scans only `artifact get`/`versions` argv seen.
   - **identity generation (concern 1)** — two real subprocesses over a temp
     copy of `.aitask-scripts/lib/` on `sys.path` and a shared temp
     `AIT_TRAIL_CACHE_DIR`: process A imports `trail_discovery`, then (still
     running) the test edits the copy — a producer change with a visible effect
     (e.g. owner records gain a marker in `name`) and, in a second case, a
     schema change that rejects a fixture doc A accepts — then A runs
     `discover_trails()` and saves. `owner_identity()` / `doc_identity()` in A
     equal their pre-edit values. Process B (fresh import of the edited copy)
     then scans: its identities differ from A's, both layers are discarded, and
     B's result equals an uncached B run (`AIT_TRAIL_CACHE=0`) — never A's
     output. Negative control: without the edit, B hits A's entries (0 parses,
     0 `get` spawns).
   - `load_trail(..., schema=)` and `parse_schema`: the frozen schema is what
     validates (a schema file edited after import does not change A's
     verdict); `load_schema()` messages unchanged.
   - **empty discovery (concern 2)** — an empty tree, an every-owner-unreadable
     tree and a tree whose last owner was just removed (warm cache first), each
     with the cache enabled **and** `AIT_TRAIL_CACHE=0`: `discover_trails()`
     returns `([], unreadable)` with `unreadable` / `scan_errors` as without
     the cache, no executor is constructed (patch
     `trail_discovery.ThreadPoolExecutor` to raise), and the existing
     `test_empty_tree_reports_no_trails_and_no_failures`
     (tests/test_trail_discovery.py:220) stays green in both modes. A
     one-trail tree also loads without the executor.
   - Existing suites: `tests/test_trail_discovery.py`,
     `tests/test_trail_discovery_sequencing.py`, `tests/test_board_bytrail_view.py`,
     `tests/test_trails_app.py` (update the `calls["discover"]` counts — `s` now
     always scans: :1365 and :1739–1743; re-check
     `test_an_empty_scan_is_not_a_dead_end`),
     `tests/test_trail_screen_host_protocol.py`. If any test runs discovery with
     cwd = the real repo, point `AIT_TRAIL_CACHE_DIR` at a temp dir there.
9. **Docs (current state)**: `website/content/docs/tuis/trails/_index.md`
   (table row "`s` … Lists the trails from the last scan"), `reference.md`
   (`s` row :18, cost table :74–75, :98), `how-to.md` (:28, :48, :55, :63),
   `workflows/implementation-trails.md` (:53, :104), `tuis/board/reference.md`
   (:34): `s` re-scans every time in both TUIs; repeat opens are fast because
   the scan result is cached under `.aitask-cache/` and revalidated by content.
   Keep "`r` in the selector" wording (t2173_2 changes the key). Run
   `python3 check_links.py --build` in `website/`.

### Post-phase (risk mitigations)

1. [cache_differential_real_repo] Run, and record the output in the plan's
   Final Implementation Notes: discovery over this repo with
   `AIT_TRAIL_CACHE=0`, then cold and warm with a temp cache dir — assert the
   three results are equal per handle (owner id, archived, folded, name,
   `load_error`, doc). Add the same equality as a fixture-based test that
   mutates a tree through a scripted sequence (edit / add / remove / archive
   into a bundle / repoint a manifest) and compares cached vs uncached after
   every step.

## Verification

- `python3 tests/test_archive_iter_characterization.py` — green before and after step 1.
- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED` (use `set -o pipefail` if piping).
- `bash tests/test_setup_git.sh`; `shellcheck .aitask-scripts/aitask_setup.sh`.
- `python3 tests/perf/trail_discovery_bench.py` — record no-cache / cold / warm numbers and `get` spawn counts in Final Implementation Notes (warm target: tens of ms, 0 spawns).
- Post-phase differential on this repo (uncached == cold == warm per handle).
- Manual: `ait trails`, `s` twice — second open near-instant; edit a trail-owning task's frontmatter and `s` shows it; same in the board's By-Trail view.
- `cd website && python3 check_links.py --build`.
- Step 9 (Post-Implementation): archive this child; parent stays until t2173_2 lands.

## Risk

### Code-health risk: medium
- `archive_iter.py` is shared (stats, explain, trail discovery, archived lookups); refactoring its iteration into a unit partition could change order or error reporting for other consumers · severity: low (residual — addressed by inline pre-phase characterize_archive_iter) · → mitigation: inline pre-phase characterize_archive_iter
- A content-keyed cache that serves a stale owner list or document would be worse than slow (wrong trail shown); the keys (path+bytes hash, fetched-blob hash, layer identities) are designed for it but the failure is silent · severity: low (residual — addressed by inline post-phase cache_differential_real_repo) · → mitigation: inline post-phase cache_differential_real_repo
- A doc-layer hit re-proves the manifest (full `validate` parity via the non-exiting refactor) but not blob availability, so an unreachable non-local store still shows the last verified document instead of an error card · severity: low · → mitigation: none (stated boundary in the module docstring; content-addressed, so never a wrong document)
- A process left running across an upgrade could label results from its old imported parser/validator with the new on-disk identity (review concern 1) · severity: low (residual — identities and the validation schema are frozen at import; only an upgrade landing mid-import is uncovered) · → mitigation: none (designed out; pinned by the identity-generation subprocess test in step 8)
- Parallel cold path could crash on an empty discovery (`ThreadPoolExecutor(max_workers=0)` raises, review concern 2) · severity: low (residual — executor only for n ≥ 2) · → mitigation: none (designed out; pinned by the empty-discovery tests in step 8)
- Best-effort scans now drain and check `zstd`'s exit status for every bundle (private per-unit diagnostics), slightly more work than today on a cold scan · severity: low · → mitigation: none

### Goal-achievement risk: low
- The warm-open target ("tens of ms") is unmeasured: listing + reading + hashing ~1300 files, 13 manifest reads and the docs JSON decode could land nearer 100ms · severity: low · → mitigation: none (the benchmark in t2173_1 step 7 measures it; a miss is a follow-up, not a redesign)
- The doc layer is off in layouts Python cannot prove (an unlinked linked worktree) — correct but slower there · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_archive_iter | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: archive_iter refactor changing order/error reporting for other consumers | desc: pin archive_iter readers' (name, text) sequence and errors on a mixed fixture before the refactor (t2173_1)
- timing: post-phase | name: cache_differential_real_repo | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: cache silently serving a stale owner list or document | desc: uncached vs cold vs warm equality on this repo plus a scripted-mutation cached-vs-uncached fixture test (t2173_1)

## Post-Review Changes

### Change Request 1 (2026-10-31 22:10)
- **Requested by user:** two blocking review concerns, both verified and
  confirmed. (1) `DocCache.lookup` accepted any cached dict whose `blob` field
  matched the manifest's `current`: a dict-shaped corruption (`{"waves":[0]}`,
  `{}`) was served with `load_error=""` and zero `get` spawns, and crashed
  `trail_entry_refs`. (2) `setup_cache_gitignore` ran only from `ait setup`;
  `ait upgrade` (install.sh) never runs setup and the release tarball carries
  no root `.gitignore`, so an upgraded-only project showed `?? .aitask-cache/`.
- **Changes made:**
  1. The doc layer stores the fetched blob's **raw bytes** (UTF-8 text) instead
     of the parsed document. A hit requires the manifest `current` == entry
     `blob`, `sha256(raw)` == `current` (it IS the blob `get` verified), and
     re-validation with `FROZEN_SCHEMA`; the document is parsed fresh from
     `raw` (no `deepcopy`). Any failure — hash mismatch, invalid document, lone
     surrogate, `RecursionError` — is a miss that falls back to the real `get`.
     `_BlobLoad` gained `.blob_raw`. Warm cost on this repo: 62 ms median
     (was 55 ms), still 0 `get` spawns.
  2. `aitask_setup.sh`: `_ait_add_cache_gitignore_rule` (write only, 0 added /
     1 present); `setup_cache_gitignore` = write + `_ait_commit_gitignore_rule`;
     new `upgrade_cache_gitignore` = write only. `install.sh` calls it for
     existing installs (guarded by `declare -F`), beside
     `setup_data_gitignore_symlink_safe`, before `commit_installed_files` — so
     the pre-upgrade dirty baseline decides whether `.gitignore` is committed.
  3. Tests: `DocEntryIntegrityTests` (six forgeries incl. dict-shaped ones, a
     forged entry holding the real-but-invalid blob, fresh parse per hit);
     `test_install_upgrade_dirty_baseline.sh` cases K (clean `.gitignore`:
     rule committed, a written cache file stays out of `git status`, no
     duplicate on re-upgrade) and K2 (dirty `.gitignore`: rule on disk only).
     Negative controls: mutants dropping the hash check or the re-validation
     each fail `DocEntryIntegrityTests`; the pre-fix `install.sh` (HEAD) fails
     6 K/K2 assertions, reproducing `?? .aitask-cache/trail_discovery/owners.json`.
- **Files affected:** `.aitask-scripts/lib/trail_discovery_cache.py`,
  `.aitask-scripts/lib/trail_discovery.py`, `.aitask-scripts/aitask_setup.sh`,
  `install.sh`, `tests/test_trail_discovery_cache.py`,
  `tests/test_install_upgrade_dirty_baseline.sh`.

### Change Request 2 (2026-10-31 22:40)
- **Requested by user:** one blocking concern, verified and confirmed:
  `_ait_add_cache_gitignore_rule` returned 0 ("added") after an unchecked
  grouped redirection, and both wrappers call it in a status-tested context
  (errexit suspended), so a read-only `.gitignore` printed "Permission denied"
  yet both wrappers announced success while the rule stayed absent. An
  unreadable `.gitignore` (grep exit 2) was also misread as "rule absent".
- **Changes made:** the helper returns 0 added / 1 already present / 2 could
  not inspect or write — every write is checked (`2>/dev/null` placed BEFORE
  the target redirection, since a failed redirection is reported before later
  redirections apply) and the rule is read back before it counts. Both
  wrappers branch on all three: rc 2 → `_ait_warn_cache_gitignore_failed`
  (accurate warning + the `ait setup` repair hint), non-fatal, no commit, no
  success claim. Tests: `tests/test_setup_git.sh` 27f (both wrappers × a
  read-only file and a directory in place of `.gitignore`: rc 0, the failure
  reported, no added/already claim, no commit, file unchanged) and 27g (the
  upgrade wrapper's add + idempotent no-op, never committing). Negative
  control: the pre-fix helper body under the same read-only fixture prints
  "Added .aitask-cache/ to .gitignore" over an unchanged file.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`, `tests/test_setup_git.sh`.

## Final Implementation Notes
- **Actual work done:** all nine plan steps plus both inline mitigations.
  - Pre-phase `characterize_archive_iter`: `tests/test_archive_iter_characterization.py`
    (10 tests) pins every archive_iter reader's `(name, text)` order and `errors`
    list on a mixed tree (loose parents/children, a child name at top level, a
    CRLF file, zst + gz bundles with and without a twin, a garbage bundle, a
    whole archive followed by trailing garbage → `zstd exited 1`, an
    unparseable member, legacy `old.tar.zst`, by-id lookups). Green before and
    after the refactor; the existing `test_archive_iter_consolidated.py` (42)
    also stayed green.
  - `archive_iter.py`: `_numbered_archive_paths`, `archived_markdown_sources`,
    `read_loose_markdown`, `iter_archive_file(archive_path, fileobj=None)`,
    `parse_archived_frontmatter`; the public readers are rebuilt on them.
  - `trail_schema.py`: `VALIDATOR_REVISION = 1`, `parse_schema(raw, path)`
    (factored out of `load_schema`), `load_trail(..., *, schema=None)`.
  - `artifact_manifest.py`: `ManifestError`, `manifest_violation`,
    `read_manifest`; `validate` / `load` are thin dying wrappers, messages
    unchanged (`test_artifact_manifest_lib.sh` 50/50, `test_artifact_cli.sh`
    251/251).
  - `lib/trail_discovery_cache.py` (new): `OwnerCache` / `DocCache` over
    `owners.json` / `docs.json`; identities and `FROZEN_SCHEMA` frozen at
    import; `proven_manifest_dir`; `manifest_current`.
  - `trail_discovery.py`: per-unit cached readers, `_BlobLoad` (`blob_hash`,
    `blob_raw`), `_cached_blob_loader`, `discover_trails` with the executor
    only for ≥2 trails.
  - Hosts: `action_trail_select` always re-scans; host docstrings updated.
  - Setup: `.gitignore` rule; `_ait_add_cache_gitignore_rule` +
    `setup_cache_gitignore` (setup) + `upgrade_cache_gitignore` (called by
    install.sh for existing installs).
  - Docs: trails `_index` / `reference` / `how-to`, `implementation-trails`,
    board `reference`. `check_links.py --build`: SWEEP PASSED.
  - Post-phase `cache_differential_real_repo`: `tests/perf/trail_discovery_bench.py`
    on this repo (13 trails), final run:
    ```
    phase        seconds  get spawns
    no-cache       2.341          13
    cold           1.904          13
    warm           0.062           0   (median of 7; min 0.060, max 0.073)
    DIFFERENTIAL: PASS — uncached == cold == warm for all 13 handle(s)
    ```
    (first run, before the doc-entry re-proof: no-cache 1.957 / cold 1.890 /
    warm 0.055). The fixture-based scripted-mutation differential is
    `CachedEqualsUncachedTests.test_scripted_mutation_sequence` (edit / add /
    remove / archive into a bundle / repoint a manifest / folded duplicate /
    store failure on a fresh handle / recovery).
- **Deviations from plan:**
  - `archived_markdown_sources` is a lazy generator, not a list: with a list,
    every directory would be listed before any loose file is read, which
    reorders the `errors` interleaving the characterization pins.
  - `OwnerCache.lookup` returns record tuples; `trail_discovery` builds the
    fresh `TrailInfo`s (no import cycle between the two modules).
  - The doc layer stores the blob's raw bytes, not the parsed doc (Change
    Request 1), and the identity tests patch the frozen `DOC_IDENTITY` rather
    than `VALIDATOR_REVISION` (identities are frozen at import — review
    concern 1 of the plan review).
  - A faulty active file that is not task-named (e.g. `README.md` failing to
    parse) is not cached either — re-parsed each scan; trivial cost, simpler
    rule ("a unit whose parse failed is never cached").
  - The planned "failing get, versions fallback" table and the post-phase
    differential surfaced the stated boundary concretely: a handle whose store
    becomes unreachable behind a VALID manifest is served from the cache (the
    last verified document). It is pinned as its own test
    (`test_the_stated_boundary_blob_availability_is_not_reproven`) instead of
    being part of the equality sequence, which uses a fresh handle for the
    store-failure step.
- **Issues encountered:**
  - Existing tests scanning an absolute `TASK_DIR` from the repo root wrote a
    real `.aitask-cache/` into the checkout: `tests/test_trail_discovery.py`'s
    `_tree()` now points `AIT_TRAIL_CACHE_DIR` into its temp tree. After the
    full suite no `.aitask-cache/` is left in the repo.
  - `tests/test_trails_app.py`: 7 cases asserted the old "`s` serves the
    in-memory list" counts; updated to "`s` always scans". The rev2 case is
    stronger now: the stub's re-scan (original doc, `read_seq=0`) must lose to
    rev2 under newest-wins.
  - Inside doc-layer tests `subprocess.run` is the fake store, so the bundle
    builder binds the real `subprocess.run` at import.
- **Key decisions:**
  - Cleanliness of a unit is decided from private per-unit diagnostics on
    every scan; best-effort scans therefore now drain and check `zstd`'s exit
    status (they report to nobody, they just refuse to cache).
  - Verification by mutants (isolated copy under the scratchpad): identity
    re-read from disk, schema re-read, validating with the on-disk schema,
    owner identity omitting `trail_discovery.py`, no empty-discovery guard,
    caching a faulty bundle, caller's lists deciding cleanliness, a hand-rolled
    manifest check, no `current` check, lookup outside the read lock, no hash
    re-proof, no re-validation — every one fails the new tests. One equivalent
    mutant survives (dropping the `not error` guard before `store`: on error
    `blob_hash` / `blob_raw` are empty and `store` refuses them).
  - The pre-fix `install.sh` (HEAD) fails 6 of the new upgrade assertions
    (cases K/K2), reproducing `?? .aitask-cache/trail_discovery/owners.json`.
- **Upstream defects identified:**
  - `install.sh:1909-1914` — `ait upgrade` never runs setup and calls only the `.gitignore` repairs explicitly wired into it, so the setup-only rules `.aitask-scratchpad/`, `.aitask-shadow/`, `.aitask-gates/` and `.aitask-testmap/` (`setup_scratchpad_gitignore`, `setup_shadow_store_gitignore`, `setup_gate_logs_gitignore`, `setup_testmap_gitignore` in `aitask_setup.sh`) never reach an upgraded-only project — their stores show as untracked there (this task wired only `.aitask-cache/`).
  - `.aitask-scripts/lib/trail_schema.py:645-652` — `load_trail` catches only `ValueError` from `json.loads`, so a deeply nested JSON payload raises `RecursionError` out of `load_trail` (and out of `trail_discovery.load_trail_blob`, which catches only `TrailValidationError`), crashing the discovery worker instead of yielding a fail-closed `load_error` card. The cache's hit path already treats it as a miss.
- **Notes for sibling tasks:**
  - t2173_2 (two-pane dialog): `s` now ALWAYS re-scans in both hosts
    (`action_trail_select` → `_open_trail_select(rescan=True)`); the
    `LoadingOverlay("Scanning for trails…")` still shows on every scan (a warm
    one ~60 ms only flashes it). `r` in the selector still dismisses
    `TRAIL_SELECT_RESCAN`; with `s` re-scanning, `r` is now redundant for
    picking up new trails — when you rebind it for the search box, the docs
    that still mention "`r` in the selector" are trails `reference.md` (keys
    table :41, refresh table, Tabs section) only.
  - Tests that run real discovery should set `AIT_TRAIL_CACHE_DIR` to a temp
    dir (or `AIT_TRAIL_CACHE=0`); the cache dir is cwd-relative by default.
  - t2173_3 (manual verification): the warm open should feel near-instant;
    `.aitask-cache/trail_discovery/{owners,docs}.json` appear in the checkout
    and are gitignored; editing a trail-owning task's frontmatter is picked up
    by the next `s`.
