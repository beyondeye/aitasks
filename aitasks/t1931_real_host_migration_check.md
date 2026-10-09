---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [testmap, install, ait_setup, bash_scripts]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-10-09 15:29
updated_at: 2026-10-09 15:29
---

## Origin
Risk-mitigation ("after") follow-up for t1852_6, created at Step 8d after implementation landed.

## Risk addressed
real-home half-migration risk (code-health) and untested BSD/macOS behaviour (goal-achievement)

- Code-health: The new verb renames entries inside the user's real `~/.aitask`, the directory holding the venv and Python every `ait` command runs on. A defect in the move/verify/rollback sequence could leave a half-migrated home. Bounded by: an explicit verb only, a full preflight (resolved-path aliasing included) before any `mkdir` or move, per-move inode verification, state-derived rollback, INT/TERM/HUP recovery tracked by phase, explicit `HOME_FAILED` / `HOME_STRANDED` output with manual restore steps, and every test on a scratch HOME. SIGKILL and power loss mid-move still leave a split home, which a later run refuses as `destination-exists` without repairing it · severity: medium
- Goal-achievement: BSD/macOS behaviour (`stat -f`, `mv -n`, `ln -s` onto a recreated directory) is coded for but only exercised on Linux here, and the cross-device case skips on a single-filesystem host · severity: low

## Goal
Verify `ait engine home --migrate` (shipped in t1852_6, commit f26d94777) on real hosts, where every test so far used a scratch HOME.

- [ ] Linux: on a real host with a populated `~/.aitask` (venv, pypy_venv, python, bin, uv, dev_tier, update_check), run `ait engine home` and check the report lists every tenant and says `HOME_NEXT:migrate|<n>|…`.
- [ ] Linux: back up `~/.aitask` (for example `cp -a ~/.aitask ~/.aitask.bak`), run `ait engine home --migrate`, and confirm `HOME_MIGRATED:<n>`, with `~/.aitask` now a symlink to `~/.aitasks`.
- [ ] Linux: after migrating, `ait board` starts on the PyPy venv, `ait monitor` starts, `ait setup` re-runs cleanly (no `HOME_LEGACY:` hint), and `ait upgrade` (or `ait setup` reinstall) works through the symlink.
- [ ] Linux: `~/.aitask/venv/bin/python -c 'print(1)'` and `~/.aitask/bin/python3 -c 'print(1)'` both run.
- [ ] macOS: run `bash tests/test_aitasks_home.sh` and confirm ALL TESTS PASSED (BSD `stat -f`, `mv -n`, `sort -z`, `ln -s`, and `find -print0` paths).
- [ ] macOS: repeat the real-host migration and the TUI checks above.
- [ ] Rerun `ait engine home --migrate`: it reports `HOME_SKIPPED:already-migrated` and changes nothing.
