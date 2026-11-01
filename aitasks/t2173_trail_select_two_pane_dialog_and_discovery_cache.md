---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [trails, aitask_board, tui, performance]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2173_3]
created_at: 2026-10-31 18:23
updated_at: 2026-11-01 09:07
---

## Goal

The trail-selection dialog gets slower as trails and archived tasks accumulate,
and with many trails its list is hard to scan. Two changes:

1. **Discovery cache.** Opening the trail selector after the first time must be
   fast. The cache lives on disk, so it survives app launches, and it is keyed on
   content, so it is checked on every open and never serves a stale list.
2. **Two-pane selection dialog.** A larger dialog. Left pane: a list of trail
   titles only, with a fuzzy search box at the top. Right pane: details of the
   trail currently highlighted.

Both hosts get the new behaviour: `ait trails` (`TrailsApp`) and the board's
By-Trail view (`KanbanApp`). They share `TrailSelectScreen` and
`discover_trails`.

## Current state (measured 2026-10-31 in this repo, 13 trails)

`discover_trails()` (`.aitask-scripts/lib/trail_discovery.py`) takes **~3.3s**
per scan, in three parts:

| phase | cost | grows with |
|---|---|---|
| archived frontmatter (`iter_archived_frontmatter`: 2402 files, mostly decompressed from `aitasks/archived/_b*/old*.tar.zst`) | ~1.43s | archive size |
| active task frontmatter (648 files) | ~0.36s | active tasks |
| `load_trail_blob` per trail: one serial `aitask_artifact.sh get` subprocess plus `trail_schema.load_trail` validation | ~0.11s × 13 = ~1.43s | number of trails |

When the scan runs:
- **Board:** `action_trail_select` (`board_trail_screen.py`) rescans on every
  `s`, and entering By-Trail sets `_trail_infos = None`
  (`aitask_board.py` ~:3761).
- **`ait trails`:** keeps an in-memory `_trail_infos` for the session and
  rescans only on `r`, but every launch scans again.

Cheap inputs for a content key:
- sha256 of every active and archived task file plus every archive bundle:
  **13ms** for 1276 files.
- Each trail's manifest records `current: sha256:<hash>`, a content address of
  the stored blob (for example
  `.aitask-data/artifacts/manifests/trail-crew-runner.json` in branch mode).
  Resolve manifests through `lib/artifact_manifest.py` (`manifest_path`, `load`)
  and the artifact config. Never hardcode `.aitask-data/`, because legacy mode
  is still supported.

## Part 1: Content-keyed discovery cache

A warm open should cost hashing plus a re-parse of only what changed: tens of ms
instead of seconds.

- **Owner-record layer.** Map each task file and archive bundle's *content hash*
  to the trail `TrailInfo` owner records it yields. Almost every file yields
  none, so cache those empty results too. A changed or new file (or bundle) is
  parsed again; a vanished one drops out. Owner state (archived, folded) comes
  from the file contents, so the hash covers it. Stat freshness alone
  (mtime/size) is not an acceptable key: key on the contents of every input the
  producer reads.
- **Document layer.** Map `(handle, manifest current hash, trail-schema
  identity)` to the validated trail document. "Schema identity" means a hash of
  `lib/implementation_trail.schema.json` plus a version constant in
  `trail_schema.py`, so a validator change invalidates every entry. **Do not
  cache failures** (`load_error` set): an unresolved artifact is a retryable
  condition and must stay fail-closed. It keeps the `versions` fallback listing
  and runs a real `artifact get` each time.
- **Keep these contracts:**
  - `discover_trails()` returns `(infos, unreadable)`.
  - `unreadable` and `scan_errors` reporting (t1365, t1957_3) is unchanged:
    cached data never hides an unreadable file.
  - `TASK_DIR` is resolved per call.
  - The read-only contract holds: only `artifact get` and `artifact versions`
    are ever spawned.
  - `read_seq` ordering (`sequenced_trail_read`): a cache hit is still a read
    and must still draw its sequence inside the per-handle lock, after reading
    the manifest, so `_reconcile_discovered_trails` keeps its newest-wins
    guarantee.
- **Storage.** A new gitignored per-checkout directory, with atomic writes. The
  board and `ait trails` can run at once and both write it, so a torn or corrupt
  cache file must be treated as a miss, never as an error. Adding a new local
  directory follows `aidocs/framework/aitasks_extension_points.md` (`.gitignore`,
  seed, setup).
- **Hosts.** Once revalidation is cheap, both hosts should revalidate on every
  open, which removes the stale-list problem the in-memory cache has. Decide in
  planning whether `TrailsApp` still needs a session cache and whether the
  `LoadingOverlay("Scanning for trails…")` should only appear on a cold scan.
- Optionally run the cold-path blob loads in parallel (different handles never
  share a lock).
- Extend `tests/perf/trails_pilot_bench.py` (or add a benchmark) to report cold
  and warm open times.

## Part 2: Two-pane `TrailSelectScreen`

Today the dialog (`board_trail_view.py` `TrailSelectScreen` and
`TrailSelectItem`) is 60% wide with max height 50%. Each row is
`title · owner · scope · freshness · updated`, followed by one
`└ also references: <ref> (<other title>)` sub-line per shared task. That second
part is what makes the list hard to scan.

New layout, a much larger dialog (for example ~90% × 80%):
- **Left pane:** a fuzzy search `Input` at the top, then a list of **titles
  only**, with an `● open` marker for trails that already have a tab.
  - Filtering matches the **title only**, using
    `.aitask-scripts/lib/fuzzy_filter.py`. See also `FuzzySelect` in
    `lib/agent_model_picker.py` as a reusable pattern.
  - ↑/↓ move through the list while focus is in the search box.
  - Enter opens the highlighted trail; a click also opens.
- **Right pane:** details of the highlighted trail:
  - A metadata block: owner (and whether it is archived), scope kind, stored
    freshness (`_trail_stored_freshness`), the generated-at label
    (`trail_generated_label`), and the open marker.
  - The shared-task lines (the current "also references" notes from
    `compute_trail_overlaps`), moved here out of the list.
  - Error trails (`load_error`) show their error and the versions fallback here.

Keep the existing behaviour:
- It is a `GuardedModalScreen`, so a late key must not pop a different screen.
- `Esc` and the Cancel button dismiss `None`.
- `r` dismisses `TRAIL_SELECT_RESCAN` only when `allow_rescan`. **Note:** with a
  search box, a typed `r` must reach the input, so `r` needs another binding or
  a focus-aware check. Pick one in planning and update the title hint.
- Dismissing a handle; `open_handles`.
- The `DEFAULT_CSS` self-containment rule for modals pushed by several Apps.

Read `aidocs/framework/tui_conventions.md` before editing.

## Tests and related work

- Tests that use the dialog or discovery: `tests/test_trails_app.py`,
  `tests/test_board_bytrail_view.py`, `tests/test_board_trail_view.py`,
  `tests/test_trail_screen_host_protocol.py`,
  `tests/perf/trails_pilot_bench.py`.
- Cache tests to add:
  - A hit/miss table per layer: unchanged, edited, new and removed files; a
    changed manifest `current`; a schema change.
  - A corrupt cache file is treated as a miss.
  - A failure is not cached.
  - The `read_seq` and `unreadable` paths are unchanged.
- **t1647_5** (board By-Trail fold-trails command) plans a
  `TrailMergeSelectScreen` modelled on `TrailSelectScreen` and its item widget,
  reusing the overlaps dict. Check its status when planning and coordinate (or
  send it a note) so it builds on the new two-pane widget rather than the old
  row layout.
