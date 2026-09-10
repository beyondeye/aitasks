---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-09-10 21:23
updated_at: 2026-09-10 21:23
---

## Origin

Spawned from t1731 during Step 8b review. t1731 converges a diverged data branch with a guarded merge when the rebase is blocked.

## Upstream defect

- `.aitask-scripts/aitask_sync.sh:1837 — do_pull_rebase runs git pull --rebase without --no-autostash, so a user's rebase.autoStash=true stashes and re-applies files the sweep deliberately left protected`
- `.aitask-scripts/aitask_sync.sh:2165 — the existing behind-only fast-forward (merge --ff-only @{u}) runs without --no-overwrite-ignore, so it silently replaces a local ignored file (userconfig.yaml, *.local.json) that an incoming commit adds; the rebase path it falls back to likely shares this (unverified)`
- `tests/lib/sync_fixture.sh:183 — run_sync inherits the developer's global git config (no GIT_CONFIG_GLOBAL isolation), so settings such as merge.autoStash / rebase.autoStash leak into every sync test and can mask or fake an autostash defect`

Line numbers are as of commit e2f12c499. Re-derive them before editing; the file moves.

## Diagnostic context

t1731's own guarded merge advances with `merge --ff-only --no-autostash --no-overwrite-ignore`. Both flags were added because plan review found that the defaults touch files the sweep has promised not to touch.

- **Ignored files.** `git merge` (including `--ff-only`) silently overwrites ignored files by default; `--overwrite-ignore` is documented as the default in `git merge -h` and the man page. The plan reviewer reproduced this in an isolated repository. t1731's mutation control confirms it end to end: with `--no-overwrite-ignore` dropped, the ignored-file race cell reported `MERGED`, the local `userconfig.yaml` bytes were replaced, and the file was committed. The pre-existing behind-only fast-forward at `:2165` uses the same command without the flag.
- **Autostash.** Archived t1658_1 and t1599_3 deliberately rejected stashing across the shared data worktree. Both assumed `rebase.autoStash` was unset rather than enforcing it off, so a user's own git config can still stash and re-apply a protected file during `pull --rebase`.
- **Test isolation.** The sync fixtures never isolate global git config. A developer with autostash configured runs every sync test under it, which can both hide this defect and invent failures.

## Suggested fix

- Pass `--no-autostash` to every `pull --rebase` / `rebase` in the sync path (`do_pull_rebase`), enforcing the stashing decision t1599_3 and t1658_1 already made.
- Pass `--no-overwrite-ignore` to the behind-only `merge --ff-only`.
- For the rebase fallback, first verify whether it overwrites ignored files. If it does, refuse when the incoming paths collide with an ignored file, reusing t1731's `_gm_names_into` / `_gm_collides`; `git rebase` has no equivalent flag.
- Isolate git config in `tests/lib/sync_fixture.sh::run_sync` (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`). Keep the per-repo `user.*` settings the fixture already writes.
- Pin each fix with a red-then-green test that sets the offending config explicitly in the fixture.

## Sequencing

This task depends on t1747_3, which is Implementing and editing `do_pull_rebase` itself.
