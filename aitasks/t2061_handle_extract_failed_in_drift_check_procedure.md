---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-10-19 12:51
updated_at: 2026-10-19 12:56
---

## Origin

Spawned from t2035 during Step 8b review.

## Upstream defect

- `.claude/skills/task-workflow/remote-drift-check.md:47` — the output-parsing list has no `EXTRACT_FAILED` branch, although `aitask_remote_drift_check.sh` emits it (exit 3) for an unreadable plan, an unreachable `lib/plan_paths.py` and, since t2035, an unusable Python (checked before the fetch). An agent following the procedure gets no instruction for the infra-failure token.

## Diagnostic context

t2035 moved the drift check's fetch onto `lib/bounded_run.py`. The regression sweep then showed that with a poisoned interpreter the fetch failed first and the check printed `FETCH_FAILED`, which the procedure deliberately never displays ("could not reach the remote"), so a broken install read as a flaky network. t2035 added a preflight so an unusable Python emits `EXTRACT_FAILED` (exit 3) again, which `tests/test_plan_paths_seam.sh` pins. But the procedure that consumes the helper's output (`remote-drift-check.md`, step 3) lists `LEGACY_MODE_SKIP` / `NO_REMOTE` / `UP_TO_DATE` / `FETCH_FAILED` / `LOCAL_BRANCH_MISSING` / `AHEAD:` and has no rule for `EXTRACT_FAILED` or for a non-zero exit. The fail-closed token therefore reaches an agent with no defined action.

## Suggested fix

Add an `EXTRACT_FAILED` (exit 3) branch to step 3 of `remote-drift-check.md` (the Claude Code source `.md`/`.md.j2` under `.claude/skills/task-workflow/`). It should display that the overlap scan could not run, with `ait setup` as the repair hint, and then ask the step-4 question rather than silently returning. Regenerate the affected goldens. Then suggest porting the change to the other agent trees.
