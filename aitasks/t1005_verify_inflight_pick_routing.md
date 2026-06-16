---
priority: medium
effort: medium
depends: [t635_7]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t635_7]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-16 10:27
updated_at: 2026-06-16 10:47
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t635_7

**Run in autonomous mode** (`auto-verification.md` §2a): the checklist builds
and tears down its own ephemeral in-flight fixtures inline, so no human setup is
required. This is the live behavioral counterpart to t635_7's static render/unit
tests — it confirms the gate-aware `aitask-pick` §2.0 section lists in-flight
tasks with the correct derived state and routes each pick to the matching
`task-workflow` step (Check 5 resume / Check 4 archival). For the POSTIMPL case,
assert the route reaches Step 9's NON-SKIPPABLE merge approval and then abort —
do not complete destructive steps.

## Verification Checklist

- [ ] Setup: build ephemeral in-flight fixtures (do NOT commit) — create throwaway tasks via aitask_create.sh --batch, set each to status Implementing (aitask_update.sh --batch <id> --status Implementing), and populate the ## Gate Runs ledger with aitask_gate.sh append to land each resume stage: PLAN (no gate runs), IMPLEMENT (plan_approved pass), POSTIMPL (plan_approved + review_approved pass). Create at least one parent fixture and one child fixture.
- [ ] Enumeration: ./.aitask-scripts/aitask_query_files.sh inflight lists every Implementing+ledger fixture (parent AND child) as INFLIGHT:<id>|<path>|<resume_point>|<archive_status>, with resume_point matching the appended ledger (PLAN/IMPLEMENT/POSTIMPL) and archive_status NO_GATES; excludes an Implementing fixture with no ledger and a Ready fixture that has a ledger.
- [ ] Pick-list surfacing: /aitask-pick (no argument) shows the §2.0 In-Flight Tasks section listing the fixtures with the correct derived-state label (e.g. POSTIMPL -> "reviewed — resume at merge / post-implementation"), separate from the normal Ready list.
- [ ] Routing PLAN: picking the PLAN fixture proceeds to task-workflow Step 3 Check 5 -> resume_point PLAN -> normal plan-from-scratch flow (no resume banner / behaves like a fresh pick). Observe the route; do not complete the task.
- [ ] Routing IMPLEMENT: picking the IMPLEMENT fixture surfaces the Check 5 resume banner and reaches Step 7's "Follow the approved plan" implementation body (not Step 7 top). Observe the route; do not complete the task.
- [ ] Routing POSTIMPL: picking the POSTIMPL fixture reaches Step 9 and STOPS at the NON-SKIPPABLE merge approval (correct autonomous behavior); then abort the fixture without merging.
- [ ] Archival (ALL_PASS): a fixture that declares gates which all pass surfaces in §2.0 as "all gates pass — ready to archive"; picking it routes to Step 3 Check 4 archival offer (do not archive — observe the offer).
- [ ] Teardown: unlock (aitask_lock.sh --unlock) and delete every fixture; confirm git status is clean (fixtures were never committed). Mark items defer (not fail) only if genuinely blocked.
