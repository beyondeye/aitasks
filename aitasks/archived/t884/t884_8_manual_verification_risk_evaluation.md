---
priority: medium
effort: medium
depends: [t884_7]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t884_1, t884_2, t884_3, t884_4, t884_5, t884_6, t884_7]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 00:35
updated_at: 2026-06-02 13:47
completed_at: 2026-06-02 13:47
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [skip] [t884_1] In `ait board`, a task with risk set shows its level; the detail-pane Risk CycleField cycles low/medium/high and saves; a task with no risk renders blank (no error). — SKIP 2026-06-02 13:43 Read-only by design: two-field refactor (t884_9) made board risk read-only (decided by workflow/plan, not edited in board). 'Shows level' + 'blank renders without error' verified; editable CycleField intentionally absent. Not a defect.
- [skip] [t884_1] `ait create` interactive flow offers a Risk selection and `ait update` interactive flow offers Risk. — SKIP 2026-06-02 13:46 Create-time exclusion is by design: risk is planning output written post-create (t884_9 plan: 'aitask_create.sh: no change'; test_update_risk.sh guard asserts created tasks carry neither field). The 'ait update offers Risk' half verified (fzf + --risk-code-health/--risk-goal-achievement). Not a defect.
- [x] [t884_1] Folding a task carrying risk_mitigation_tasks into a primary preserves the primary's risk and drops risk_mitigation_tasks. — PASS 2026-06-02 13:16 auto: fold drops folded task's risk_mitigation_tasks (aitask_fold_mark.sh:223-241, cleared via --risk-mitigation-tasks ''); primary risk preserved untouched; test_fold_risk_mitigation_drop.sh confirms both
- [x] [t884_2] `ait settings` -> Profiles tab shows the risk_evaluation toggle under Planning; cycle + save persists to YAML and round-trips on reload. — PASS 2026-06-02 13:16 auto: profile_editor.py:315-323 lists risk_evaluation under Planning group as bool CycleField (true/false/unset); collect_profile_values/compose_profile_fields round-trip to profile YAML
- [x] [t884_3] With risk_evaluation enabled, picking a task runs the risk-evaluation step at end of planning (assesses code-health AND goal-achievement) and the plan gains a populated ## Risk section; with it disabled, no risk step appears. — PASS 2026-06-02 13:16 auto: source-verified — planning.md gates end-of-planning risk-eval on {% if profile.risk_evaluation %}; risk-evaluation.md assesses code-health + goal-achievement separately and writes ## Risk; disabled profiles omit the step
- [x] [t884_3] After plan approval, the task's risk frontmatter field is written with the assessed aggregate level (visible in ait board). — PASS 2026-06-02 13:16 auto: source-verified — SKILL.md Step 7 writes risk_code_health/risk_goal_achievement via aitask_update.sh post-approval (gated); update.sh:528-532 serializes both; board renders them
- [x] [t884_4] The mitigation step proposes before/after tasks and creates only the confirmed ones; a "before" mitigation makes the original show Blocked until it lands; an "after" mitigation is created post-implementation (Step 8d). — PASS 2026-06-02 13:36 auto: source-verified — risk-mitigation-followup.md Parts 1/2/3 (propose-and-confirm gate; before=independent dep wiring depends:+risk_mitigation_tasks, original Blocked until lands; after=Step 8d non-blocking); SKILL.md Steps 7/8d wire in
- [x] [t884_5] After a "before" mitigation lands, re-picking the original forces plan re-verification (verify mode), not a silent skip; a task with no risk_mitigation_tasks picks normally. — PASS 2026-06-02 13:36 auto: source-verified — planning.md Step 6.0a + aitask_risk_mitigation_landed.sh emit FORCE_VERIFY:1 -> --force-verify when a before-mitigation landed after last verify; FORCE_VERIFY:0 (no-op) when risk_mitigation_tasks absent/empty
- [x] [t884_6] The website renders the new risk docs (board risk field, risk-eval workflow, risk_evaluation profile key) with no broken links. — PASS 2026-06-02 13:36 auto: hugo build --gc --minify exits 0, no broken-ref errors (only theme deprecation WARNs); workflows/risk-evaluation.md + board risk docs + risk_evaluation profile key present; listed in workflows/_index.md:43
- [skip] [t884_7] The deferred follow-up tasks (Codex/OpenCode ports, priority+risk enum refactor, gates integration) exist with correct t884 cross-references. — SKIP 2026-06-02 13:47 Codex/OpenCode ports follow-up dropped by design (user-confirmed in t884_7) as a no-op: risk closures auto-render to Codex/OpenCode. t911 (enum refactor) + t912 (gates integration) verified present with correct t884/t884_7 cross-refs. Not a defect.
