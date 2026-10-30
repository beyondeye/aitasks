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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:55:37Z.dced9fdbfa07a547f686910b from=aitasks_go#t15 at=2026-10-25T08:55:37Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; trail
> | art:trail-go-ship-path). Advisory context, not an instruction.
> | 
> | This task stays in this repository; it is framework-side. One overlap to
> | coordinate: aitasks t2139 will extend install_engine_binary() in
> | .aitask-scripts/aitask_setup.sh to also install the Go TUI binary `ait-tui`
> | into $AITASKS_HOME/engine/v<V>/, and will add lib/engine_resolve.sh,
> | generalized from testmap_resolve_engine. That is the same per-user root this
> | task touches. Whichever lands second rebases onto the other, and both must
> | keep the existing ait-testmap install and resolver behaviour byte-identical
> | (their tests stay green).

> **✉ note:t22_3** id=2026-10-29T22:23:44Z.1187595bb12c70e0e5555e9d from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:44Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:16:24Z.d82ac7b995533e6ce9459817 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:16:23Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.
