---
Task: t2173_trail_select_two_pane_dialog_and_discovery_cache.md
Base branch: main
Output branch: main
---

# t2173 — Trail selector: content-keyed discovery cache + two-pane dialog

## Context

Opening the trail selector costs ~3.3s per scan (`discover_trails()`:
archived frontmatter ~1.43s, active frontmatter ~0.36s, 13 serial
`artifact get` + validation ~1.43s), and the board rescans on every `s`. The
dialog itself is a 60%×50% list whose rows carry `└ also references` sub-lines,
which makes many trails hard to scan. Goal: a warm open costs hashing plus
re-parsing only what changed (tens of ms), on-disk so it survives launches and
content-keyed so it is revalidated on every open; and a large two-pane dialog
(fuzzy-filtered title list | details of the highlighted trail). Both hosts —
`KanbanApp` By-Trail and `ait trails` (`TrailsApp`) — share `TrailSelectScreen`
and `discover_trails`, so both get both changes.

**Decomposition (user-confirmed): two children**, each self-contained for a fresh
context. t2173_2 does not depend on t2173_1's code, but lands after it (sibling
auto-dependency) so the docs are edited in order.

- **t2173_1** — discovery cache + both hosts revalidate on every `s` + benchmark
  + `.aitask-cache/` setup + docs for the `s` semantics.
- **t2173_2** — two-pane `TrailSelectScreen` + Ctrl+R rescan + test migration +
  docs for the selector + note to t1647_5.

---

## t2173_1 — Content-keyed discovery cache

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
2. **`lib/trail_schema.py`** — add `VALIDATOR_REVISION = 1` with its comment.
   **`lib/artifact_manifest.py`** — the `ManifestError` / `manifest_violation`
   / `read_manifest` refactor above; `validate` / `load` keep their CLI-facing
   die behaviour and messages (existing artifact-manifest tests must pass
   unchanged).
3. **`lib/trail_discovery_cache.py`** (new) — `cache_dir()` (env override /
   disabled), `owner_identity()`, `doc_identity()`, `proven_manifest_dir()`,
   `manifest_current(handle)`, `class OwnerCache` (`open()`, `lookup(key, sha)`
   → list of fresh `TrailInfo` or None, `store(key, sha, records)`, `seen(key)`,
   `save()`), `class DocCache` (`open()`, `lookup(handle)` → fresh doc copy or
   None, `store(handle, blob_hash, doc)` under a `threading.Lock`, `save()`).
   Disabled ⇒ both classes are no-ops that always miss. Module docstring states
   the keying rules, the clean-units-only rule and the proven-layout rule.
4. **`lib/trail_discovery.py`**:
   - `_BlobLoad(tuple)` with `.blob_hash`; `load_trail_blob` hashes the
     `--out` file bytes after a successful get and validates via
     `trail_schema.load_trail(raw_bytes)` (same validation, one read).
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
     `getattr(result, "blob_hash", "")` and no error; parallel
     `sequenced_trail_read` as above; `DocCache.save()`. Docstrings updated
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
   - Existing suites: `tests/test_trail_discovery.py`,
     `tests/test_trail_discovery_sequencing.py`, `tests/test_board_bytrail_view.py`,
     `tests/test_trails_app.py` (update the `calls["discover"]` counts — `s` now
     always scans; re-check `test_an_empty_scan_is_not_a_dead_end`),
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

---

## t2173_2 — Two-pane `TrailSelectScreen`

### Design

`board/board_trail_view.py` — replace `TrailSelectItem` + the list body of
`TrailSelectScreen` (:704–:820). Constructor signature, `GuardedModalScreen`
base, `TRAIL_SELECT_RESCAN`, `open_handles`, `allow_rescan` and dismissal
values unchanged.

```
Container#trail_select_dialog            (90% × 80%, own ids — not #dep_picker_dialog)
  Label#trail_select_title     "Select trail" (bold)
  Label#trail_select_hint      "Type to filter · ↑/↓ move · Enter open · Ctrl+R rescan · Esc cancel"
                               (the Ctrl+R segment only when allow_rescan)
  Horizontal#trail_select_body (1fr)
    Vertical#trail_select_left (40%, min-width 24)
      Input#trail_select_search   placeholder "Filter by title…"   (focused on mount, keeps focus)
      TrailTitleList#trail_select_list   OptionList subclass, can_focus=False; one Option per
                                         shown trail, id = handle, prompt = title [+ "  ● open"]
    TrailDetailPane#trail_select_detail (1fr)   VerticalScroll subclass, can_focus=False
      Static#trail_select_detail_body
  Horizontal#trail_select_buttons
    Button "Cancel" #btn_trail_select_cancel
```

- **Focus model (settled)**: the search `Input` and the Cancel button are the
  only focusable widgets. Both the list and the detail pane are
  `can_focus=False` subclasses — `VerticalScroll` is focusable by default in
  Textual 8.2.7, and a focused detail pane would re-activate both Apps'
  priority `nav_up/nav_down` (focus moves instead of scrolling). Tab /
  Shift+Tab cycle box ↔ Cancel; with Cancel focused, ↑/↓ follow each host's
  existing modal behaviour (back to the box). The detail pane scrolls with
  **PgUp/PgDn** (screen bindings; neither `Input` nor either App binds them)
  and the mouse wheel; ↑/↓ always belong to the list.
- **Keys**: screen `BINDINGS` `up`/`down` → the list's cursor actions,
  `pageup`/`pagedown` → the detail pane's `scroll_page_up/down`
  (non-priority: with the `Input` focused both Apps'
  priority `nav_up/down` are inactive — `KanbanApp.check_action` :2465,
  `TrailsApp.check_action` :784 — so arrows fall through to the screen);
  `Input.Submitted` → dismiss highlighted handle; `OptionList.OptionSelected`
  (click) → dismiss that handle; `escape` + Cancel → `None`;
  **`ctrl+r` → `TRAIL_SELECT_RESCAN` when `allow_rescan`** (decision: a typed
  `r` must reach the search box, and a focus-aware `r` would never fire because
  the box always has focus).
- **Hint**: two lines so it fits 80×24 —
  `Type to filter · ↑/↓ move · Enter open · Esc cancel` and
  `PgUp/PgDn scroll details` (+ ` · Ctrl+R rescan` when `allow_rescan`).
- **Filtering**: `fuzzy_filter.rank(query, infos, key=_trail_select_title)` —
  title only (`doc.title or info.name or info.handle`, factored out of the old
  row code); blank query = original order; highlight resets to the first match;
  no match → empty list and the detail pane says `No trail title matches "<q>"`;
  Enter with no match does nothing.
- **Detail pane** — pure `trail_select_detail(info, overlap_notes, is_open) ->
  Text` (headless-testable, all values appended as `Text`, never markup):
  title (+ `● open`), handle; Owner `t<id>` + `(archived)` / `(folded)`; Scope
  kind; Freshness `_trail_stored_freshness(info)`; Generated
  `trail_generated_label(raw) or raw or "?"`; a **Shared tasks** block from
  `compute_trail_overlaps` (`<ref> — also in <other title>`); for `load_error`
  trails an **Error** block and the recorded `versions` fallback. Re-rendered
  on `OptionList.OptionHighlighted` and after each filter change.
- **CSS**: own `DEFAULT_CSS` covering every rule above plus a visible
  highlight for the unfocused list
  (`#trail_select_list > .option-list--option-highlighted`), per
  tui_conventions "Modals pushed by multiple Apps".
- Remove `TrailSelectItem`; drop it from `aitask_board.py`'s re-export (:125)
  and the export lists in `tests/test_board_trail_view.py` (:63, :207).

### Steps

1. Implement the screen + `trail_select_detail` + `_trail_select_title` in
   `board_trail_view.py`; update the module docstring's modal list if needed.
2. Tests:
   - `tests/test_board_trail_view.py` `ModalDefaultCssTests`: `#trail_select_dialog`
     at 0.9 width, scoping negative control with a plain modal reusing that id.
   - `tests/test_board_bytrail_view.py` (:685–:810): highlight moves on `down`
     and changes the frame while the search box keeps focus; overlap note shows
     in the detail pane and not in the list; last option reachable (scrolled
     into view), Cancel visible; hint not truncated at 80×24.
   - New, in **both** hosts (KanbanApp By-Trail and TrailsApp): typing filters
     by title only (a query matching only an owner/scope string matches
     nothing); subsequence match; ↑/↓ move the highlight and update the detail
     pane; Enter opens the highlighted trail; click opens; Esc → nothing opened;
     typed `r` lands in the box and does not rescan; Ctrl+R rescans only with
     `allow_rescan`; `● open` marker in list and detail; error trail shows error
     + versions.
   - **Focus cycle + overflowed details, in both hosts**: with a detail pane that
     overflows (an error trail with many recorded versions, or many shared
     tasks) — Tab and Shift+Tab from the box visit only the box and Cancel, never
     `#trail_select_detail` or the list (`app.focused` after each press); PgDn
     raises the pane's `scroll_y` and PgUp lowers it; the last detail line is
     viewable after enough PgDn; ↑/↓ still move the list highlight after a Tab
     round-trip; with Cancel focused, ↑ returns focus to the box rather than
     scrolling or leaving the dialog.
   - `tests/test_trails_app.py`: `pilot.press("r")` in the selector → `ctrl+r`
     (:203, :1611; check :2137 is the main-screen `r`); :1367 query the list's
     options instead of `TrailSelectItem`; `test_a_stale_selector_key_pops_nothing`
     unchanged (it calls `action_rescan`/`action_cancel`).
   - `tests/test_board_detail_followup_kind.py:539` — check whether it targets
     this dialog's `#btn_dep_cancel`; adapt if so.
   - `tests/perf/trails_pilot_bench.py`: select the trail by typing/highlight,
     not by focusing a `TrailSelectItem`.
3. Docs: `tuis/trails/reference.md` "In the trail selector" table (type to
   filter, ↑/↓, Enter or click, Ctrl+R, Esc) and a sentence on the two panes;
   every "`r` in the selector" in `how-to.md`, `_index.md`, `reference.md`,
   `workflows/implementation-trails.md` → Ctrl+R; `how-to.md` "Rows for trails
   that are already open are marked `● open`" still true (keep). Run
   `check_links.py --build`.
4. Step 8e: `./ait note 1647_5 --from 2173_2` — `TrailSelectItem` is gone; model
   `TrailMergeSelectScreen` on the two-pane `TrailSelectScreen` (search box +
   `TrailTitleList` + `trail_select_detail`), overlaps now render in the detail
   pane. Hedge: the note's SHA dates it.

---

## Verification

- t2173_1: `python3 tests/test_archive_iter_characterization.py` (green before
  and after step 1); `bash tests/run_all_python_tests.sh` (last line
  `PYTHON SUITE: PASSED`); `bash tests/test_setup_git.sh`; `shellcheck
  .aitask-scripts/aitask_setup.sh`; `python3 tests/perf/trail_discovery_bench.py`
  (record cold/warm numbers; warm target: tens of ms, 0 `get` spawns); the
  real-repo differential (post-phase); manual: `ait trails`, `s` twice — the
  second open is near-instant; edit a trail-owning task's frontmatter, `s`
  shows the change; same in the board's By-Trail view.
- t2173_2: the Python suite; manual in both TUIs at 80×24 and a wide terminal:
  type to filter, arrows, Enter, click, Ctrl+R (trails only), Esc, an error
  trail's detail pane.
- Step 9 (Post-Implementation) of the shared workflow handles archival of each
  child and, after the last child, the parent.

## Risk

### Code-health risk: medium
- `archive_iter.py` is shared (stats, explain, trail discovery, archived lookups); refactoring its iteration into a unit partition could change order or error reporting for other consumers · severity: low (residual — addressed by inline pre-phase characterize_archive_iter) · → mitigation: inline pre-phase characterize_archive_iter
- A content-keyed cache that serves a stale owner list or document would be worse than slow (wrong trail shown); the keys (path+bytes hash, fetched-blob hash, layer identities) are designed for it but the failure is silent · severity: low (residual — addressed by inline post-phase cache_differential_real_repo) · → mitigation: inline post-phase cache_differential_real_repo
- The dialog rewrite changes keyboard routing in two Apps that bind arrows with `priority=True`; a host whose `check_action` does not fall through for the focused `Input` would lose ↑/↓ · severity: low · → mitigation: none (t2173_2 tests both hosts)
- ~6 test files and the perf bench need migration with the dialog and the `s` semantics · severity: low · → mitigation: none
- A doc-layer hit re-proves the manifest (full `validate` parity via the non-exiting refactor) but not blob availability, so an unreachable non-local store still shows the last verified document instead of an error card · severity: low · → mitigation: none (stated boundary in the module docstring; content-addressed, so never a wrong document)
- Best-effort scans now drain and check `zstd`'s exit status for every bundle (private per-unit diagnostics), slightly more work than today on a cold scan · severity: low · → mitigation: none

### Goal-achievement risk: low
- The warm-open target ("tens of ms") is unmeasured: listing + reading + hashing ~1300 files, 13 manifest reads and the docs JSON decode could land nearer 100ms · severity: low · → mitigation: none (the benchmark in t2173_1 step 7 measures it; a miss is a follow-up, not a redesign)
- The doc layer is off in layouts Python cannot prove (an unlinked linked worktree) — correct but slower there · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_archive_iter | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: archive_iter refactor changing order/error reporting for other consumers | desc: pin archive_iter readers' (name, text) sequence and errors on a mixed fixture before the refactor (t2173_1)
- timing: post-phase | name: cache_differential_real_repo | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: cache silently serving a stale owner list or document | desc: uncached vs cold vs warm equality on this repo plus a scripted-mutation cached-vs-uncached fixture test (t2173_1)
