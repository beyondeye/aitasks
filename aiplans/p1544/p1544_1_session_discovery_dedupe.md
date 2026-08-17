---
Task: t1544_1_session_discovery_dedupe.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_2_*.md, aitasks/t1544/t1544_3_*.md, aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_6_*.md, aitasks/t1544/t1544_7_*.md, aitasks/t1544/t1544_8_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_1 — Session-discovery dedupe

## Goal

Make session discovery return **one record per repository**, so
`merge_stats_data` can no longer be handed the same `StatsData` object twice.
This is a pre-existing bug affecting every existing stats counter; t1544_3's
"a multi-project run does not double-count" test is untestable without it.

## Pre-phase (risk mitigations)

Runs **before** any edit to `_assemble_aitasks_sessions`.

1. `[characterize_session_discovery]` Add a characterization test pinning the
   **current** output of `_assemble_aitasks_sessions` for the non-duplicate
   cases:
   - a single live root;
   - a live entry plus a registered entry with **distinct** names;
   - a `STALE` registry row — pin what the assembler does with it *and* what
     `discover_stats_sessions` does (the assembler keeps it, the stats wrapper
     drops it; they are different layers and both must stay put);
   - the `found.sort(key=lambda s: s.session)` ordering.

   Assert on the returned list: count, `project_name`, `project_root`,
   `is_live`, `is_stale`, and order.

   **This test must pass unchanged after step 3.** Only a *new* duplicate-input
   case may be added to the file. Run it and see it pass before editing
   anything — a characterization test written after the change characterizes the
   change, not the baseline.

## Implementation steps

1. **Locate the two seams.** In `.aitask-scripts/lib/agent_launch_utils.py`,
   `_assemble_aitasks_sessions` builds `found` from `live_roots` with no dedupe,
   then appends registered rows skipped only when `name in live_names`. In
   `.aitask-scripts/stats/stats_app.py`, `discover_stats_sessions` filters
   `is_stale` and nothing else, and `_stats_for` caches on `sess.key`
   (`realpath(project_root)`).

2. **Decide where the dedupe lives, and write the decision down.** Prefer the
   **assembler**: the doubling is not stats-specific, and every TUI consumes the
   same helper. The alternative (dedupe only in `discover_stats_sessions`) keeps
   the blast radius to stats but leaves the bug live everywhere else. Record the
   choice and its blast radius in the Final Implementation Notes — t1544_3 needs
   to know which layer guarantees uniqueness.

3. **Make the registered-vs-live skip path-based.** Replace the `project_name`
   comparison with a realpath comparison against the live roots. Reuse the idiom
   already in this module — `_build_registry_group_lookup` keys on
   `os.path.realpath(...)` inside a `try/except OSError` fallback to `str(path)`.
   Do not invent a second normalization.

4. **Dedupe live-vs-live on the same key**, preferring the `is_live=True` entry
   when both a live and a registered record resolve to one path. Keep first-seen
   order among the survivors so step 1's ordering assertion still holds after
   the final `sort`.

5. **Add the duplicate-input tests:**
   - two live roots at one path → 1 entry;
   - a registry row whose `name` differs from the directory basename but whose
     path matches a live root → 1 entry, and it is the **live** one
     (`is_live is True`);
   - the surviving entry's `key` is the realpath.

6. **Re-run the pre-phase test** and confirm it passes **unchanged**.

7. Note in the Final Implementation Notes that `disambiguate_labels`'s
   "guaranteed-unique" contract was previously violated by these duplicates
   (primary, secondary and fallback were all identical) and is restored by
   removing the duplicate at source — no change to that function is needed.

## Post-phase (risk mitigations)

1. `[tui_discovery_smoke_after_dedupe]` Capture the session list from
   `ait board`, `ait monitor`, `ait minimonitor` and the `j` switcher **before**
   the change; after it lands, capture them again and confirm each is identical
   — same count, same names, same order. Record both lists in the Final
   Implementation Notes. The unit tests cannot reach the live discovery path in
   four other TUIs; only this can. The same four checks are already seeded on
   t1544_7's checklist.

## Files

- `.aitask-scripts/lib/agent_launch_utils.py` — `_assemble_aitasks_sessions`
- `.aitask-scripts/stats/stats_app.py` — `discover_stats_sessions`
- `tests/` — characterization test + duplicate-input cases (follow the fixture
  style of `tests/test_stats_include_registered.py` or the nearest existing
  session-discovery module rather than inventing one)

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` passes.
- The characterization test passes **unchanged** across the edit — this is the
  primary signal.
- Two live roots at one path yield exactly one session record.
- A registry-name-vs-basename mismatch at a live path yields exactly one record,
  and it is the live one.
- `ait board`, `ait monitor`, `ait minimonitor` and the `j` switcher each list
  the same sessions as before the change.
- The stats TUI's aggregate view does not double any counter for a repo that is
  discoverable twice.

## Notes for sibling tasks

Record which layer now guarantees session uniqueness (assembler vs
`discover_stats_sessions`) — t1544_3's merge test depends on it.
