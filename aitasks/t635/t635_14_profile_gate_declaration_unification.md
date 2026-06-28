---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t635_12, t635_13]
issue_type: refactor
status: Implementing
labels: [gates, execution_profiles, task_workflow]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 18:55
updated_at: 2026-06-28 12:46
---

## Context

Phase 4 of `aidocs/gates/integration-roadmap.md`. Pseudo-gates are toggled
today by profile keys via Jinja at render time (`risk_evaluation`,
`manual_verification_followup_mode`, ...); the gate framework toggles via
per-task `gates:` frontmatter + registry at runtime. Without unification,
every converted checkpoint ends up configured in two places.

## Principle to implement (locked in roadmap Phase 4)

Profiles stop being the RUNTIME toggle for converted checkpoints. Instead,
profiles (and the registry's `default_gates`) choose which gates get
DECLARED in `gates:` at planning time; the registry defines how gates run.
Never configure the same checkpoint in two places.

## Scope

- task-workflow planning writes `gates:` into new tasks from the active
  profile / `default_gates` (framework doc integration table row for
  planning.md).
- For checkpoints already converted (build/tests t635_12, risk t635_13):
  retire the duplicated Jinja profile-gating, keeping the user-visible
  opt-in semantics (a profile that disables risk evaluation simply does not
  declare the risk gate).
- Document the declaration model in
  `.claude/skills/task-workflow/profiles.md` and the profile schema.
- Unconverted pseudo-gates (manual-verification family, 8b/8d follow-ups)
  keep their Jinja gating untouched — they migrate only if/when converted.
- Read `aidocs/framework/agent_runtime_guards_audit.md` before moving any
  runtime guard into a Jinja gate or vice versa.

## Coordination (from t635_2)

t635_2 added the first gate-related execution-profile key, `record_gates`
(opt-in bool), and registered it in `.aitask-scripts/lib/profile_editor.py`
(`PROFILE_SCHEMA` + `PROFILE_FIELD_INFO`) under a new **"Gates"**
`PROFILE_FIELD_GROUPS` entry. When this task introduces `default_gates`,
register it the same way (schema + field info + the existing "Gates" group) and
pick a clear user-facing name consistent with `record_gates`.

## Coordination (from t635_3)

t635_3 added the registry per-gate `blocks_dependents` flag and the per-task
`also_blocks_dependents:` frontmatter field (extra gates required before a task's
dependents unblock). The unblock logic is **dormant until this task** makes
profiles / `default_gates` populate `gates:` at planning time — once a task
declares gates, a declared gate marked `blocks_dependents` becomes a dependent
unblock requirement and the t635_3 mechanism goes live. Keep the two in sync: the
gates a profile declares determine which become unblock requirements;
`also_blocks_dependents` is the per-task escape hatch on top of the
profile/registry defaults. See `aidocs/gates/dependency-unblock-semantics.md`.

## Coordination (from t635_4)

Gate-guarded archival (t635_4) is **dormant until this task** populates `gates:`.
The archival guard (`aitask_archive.sh` `gate_guard()` via
`aitask_gate.sh archive-ready` / `gate_ledger.archive_status`) keys off the
declared `gates:` field, which no task carries until profiles / `default_gates`
declare them here. Once live: t635_2's recorded integration gates
(`build_verified` / `review_approved` / `merge_approved`) pass during the
workflow and archive normally — only post-integration gates that pass out of band
(async human review, `docs_updated`, manual verification) defer archival. The
guard is profile-INVARIANT (it reads declared gates, not `record_gates`), so the
profile→declaration mapping you build is exactly what activates it. See
`aidocs/gates/gate-guarded-archival.md`.

## Coordination (from t635_12)

t635_12 converted build/tests/lint into machine gates and wired task-workflow
Step 9 to `ait gates run`, but kept the **legacy inline `verify_build`
procedure** as a transitional fallback for tasks that declare no `gates:` (the
common case until this task makes declaration universal). **t635_24
(`depends: [t635_14]`) removes that fallback** — the inline `verify_build` block,
its `record_gates` manual recording, and the standalone `verify_build` settings
surface — once this unification lands. Coordinate: this task should leave the
fallback intact (its removal is t635_24's job), and t635_24 unblocks only after
this completes.

## Coordination (from t635_13)

t635_13 built and registered the `aitask-gate-risk` **state-inspection verifier**
(`.aitask-scripts/aitask_gate_risk.sh`, registry `risk_evaluated.verifier`), dormant
until this task declares the gate. When this task makes profiles *declare*
`risk_evaluated`, the following are **required acceptance criteria**:

1. **Keep the planning-time PRODUCER alive (core requirement).** The risk feature is
   a planning-time *producer* (the `risk-evaluation.md` procedure that authors the
   `## Risk` section + threads the two levels, run **before plan approval**) plus a
   verify-time *checker* (the new gate). A machine verifier can only check artifacts,
   never produce them. So declaring `risk_evaluated` MUST continue to trigger the
   planning-time risk-evaluation procedure before plan approval — the gate must not
   become a post-planning-only check. Dropping the producer keeps the gate but loses
   the plan-quality benefit (and the verifier would just fail, with no `## Risk`).
2. **Toggle producer and checker together.** A task declares `risk_evaluated` iff
   risk evaluation is enabled (the `risk_evaluation` opt-in), so the producer never
   runs without the checker, nor the checker without the producer.
3. **No double-recording of `risk_evaluated`.** Today task-workflow Step 7
   self-records `risk_evaluated` (guarded by `record_gates`); once a task *declares*
   the gate, the Step 9 orchestrator also records it → two terminal `risk_evaluated`
   runs for one planning approval. Close this with a **structural fix** (preferred
   over a fragile test-only invariant): gate the Step 7 self-record so it fires
   **only when the task does not declare `risk_evaluated`** (the orchestrator owns
   recording for declared gates), making the double-record impossible. **Plus a
   regression test** asserting exactly **one** terminal `risk_evaluated` run is
   recorded across a full plan→implement→Step 9 pass for a declaring task. This is
   the risk analog of t635_24 removing build's inline self-record.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 4)
- `aidocs/gates/dependency-unblock-semantics.md` (t635_3 — blocks_dependents / also_blocks_dependents)
- `aidocs/gates/gate-guarded-archival.md` (t635_4 — declared-gate archival guard)
- `.claude/skills/task-workflow/profiles.md`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-28T09:46:08Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-28T09:46:10Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-28T15:09:19Z status=pass attempt=1 type=human
