---
priority: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [codeagent, models]
assigned_to: dario-e@beyond-eye.com
anchor: 1916
created_at: 2026-10-09 16:11
updated_at: 2026-10-09 16:12
---

## Origin

Follow-up of t1937. Until t1937 (commit 579dd60bc), `tests/test_verified_update_flags.sh`
ran `aitask_verified_update.sh` against the real repository, so every run recorded a
`test_414_flags` verified score and pushed it to `origin/aitask-data`.

## Work

Remove the junk skill key from every row of `aitasks/metadata/models_claudecode.json`:
`.verified.test_414_flags` and `.verifiedstats.test_414_flags`. As of 2026-10-09 it sits
on two rows — `opus4_6` (87 runs on origin, 85 locally) and `opus4_7_1m` (3 runs).
Re-query before editing; also check the other `models_*.json` registries
(`jq '[.models[] | select(.verified.test_414_flags) | .name]'`).

## Preconditions / constraints

- Reconcile the data branch first (`ait syncer`). At t1937 time it had diverged
  (local unpushed + remote unpulled, rebase blocked by unstaged changes); deleting the
  key on one side would conflict with the other side's edits to the same rows.
- The registry has concurrent writers coordinated by `lib/registry_cas.sh` (t1928).
  Do the rewrite through that compare-and-swap path rather than a bare `jq > file`,
  so a concurrent usage/verified update is not lost.
- Commit via `./ait git` / `aitask_task_commit.sh`, naming only the registry path.

## Verification

- The `jq` query above returns `[]` for every registry, locally and on `origin/aitask-data`.
- Other rows' `verified` / `verifiedstats` / `usagestats` are byte-identical to before.
