---
Task: t2086_real_host_migration_check_carryover.md
Base branch: main
Output branch: main
---

# t2086 — macOS carry-over of t1931's `ait engine home --migrate` real-host checks: auto-execution record

Strategy: autonomous. Host: macOS (Darwin 24.6.0, APFS, `~/.aitask` and `~/.aitasks`
on the same volume `/dev/disk3s5`). Code under test: this checkout at `main`
`f8f63eadc`; the setup re-run used released v0.38.0, mirroring t1931. The user
explicitly approved migrating the real `~/.aitask` after a backup. Both items passed.

## Execution Log

### Item 1
- Item text: macOS: run `bash tests/test_aitasks_home.sh` and confirm ALL TESTS PASSED (BSD `stat -f`, `mv -n`, `sort -z`, `ln -s`, and `find -print0` paths)
- Approach: CLI invocation
- Action run: `bash tests/test_aitasks_home.sh`
- Output (trimmed): `Results: 236 passed, 0 failed, 236 total` / `ALL TESTS PASSED`, exit 0.
  `SKIP: H8 cross-device (no second writable filesystem at /dev/shm) — not counted`,
  plus two `SKIP (not landed)` lines for scripts absent from this tree.
- Verdict: pass

### Item 2
- Item text: macOS: repeat the real-host migration and the TUI checks above
- Approach: CLI on the real home + TUI interaction (private tmux socket `-L av2086`) + CLI in a scratch project
- Action run:
  - Pre-state: `ait engine home` → `HOME_LEGACY:~/.aitask|bin,pypy_venv,python,venv`,
    `HOME_SYMLINK:none`, `HOME_NEXT:migrate|4|…` (~/.aitasks held only `engine/`).
  - `cp -a ~/.aitask ~/.aitask.bak` (`diff -rq` clean), then `./ait engine home --migrate`.
  - `~/.aitask/venv/bin/python -c 'print(1)'`, `~/.aitask/bin/python3 -c 'print(1)'`.
  - `./ait board` and `./ait monitor` in windows of a detached session on the private socket
    (`TMUX` unset); `ps` on the pane children; `lsof` on the monitor pid.
  - `install.sh --dir <scratch>/proj --version 0.38.0` into a fresh `git init` project and
    `./ait setup </dev/null` there.
  - Rerun `./ait engine home --migrate` with an md5 fingerprint of
    `find ~/.aitasks/ -exec stat -f '%N %i %m'` before and after.
- Output (trimmed):
  - `HOME_MIGRATED:4`, exit 0; `~/.aitask -> /Users/daelyasy/.aitasks`. The live `-L ait`
    session (this agent's own pane) kept running throughout (same-volume rename).
  - Both interpreters print `1`; `~/.aitask/pypy_venv/bin/python` reports `pypy`.
  - Board rendered its columns; process `~/.aitask/pypy_venv/bin/python …/aitask_board.py`.
    Monitor rendered "tmux Monitor — 1 session · 2 panes"; `ps` shows the Homebrew
    framework `Python.app` because the venv's `python3.13` symlinks to Homebrew python
    (macOS framework builds re-exec), but its loaded `site-packages` resolve under
    `/Users/daelyasy/.aitasks/venv/lib/python3.13/`, so it is the venv.
  - Setup exit 0; 0 `HOME_LEGACY` lines; "Python virtual environment already exists at
    /Users/daelyasy/.aitask/venv", "PyPy venv ready", summary
    `AITASKS_HOME:/Users/daelyasy/.aitasks`. textual 8.2.7 imports in both venvs.
    `~/.config/aitasks/projects.yaml` md5 and the `~/.aitasks` entry list unchanged.
  - Rerun → `HOME_SKIPPED:already-migrated`, exit 0, fingerprint `UNCHANGED`;
    `ait engine home` → `HOME_SYMLINK:/Users/daelyasy/.aitasks`, `HOME_NEXT:none|already-migrated`.
- Deviation: as in t1931, setup ran in a scratch project rather than this checkout
  (the default flow merges agent settings, edits `.gitignore` and commits framework
  files). `ait upgrade` was not run separately; the item allows `ait setup` reinstall.
  The cross-device path remains unexercised on macOS too (single volume).
- Verdict: pass

## Cleanup

- Removed: the scratch project and logs under the session scratchpad
  (`auto_verify_2086_2/`); the private tmux server `av2086` was killed.
- Kept on purpose: `~/.aitask.bak` (the user's pre-migration backup; delete it once
  satisfied the migrated home works).
