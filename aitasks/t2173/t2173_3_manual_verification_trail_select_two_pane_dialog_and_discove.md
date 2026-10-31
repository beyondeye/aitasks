---
priority: medium
effort: medium
depends: [t2173_2]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [2173_1, 2173_2]
anchor: 2173
followup_kind: manual_verification
created_at: 2026-10-31 20:45
updated_at: 2026-10-31 20:45
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t2173_1] `python3 tests/test_archive_iter_characterization.py` — green before and after step 1.
- [ ] [t2173_1] `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED` (use `set -o pipefail` if piping).
- [ ] [t2173_1] `bash tests/test_setup_git.sh`; `shellcheck .aitask-scripts/aitask_setup.sh`.
- [ ] [t2173_1] `python3 tests/perf/trail_discovery_bench.py` — record no-cache / cold / warm numbers and `get` spawn counts in Final Implementation Notes (warm target: tens of ms, 0 spawns).
- [ ] [t2173_1] Post-phase differential on this repo (uncached == cold == warm per handle).
- [ ] [t2173_1] Manual: `ait trails`, `s` twice — second open near-instant; edit a trail-owning task's frontmatter and `s` shows it; same in the board's By-Trail view.
- [ ] [t2173_1] `cd website && python3 check_links.py --build`.
- [ ] [t2173_2] `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED`.
- [ ] [t2173_2] Manual, both TUIs, 80×24 and a wide terminal: type to filter, ↑/↓, Enter, click, PgUp/PgDn on a long detail pane, Tab cycle (box ↔ Cancel), Ctrl+R (`ait trails` only), Esc, an error trail's detail pane.
- [ ] [t2173_2] `cd website && python3 check_links.py --build`.
