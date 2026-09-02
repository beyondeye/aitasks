---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, task_metadata, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-02 09:02
updated_at: 2026-09-02 09:02
---

## Origin

Risk-mitigation ("after") follow-up for t1599_3, created at Step 8d after implementation landed.

## Risk addressed

`addresses: goal-achievement — ownerless metadata files have no session that
commits them, so an ownerless dirty file becomes a permanent rebase deferral`

From p1599_3's `## Risk`:

> Ownerless files (`aitasks/metadata/stats_config.json`, `board_config.json`)
> have **no session that ever commits them** — verified: their writers only
> write. The plan's premise that they "stay dirty until the session that changed
> them commits them" does not hold, so an ownerless dirty file becomes a
> *permanent* rebase deferral, blocking all task-data sync until a human
> intervenes — a worse outcome than the swallow it replaces · severity: high

## Goal

t1599_3 stopped `ait sync` sweeping ownerless files into a commit that names an
unrelated task. That is correct — the parent task's own evidence is
`aitasks/metadata/stats_config.json`, which has four commits in its entire
history and three of them are swallows. But it leaves a real gap: **nothing else
commits those files.**

Give every tracked `aitasks/metadata/*` write an owner that clears it. The
writers to audit:

- `.aitask-scripts/settings/settings_app.py` — writes `board_config.json` and
  the other project-layer configs. The user layer (`*.local.json`) is gitignored
  and needs nothing; only the project layer matters.
- `.aitask-scripts/board/aitask_board.py` — `METADATA_FILE` /
  `lib/board_columns.py`.
- whatever writes `aitasks/metadata/stats_config.json` (the stats surface).

Commit each write through `task_git_commit_scoped` (`lib/task_utils.sh`), the
framework's canonical scoped-commit seam, under a message that names the file
rather than a task — the same rule `aitask_pick_own.sh` already applies to the
shared contributor list `emails.txt`, and for the same reason: a shared file with
no task owner can only get honest provenance from a message that stays true
regardless of who wrote it.

Re-derive the writer list before starting; do not trust this one.

## Verification

- edit a project-layer config through `ait settings`, then assert the file is
  committed by that action and the worktree is clean afterwards
- assert `ait sync` no longer reports it as ownerless (the report text is in
  `aitask_sync.sh`'s `_protect "ownerless"` branch)
- negative control: the assertion must fail against today's write-without-commit
