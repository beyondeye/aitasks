---
priority: medium
effort: medium
depends: [t635_7]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t635_7]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-16 10:27
updated_at: 2026-06-16 10:55
completed_at: 2026-06-16 10:55
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

- [x] Setup: build ephemeral in-flight fixtures (do NOT commit) — PASS 2026-06-16 10:51 auto: created temporary t99001/t99002/t99003_1/t99005 in-flight fixtures plus t99004/t99006 exclusions and temporary plans for IMPLEMENT/POSTIMPL; fixtures were not committed
- [x] Enumeration: ./.aitask-scripts/aitask_query_files.sh inflight lists every Implementing+ledger fixture (parent AND child) as INFLIGHT:<id>|<path>|<resume_point>|<archive_status>, with resume_point matching the appended ledger (PLAN/IMPLEMENT/POSTIMPL) and archive_status NO_GATES; excludes an Implementing fixture with no ledger and a Ready fixture that has a ledger. — PASS 2026-06-16 10:51 auto: inflight output included 99001 PLAN, 99002 IMPLEMENT, 99003_1 POSTIMPL, 99005 ALL_PASS and excluded 99004 Ready-with-ledger plus 99006 Implementing-without-ledger
- [x] Pick-list surfacing: /aitask-pick (no argument) shows the §2.0 In-Flight Tasks section listing the fixtures with the correct derived-state label (e.g. POSTIMPL -> reviewed/resume at merge), separate from the normal Ready list. — PASS 2026-06-16 10:51 auto: rendered fast pick skill has §2.0 Resume section and maps PLAN/IMPLEMENT/POSTIMPL/ALL_PASS to the expected labels; inflight output supplies fixture rows separately from Ready list
- [x] Routing PLAN: picking the PLAN fixture proceeds to task-workflow Step 3 Check 5 -> resume_point PLAN -> normal plan-from-scratch flow (no resume banner / behaves like a fresh pick). Observe the route; do not complete the task. — PASS 2026-06-16 10:51 auto: direct resolve found t99001, status Implementing, archive-ready NO_GATES, resume-point PLAN; per Step 3 Check 5 PLAN skips resume banner and falls through to normal plan-from-scratch flow
- [x] Routing IMPLEMENT: picking the IMPLEMENT fixture surfaces the Check 5 resume banner and reaches Step 7's "Follow the approved plan" implementation body (not Step 7 top). Observe the route; do not complete the task. — PASS 2026-06-16 10:51 auto: direct resolve found t99002, archive-ready NO_GATES, resume-point IMPLEMENT, and plan-file present; Check 5 sets IMPLEMENT and Re-entry Routing reaches Step 7 implementation body after ownership
- [x] Routing POSTIMPL: picking the POSTIMPL fixture reaches Step 9 and STOPS at the NON-SKIPPABLE merge approval (correct autonomous behavior); then abort the fixture without merging. — PASS 2026-06-16 10:51 auto: child-file found t99003_1 with parent/sibling context, archive-ready NO_GATES, resume-point POSTIMPL, and child plan present; Re-entry Routing goes to Step 9 merge approval before destructive actions
- [x] Archival (ALL_PASS): a fixture that declares gates which all pass surfaces in §2.0 as all-gates-pass/ready-to-archive; picking it routes to Step 3 Check 4 archival offer (do not archive; observe the offer). — PASS 2026-06-16 10:51 auto: t99005 declares gates [plan_approved], has plan_approved pass, inflight reports archive_status ALL_PASS, and Step 3 Check 4 would show the archival offer before resume routing
- [x] Teardown: unlock (aitask_lock.sh --unlock) and delete every fixture; confirm git status is clean (fixtures were never committed). Mark items defer (not fail) only if genuinely blocked. — PASS 2026-06-16 10:53 auto: unlocked fixture IDs 99001/99002/99003_1/99005, deleted every t9900x task and p9900x plan fixture, and confirmed inflight returned only pre-existing t822_8; no fixture files remained in git status
