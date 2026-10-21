---
Task: t1931_real_host_migration_check.md
Base branch: main
Output branch: main
---

# t1931 — Real-host verification of `ait engine home --migrate` (t1852_6): auto-execution record

Strategy: autonomous. Host: Linux (Omarchy, btrfs `/home`, single filesystem).
Code under test: this checkout at `main` `99bbbda83`, with an unrelated dirty
working tree from concurrent sessions; the setup re-run used released v0.38.0
(which contains t1852_6's f26d94777). The user explicitly approved migrating the
real `~/.aitask` after a backup. Five items passed; the two macOS items were
deferred because they need a macOS host.

The 7 checklist items were seeded from the task's `## Goal` checkboxes, which the
parser does not read (no `## Verification Checklist` section and no plan existed).

## Execution Log

### Item 1
- Item text: Linux: `ait engine home` lists every tenant and says `HOME_NEXT:migrate|<n>|…`
- Approach: CLI invocation (read-only)
- Action run: `./ait engine home`
- Output (trimmed): `HOME_ROOT:/home/ddt/.aitasks` /
  `HOME_LEGACY:/home/ddt/.aitask|bin,dev_tier,pypy_venv,python,update_check,uv,venv` /
  `HOME_SYMLINK:none` / `HOME_NEXT:migrate|7|bin,dev_tier,pypy_venv,python,update_check,uv,venv`
- Verdict: pass (all 7 tenants of the populated home; `~/.aitasks` held only `engine/`)

### Item 2
- Item text: Linux: back up, run `ait engine home --migrate`, confirm `HOME_MIGRATED:<n>` and the symlink
- Approach: CLI invocation on the real home (user-approved)
- Pre-state: ~20 live TUIs (monitor, minimonitor, trails, frozenagent across three
  projects) were running from `~/.aitask/venv/bin/python`; 186M home, 1.2T free.
- Action run: `cp -a ~/.aitask ~/.aitask.bak && diff -rq --no-dereference ~/.aitask ~/.aitask.bak`,
  then `./ait engine home --migrate`
- Output (trimmed): `BACKUP_OK`; `HOME_MIGRATED:7`, "Moved 7 entries into
  /home/ddt/.aitasks; /home/ddt/.aitask now links there.", exit 0;
  `~/.aitask -> /home/ddt/.aitasks`; `~/.aitasks` now holds the 7 tenants + `engine/`.
  Sampled live TUI pids (22742, 1902046, 103916, 25775) all still alive afterwards.
- Verdict: pass

### Item 3
- Item text: Linux: board on PyPy, monitor starts, `ait setup` re-runs cleanly (no `HOME_LEGACY:`), reinstall works through the symlink
- Approach: TUI interaction (private tmux socket `-L t1931verify`) + CLI in a scratch project
- Action run: `./ait board` and `./ait monitor` in windows of a detached session on
  the private socket; `pstree` + `/proc/<pid>/exe`; then
  `install.sh --dir <scratch>/proj --version 0.38.0` into a fresh `git init` project
  and `./ait setup </dev/null` there.
- Output (trimmed): board rendered its columns; its process is
  `/home/ddt/.aitask/pypy_venv/bin/python …/aitask_board.py` with exe
  `…/uv/python/pypy-3.11.15-linux-x86_64-gnu/bin/pypy3.11`. Monitor rendered
  "tmux Monitor — 3 sessions · 27 panes" on `/home/ddt/.aitask/venv/bin/python`.
  Setup exit 0; 0 `HOME_LEGACY` lines; "Python virtual environment already exists at
  /home/ddt/.aitask/venv", "PyPy venv ready", chat and dev tiers re-installed into
  the venv; summary `AITASKS_HOME:/home/ddt/.aitasks`. Afterwards `ait engine home`
  still `HOME_NEXT:none|already-migrated`, and textual imports in both venvs.
- Deviation: setup ran in a scratch project, not this checkout. The default flow
  merges agent settings, edits `.gitignore` and commits framework files, and this
  tree had other sessions' uncommitted edits (e.g. `seed/project_config.yaml`). The
  item's subject — the user-global, now-symlinked home — is the same either way.
  `ait upgrade` was not run separately; the item allows `ait setup` reinstall instead.
- Verdict: pass

### Item 4
- Item text: Linux: `~/.aitask/venv/bin/python -c 'print(1)'` and `~/.aitask/bin/python3 -c 'print(1)'` both run
- Approach: CLI invocation
- Action run: both commands, plus `~/.aitask/pypy_venv/bin/python -c 'import sys; …'`
- Output (trimmed): `1` exit 0; `1` exit 0; `pypy /home/ddt/.aitask/pypy_venv`
- Verdict: pass

### Item 5
- Item text: macOS: `bash tests/test_aitasks_home.sh` passes
- Approach: not automatable here
- Verdict: defer (needs a macOS host)

### Item 6
- Item text: macOS: repeat the real-host migration and the TUI checks
- Approach: not automatable here
- Verdict: defer (needs a macOS host)

### Item 7
- Item text: Rerun `ait engine home --migrate`: `HOME_SKIPPED:already-migrated`, nothing changes
- Approach: CLI invocation with a before/after fingerprint
- Action run: md5 of `find ~/.aitasks -printf '%p %i %T@\n' | sort` before and after
  `./ait engine home --migrate`
- Output (trimmed): `HOME_SKIPPED:already-migrated`, exit 0; fingerprint `UNCHANGED`
- Verdict: pass

## Cleanup

- Removed: scratch project and logs under the session scratchpad
  (`auto_verify_1931_3/`); the private tmux server `t1931verify` was killed.
- The scratch install registered nothing in `~/.config/aitasks/` or `~/.aitasks/`.
- Kept on purpose: `~/.aitask.bak` (the user's pre-migration backup; delete it once
  satisfied). The migration itself is the intended end state and was not reverted.
