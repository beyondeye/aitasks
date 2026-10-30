---
priority: medium
effort: medium
depends: [1852_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1852_5]
anchor: 1852
followup_kind: manual_verification
created_at: 2026-10-06 23:07
updated_at: 2026-10-06 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1852_5

## Verification Checklist

- [ ] On a quiet host (stop the dedicated `-L ait` tmux server: `tmux -L ait kill-server`, after saving work), from a terminal NOT inside tmux, run `bash tests/test_frozen_agents_acceptance.sh` and confirm it exits 0 (it was deferred from t1852_5's install_regression_sweep)
- [ ] In that run's output, confirm the install.sh --local-tarball step prints `TESTMAP_BINARY:skipped` (offline install: no engine fetch) and no network call is attempted

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:23:21Z.5dc94f23454958db18d61f5d from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:21Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:16:00Z.fc778d7a3f1bb5446d5a44e0 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:16:00Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.
