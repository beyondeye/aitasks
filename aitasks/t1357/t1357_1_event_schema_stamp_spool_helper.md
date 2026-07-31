---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, reporting]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:56
updated_at: 2026-07-31 10:56
---

## Context

First child of t1357 (per-step execution stats for task-workflow). This child
builds the foundation everything else depends on: the event schema, the
git-ignored runtime spool, and the fail-safe stamp/capture helper. It is the
riskiest-spike-first child — it proves the schema + concurrency contract
before any helper or skill is instrumented.

Parent plan: `aiplans/p1357_task_workflow_step_stats_and_drift.md` (read the
Architecture section in full — the schema and layouts there are PINNED
contracts for all siblings).

## Deliverables

1. **`.aitask-scripts/lib/stats_step_lib.sh`** — shared functions: JSON line
   emission (schema `v:1` — fields `v, ts (UTC ISO seconds), task, run, step,
   sub, ev(begin|end|point), skill, profile, agent, effort, src, extra`),
   manifest read/write, spool append (single `>>` write of one full line),
   run-id minting (`r<epoch>_<pid>`), step-vocabulary constants
   (`pick_select, claim, env_setup, planning[plan_mode|risk_evaluation|externalize],
   implement, review[iteration], commit, gates, merge, archive, feedback, run`).
2. **`.aitask-scripts/aitask_stats_step.sh`** — verbs:
   - `begin-run <task_id> --skill <s> [--profile <p>]` — mint run, write
     `.aitask-stats/runs/t<id>/manifest.yaml` (run_id, task, skill, profile,
     agent=unknown, effort=unknown, started_at, pid, pid_starttime), stamp
     `run/begin`. Reuse a live manifest (same pid alive); sweep a dead one
     into an orphan capture first (outcome=orphaned).
   - `stamp <task_id> <step> <begin|end|point> [--sub <s>] [k=v ...]` —
     append to spool; auto `begin-run` with skill=unknown if no manifest.
   - `set-dim <task_id> [--agent <a/m>] [--effort <e>]` — update manifest.
   - `capture <task_id> [--outcome done|aborted|deferred] [--sweep-orphans]` —
     stamp `run/end`, back-fill manifest dims onto every spool line (the
     manifest is the single source for dims — individual stamps are not
     trusted), write
     `aitasks/metadata/stats/events/<YYYY-MM>/t<id>_<run_id>.jsonl` via the
     data-branch path, `./ait git add/commit` path-scoped best-effort (model:
     `aitask_gate_record.sh`), delete the spool dir.
   - **Fail-safe contract:** every verb runs its body under a trap that
     reports to stderr and exits 0. A stats failure must NEVER break a
     workflow helper. Verbs print a single structured stdout line
     (`STAMPED:` / `CAPTURED:<path>` / `NOOP:<reason>` / `STATS_ERROR:<reason>`
     — rich returns, not bare booleans).
3. **Ignore entries:** add `.aitask-stats/` to `.gitignore` AND to the
   gitignore-population block in `aitask_setup.sh` (find the `.aitask-gates`
   entry as the pattern; read `aidocs/framework/aitasks_extension_points.md`
   before editing setup).
4. **`ait` dispatcher entry** `ait stats-step ...` → `aitask_stats_step.sh`
   (see `ait` case table around the `stats` entry).

## Reference files for patterns

- `.aitask-scripts/aitask_gate_record.sh` — best-effort path-scoped commit +
  always-exit-0 pattern.
- `.aitask-scripts/aitask_lock.sh` lines ~204-213 — pid + pid_starttime
  liveness anchor (reuse the same starttime comparison for orphan detection).
- `aidocs/framework/shell_conventions.md` — shebang, `set -euo pipefail`,
  `sed_inplace`, error helpers (MANDATORY read before writing).
- `tests/test_claim_id.sh` — self-contained bash test structure with
  `assert_eq`/`assert_contains`.

## Verification

- `bash tests/test_stats_step.sh` (new): schema shape of emitted lines
  (parse with `python3 -c 'import json,sys; ...'`), begin/stamp/set-dim/
  capture happy path against a scratch git repo with a fake data-branch
  layout, dim back-fill correctness, orphan sweep (fake dead pid).
- **Negative control (fail-safe):** make the spool dir unwritable → every
  verb still exits 0 and prints `STATS_ERROR:`; prove the test can fail by
  temporarily breaking the trap (harness-can-fail check).
- `shellcheck .aitask-scripts/aitask_stats_step.sh .aitask-scripts/lib/stats_step_lib.sh`
