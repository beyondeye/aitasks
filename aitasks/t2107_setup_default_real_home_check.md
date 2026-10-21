---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [testmap, install, ait_setup, bash_scripts]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-10-21 15:10
updated_at: 2026-10-21 15:10
---

## Origin

Risk-mitigation ("after") follow-up for t1939, created at Step 8d after implementation landed.

## Risk addressed

code-health — default migration of real shared per-user roots

- The default now renames the shared per-user root, which holds the venv and Python that every project on the host uses, on the next `ait setup` for every user. A verb defect would hit real homes without anyone opting in. This is bounded by the verb's preflight, inode checks and rollback, by its passes on real Linux and macOS homes (t1931/t2086), and by setup's handling of each exit class. · severity: medium
- The I matrix runs the installed `main()` under production options, but the steps that do not touch the home are stubbed. An interaction with a real heavy step, for example a networked venv build changing the tenant shapes, is caught only by the gated full-setup tests and the real-home check. · severity: low

## Goal

Verify the setup-driven default (shipped in t1939, commit 2f893f39b) on real hosts. Every t1939 test used a scratch HOME, and the earlier real-host checks (t1931/t2086) exercised only the explicit verb.

- [ ] Linux: on a real home with a populated, **unmigrated** `~/.aitask` (another machine or a fresh user account; back it up first with `cp -a ~/.aitask ~/.aitask.bak`), run the released `ait setup`. Confirm it prints `HOME_MIGRATED:<n>`, `~/.aitask` is now a symlink to `~/.aitasks`, setup ends with "Setup complete!", and the summary has no `HOME_LEGACY:` hint.
- [ ] Linux: after that, `ait board` starts on the PyPy venv (when installed) and `ait monitor` starts.
- [ ] Linux: re-run `ait setup`. It prints no `HOME_MIGRATED`, no hint, and changes nothing under `~/.aitasks`.
- [ ] macOS: repeat the three checks above on a real unmigrated home.
- [ ] `ait setup --no-home-migration` on an unmigrated home leaves `~/.aitask` a directory and prints the hint after `AITASKS_HOME:`.
- [ ] From a terminal **outside tmux**, run `bash tests/test_frozen_agents_acceptance.sh` (it refuses inside tmux; t1939 only syntax-checked its edit).
- [ ] With network available, run `AIT_RUN_INTEGRATION_TESTS=1 bash tests/test_setup_python_install.sh` and `AIT_ACCEPTANCE_FULL_SETUP=1 bash tests/test_frozen_agents_acceptance.sh` (outside tmux). These are full real setups that now migrate their scratch home.
