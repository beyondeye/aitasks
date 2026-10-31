---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: []
issue_type: performance
status: Implementing
labels: [trails, aitask_board, performance]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2173
implemented_with: claudecode/opus5_5
created_at: 2026-10-31 19:29
updated_at: 2026-10-31 21:58
---

## Context

Child 1 of t2173 (trail selector: discovery cache + two-pane dialog). Opening the
trail selector costs ~3.3s per scan in this repo (13 trails): `discover_trails()`
in `.aitask-scripts/lib/trail_discovery.py` re-reads archived frontmatter (~1.43s,
2402 files mostly decompressed from `aitasks/archived/_b*/old*.tar.zst`), active
frontmatter (~0.36s, 648 files) and runs one serial `aitask_artifact.sh get`
subprocess + `trail_schema.load_trail` validation per trail (~0.11s × 13). The
board rescans on every `s`; `ait trails` (`TrailsApp`) keeps an in-memory list per
session (stale until `r`) and rescans on every launch.

Goal: an on-disk, content-keyed cache so a warm open costs hashing plus re-parsing
only what changed (tens of ms), revalidated on every open in BOTH hosts. Child 2
(t2173_2) replaces the dialog itself and depends on this child landing first only
for doc ordering.

**The full design, every decision and the step list are in the child plan
`aiplans/p2173/p2173_1_content_keyed_trail_discovery_cache.md` — read it first.**
Summary of the binding decisions (from the approved parent plan, including a
review round that tightened three points):

- New pure module `lib/trail_discovery_cache.py`; two layers in two files under
  `${AIT_TRAIL_CACHE_DIR:-.aitask-cache/trail_discovery}` (`owners.json`,
  `docs.json`); `AIT_TRAIL_CACHE=0` disables. Layer identities hash the producer
  sources (+ `trail_schema.VALIDATOR_REVISION` for docs). Corrupt/torn cache = miss.
- **Owner layer**: key = path, value = (sha256 of bytes, records). Only clean units
  are cached, and "clean" is decided from **private per-unit diagnostics collected
  on every scan regardless of the caller's `scan_errors` / `unreadable`** (the board
  scans with neither; `trail_links.build_export` scans with `scan_errors`), forwarded
  to the caller only when requested. Hash and parse read the same bytes / same fd.
- **Doc layer**: key = (handle, manifest `current`, doc identity); stored under the
  content address of the bytes `get` wrote (`_BlobLoad(tuple)` with `.blob_hash`,
  so plain-tuple test stubs are never cached). Manifest read goes through a new
  **non-exiting** `artifact_manifest.read_manifest` / `manifest_violation` that runs
  the full `validate` invariants (backend shape, timestamps, versions, filename…);
  any invalid manifest is a miss. Manifest dir only for provable layouts (rung 1
  `.aitask-data/.git`, or a primary legacy checkout); else the doc layer is off.
  Hits re-prove the manifest, not blob availability (stated boundary).
- Contracts unchanged: `(infos, unreadable)`, `TASK_DIR` per call, only `artifact
  get`/`versions` spawned, `read_seq` drawn inside the per-handle lock after the
  manifest read, failures never cached. Cold blob loads parallel (≤4 threads).
- Both hosts: `action_trail_select` always rescans; `LoadingOverlay` kept.
- New gitignored `.aitask-cache/` via `setup_cache_gitignore` in `aitask_setup.sh`.

## Key files to modify

- `.aitask-scripts/lib/archive_iter.py` — `archived_markdown_sources`,
  `iter_archive_file(fileobj=…)`, `parse_archived_frontmatter`; readers rebuilt on them.
- `.aitask-scripts/lib/artifact_manifest.py` — `ManifestError`, `manifest_violation`,
  `read_manifest`; `validate`/`load` keep CLI behaviour.
- `.aitask-scripts/lib/trail_schema.py` — `VALIDATOR_REVISION`.
- `.aitask-scripts/lib/trail_discovery_cache.py` — new.
- `.aitask-scripts/lib/trail_discovery.py` — per-unit cached readers, `_BlobLoad`,
  cached + parallel `discover_trails`.
- `.aitask-scripts/board/board_trail_screen.py` — `action_trail_select` rescans always.
- `.gitignore`, `.aitask-scripts/aitask_setup.sh`, `tests/test_setup_git.sh`.
- Docs: `website/content/docs/tuis/trails/{_index,reference,how-to}.md`,
  `website/content/docs/workflows/implementation-trails.md`,
  `website/content/docs/tuis/board/reference.md` (the `s` semantics only).

## Reference files

- `tests/test_trail_discovery.py`, `tests/test_trail_discovery_sequencing.py`
  (stub shapes the new code must keep working with).
- `.aitask-scripts/lib/task_utils.sh` `_ait_detect_data_worktree` (:77),
  `.aitask-scripts/lib/artifact_manifest.sh` `artifact_manifest_dir`.
- `setup_scratchpad_gitignore` in `aitask_setup.sh` (:3101) for the setup helper.
- `aidocs/framework/aitasks_extension_points.md` ("Test the full install flow").

## Verification

- Pre-phase: `tests/test_archive_iter_characterization.py` green before and after
  the `archive_iter` refactor.
- New `tests/test_trail_discovery_cache.py` (hit/miss tables per layer,
  best-effort-then-diagnostic scan over faulty input, warmed cache + malformed
  manifest per invariant, corrupt cache files, `read_seq`, read-only, parity of
  `proven_manifest_dir` with bash `artifact_manifest_dir`).
- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED`.
- `bash tests/test_setup_git.sh`; `shellcheck .aitask-scripts/aitask_setup.sh`.
- `tests/perf/trail_discovery_bench.py` — record cold/warm timings.
- Post-phase: uncached vs cold vs warm equality on this repo, plus a scripted
  mutation fixture test comparing cached vs uncached after every step.
- `cd website && python3 check_links.py --build`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-31T19:58:41Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-31T21:28:50Z status=pass attempt=1 type=human
