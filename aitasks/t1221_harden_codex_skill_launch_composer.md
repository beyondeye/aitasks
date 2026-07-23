---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [backend]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-23 14:24
updated_at: 2026-07-23 14:24
---

## Origin

Spawned from t1162_2 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_codeagent.sh:500-521` — the codex skill-launch composer's inner `case "$operation"` silently yields an empty prompt for any operation without an explicit arm: the outer `*` arm catches every non-batch operation, `local prompt` starts empty, and `CMD=("$binary" "$model_flag" "$cli_id" "$prompt")` composes a broken command with no error. A future operation added to `SUPPORTED_OPERATIONS` but not to the inner case fails silently at launch time.
- The same argv-flattening whitespace hazard exists for every skill-launch operation (`pick`, `explain`, `qa`, `shadow`, `learn`): slash commands are composed by joining args with spaces (`${args[*]}` for claudecode/opencode, `build_skill_prompt`'s `"$*"` for codex), so an argument containing whitespace splits undetectably. Only `work-report` currently guards against it (fail-closed rejection added in t1162_2).

## Diagnostic context

Found while registering the `work-report` operation (t1162_2): the plan-verification pass showed that omitting the inner-case arm would compose `codex -m <model> ""` with no diagnostic. A review concern then established that `--columns "my col"` (one shell argument) arrives at the skill as two text tokens; t1162_2 added a work-report-only whitespace guard in `build_invoke_command`, pinned by dry-run tests in `tests/test_codeagent_work_report.sh`.

## Suggested fix

Add a `*` arm to the codex inner case that dies with "operation not wired into the codex composer: <op>", and consider generalizing the t1162_2 whitespace guard to all skill-launch operations (behavior change for existing ops — verify no current caller passes whitespace-bearing args first).
