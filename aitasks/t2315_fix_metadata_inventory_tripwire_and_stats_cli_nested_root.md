---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [verifiedstats, models, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-11-16 11:39
updated_at: 2026-11-16 11:39
---

## Origin

Spawned from t1912_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/sitrep_crash.py:1 — t2307's commit 87ecc9799 left a metadata-targeting write unclassified in tests/test_metadata_writer_inventory.py (NewWriterTripwire fails at HEAD)`
- `.aitask-scripts/aitask_model_stats.py:211 — export/show default --root to the raw cwd and read the legacy registry under it (load_agent_stats does not resolve the toplevel), so run from a nested directory they show branch-only counters; the writers and readers pass the repo root, so only direct CLI use is affected`

## Diagnostic context

- `tests/test_metadata_writer_inventory.py::NewWriterTripwire::test_no_unclassified_file_writes_metadata`
  reports `['.aitask-scripts/lib/sitrep_crash.py']` as an unclassified file that
  writes under `aitasks/metadata`. It fails identically at HEAD `5e33fad89`
  without any t1912_4 change, so it is not a regression of the stats cutover.
  It appeared once t2307 (`bug: Validate task status in sitrep refresh TaskIndex
  lookups`, 87ecc9799) committed its `sitrep_crash.py` change. Classify that
  write: add it to `WIRED` / `KNOWN_UNCOMMITTED` in the inventory with its
  reason, or move it out of `aitasks/metadata` if it should not be there. Check
  t2307's archived plan first; it may already say which.
- t1912_4 fixed the same nested-cwd bug inside `effective_total`, the
  post-write total the writers print: the legacy registry is now read under
  `ors.toplevel(project_root)`. The display verbs `export` / `show` (and any
  direct `load_agent_stats(<nested dir>)` call) still use the raw path:
  `metadata_dir()` builds `<root>/<TASK_DIR>/metadata` from it, so from
  `<repo>/website` they find no legacy counters and show branch-only values.
  Readers are unaffected today because they all pass the repository root.

## Suggested fix

- Inventory: classify the `sitrep_crash.py` write. Coordinate with t2307's
  owner (send a note) rather than guessing its intent.
- Stats CLI: resolve a defaulted `--root` to the git toplevel once in `main()`
  (or inside `legacy_models` / `metadata_dir` via the cached `_layout`). Add a
  nested-cwd test for `export` / `show` like t1912_4's
  `test_nested_cwd_without_root_reads_the_repository_registry`.
