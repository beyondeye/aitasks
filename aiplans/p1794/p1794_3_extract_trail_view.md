---
Task: t1794_3_extract_trail_view.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md, t1794_2_*.md, t1794_4_*.md … t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_3 — Extract the pure trail code into `board_trail_view.py`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C2, C3, C7 PINNED; Decisions "Stand-alone scope").

## Move set (verbatim, anchors at e2f12c499)

`:1162–1360` (constants, `TrailEntryView`, `TrailWaveLane`,
`load_local_project_name`, `trail_ref_to_local_id`, `canonical_trail_ref`,
`build_trail_lanes`, `trail_drift_by_ref`, `trail_summary_text`,
`run_trail_drift`), `_GhostTaskStub :3761–3776`, `_trail_badge_text`/
`_trail_drift_text :3917–3945`, `TrailTaskCard :3948–4012`,
`TrailGhostCard :4014–4063`, `TrailColumn :4066–4106`,
`_trail_stored_freshness :4286–4306`, `TrailSelectItem :4309–4338`,
`TrailSelectScreen :4341–4373`, `TrailDetailScreen :4376–4733`,
`TrailSummaryScreen :4736–4788`.

## Invariants

- `load_local_project_name(tasks_dir: Path, config_path: Path | None = None)`
  — the module contains no `TASKS_DIR` name (C2); `_get_local_project`
  (`:11733–11737`) passes the board's `TASKS_DIR`.
- `TRAIL_CSS` exported; `KanbanApp.CSS` interpolates it in place of the trail
  rules (`.trail-drift :8582`, `#trail_summary :8620`, `#board_container
  :8606`, `TaskCard.markable-card:* :8576,8580`; re-derive by grep). The three
  modals carry `DEFAULT_CSS` (`tui_conventions.md:254–270`).
- Imports: `board_widgets`, `trail_discovery`, `topic_semantics`,
  `cross_repo_notation`, `yaml`, `subprocess`; no `aitask_board`.
- `aitask_board.py`: `import board_trail_view` + flat re-import of every name.
- C3: classify each `patch.object(ab|self.ab, "<name>")` in
  `tests/test_board_bytrail_view.py` as App-half caller (still valid) or
  `board_trail_view`-internal caller (repoint to `ab.board_trail_view.<name>`
  with a recorded mutant).

## Tests added

- A headless sibling of `TrailModelTests` (`:204–430`) importing
  `board_trail_view` directly and asserting `"aitask_board" not in sys.modules`.
- `TRAIL_CSS in KanbanApp.CSS` containment test.

## Order

Rebase check (t1647_5 is the known By-Trail neighbour) → module → CSS →
import pair → C3 classification + mutants → new tests → suite.

## Verification

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `tests/test_board_bytrail_view.py` green with no assertion changed in
  intent; child-1 guards and the characterization golden unchanged.
- Manual: `ait board` → `z` → `s` / `enter` / `v` / `d` work.

## Post-implementation

Task-workflow Step 9: path-scoped commit, gates, archive `t1794_3`.
