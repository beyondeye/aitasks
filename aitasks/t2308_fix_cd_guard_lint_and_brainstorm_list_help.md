---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [brainstorm, ait_dispatcher]
gates: [risk_evaluated]
anchor: 1879
followup_kind: upstream_defect
created_at: 2026-11-15 22:11
updated_at: 2026-11-15 22:11
---

## Origin

Spawned from t2305 during Step 8b review.

## Upstream defect

- `tests/test_issue_update_ledger.sh:231` — `unconfined-andchain` cd-guard violation (`( cd "$REPO" && PATH="$IFX_BIN:$PATH" STUB_LOG="$TMP/par.log" "$IFX_UPDATE" "$@" \ …`) makes `tests/test_cd_guard_lint.sh` fail 1/92 on the live tree ("no cd/pushd guard violations in tests/ … expected '0', got '1'"). The file was last touched by t2277's commit cddb129c5.
- `ait:310` — `ait brainstorm list --help` routes to `aitask_brainstorm_status.sh --list --help` and prints `status`'s usage (`Usage: ait brainstorm status <task_num>`) instead of help for `list`.

## Diagnostic context

While t2305 added `--help` to the three `ait brainstorm apply-*` wrappers, its verification ran `bash tests/test_cd_guard_lint.sh` and hit the single live-tree violation above. The violation is not in t2305's diff: t2305's new test file `tests/test_brainstorm_apply_help.sh` has no `cd`.

Before t2305 updated `website/content/docs/tuis/brainstorm/reference.md` to say every subcommand accepts `--help`, it probed `./ait brainstorm <sub> --help` for all eight subcommands. Every one exited 0 with a `Usage:` line, but `list` printed `status`'s usage, because the dispatcher implements `list` as `exec aitask_brainstorm_status.sh --list "$@"`.

## Suggested fix

- cd-guard: confine the `cd` per `tests/lib/cd_guard_scan.py` / `aidocs/framework/testing_conventions.md`, e.g. an exit-guarded `cd "$REPO" || exit 1` inside the subshell, or the confined `&&`-chain form the scanner accepts. Re-run `bash tests/test_cd_guard_lint.sh` and `bash tests/test_issue_update_ledger.sh`.
- `list --help`: either have `aitask_brainstorm_status.sh` print list-specific usage when `--list` is combined with `--help`, or handle `list --help` / `list -h` in the `ait` dispatcher's brainstorm block.
