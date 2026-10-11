---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent, models]
gates: [risk_evaluated]
anchor: 1884
followup_kind: upstream_defect
created_at: 2026-09-25 16:01
updated_at: 2026-09-25 16:01
---

## Origin

Spawned from t1884 during Step 8b review.

## Upstream defect

- `tests/test_verified_update_flags.sh:27-31` — runs `aitask_verified_update.sh` against the real repository (`cd "$PROJECT_DIR"`), committing and pushing `test_414_flags` scores into the shared `aitask-data` branch on every run. It also fails with exit 3 under `set -e` whenever the data worktree has unstaged changes (`UPDATED_REMOTE_ONLY`).
- `.aitask-scripts/aitask_opencode_models.sh:63-72` — `convert_to_model_name` is non-injective (`a_b/c` and `a/b-c` both derive `a_b_c`). `merge_with_existing` and the stats scripts select rows by name, so two such models would share a name.
- `.aitask-scripts/lib/agent_string.sh:115` — `get_cli_model_id`'s unavailable-model error tells users to run `ait opencode-models`, which the `ait` dispatcher does not route (`ait: unknown command 'opencode-models'`). The discovery script is reached through `/aitask-refresh-code-models` (`bash .aitask-scripts/aitask_opencode_models.sh`). The script's own header also documents `ait opencode-models` usage.

## Diagnostic context

While verifying t1884, running `bash tests/test_verified_update_flags.sh` pushed two `ait: Update verified score for claudecode/opus4_6 test_414_flags` commits to `origin/aitask-data`. The `opus4_6` row already held `test_414_flags` stats from 83 earlier runs, so every run of this test has been polluting the shared registry. It exited 3 because an uncommitted registry edit blocked the local fast-forward. `tests/test_verified_update.sh` and `tests/test_usage_update.sh` already show the safe pattern: an isolated `setup_repo` fixture that copies the scripts into a temporary git repo.

The other two defects were found while enumerating registry writers for t1884's reserved `unregistered_` namespace.

## Suggested fix

- Move `test_verified_update_flags.sh` onto the isolated fixture pattern (copy the scripts plus `aitask_resolve_detected_agent.sh` into a temp repo), so it never touches the real repo or its remote.
- Make `convert_to_model_name` collision-safe: detect duplicate derived names across the discovered and existing sets and fail closed before writing, the same way t1884's reserved-name guard does.
- Point the unavailable-model hint at `/aitask-refresh-code-models`, or route `ait opencode-models` in the dispatcher.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1942** id=2026-10-11T08:39:27Z.91bd93922beca96d97568943 from=t1942 from_verified=yes at=2026-10-11T08:39:27Z base=33b54e172eca2cb90762f95341e2eee203e5c3f4 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1942 (registry cleanup). This task's defect looks already fixed:
> | commit 579dd60bc "bug: Isolate verified-update flags test from the real model
> | registry (t1937)" moved tests/test_verified_update_flags.sh onto an isolated
> | fixture (setup_local_metadata_repo in tests/lib/metadata_update_fixture.sh), so
> | it no longer writes test_414_flags into the real registry or pushes to
> | aitask-data. t1942 then purged the accumulated test_414_flags keys from
> | models_claudecode.json (opus4_6, opus4_7_1m) locally and on origin/aitask-data.
> | Not verified here: whether t1937 covers every point in this task's body (e.g.
> | the exit-3 under a dirty data worktree). Re-check before archiving or folding.
