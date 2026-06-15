---
Task: t635_5_ledger_driven_reentry.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_6_aitask_resume_skill.md, aitasks/t635/t635_7_gate_aware_aitask_pick.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md, aiplans/archived/p635/p635_4_gate_guarded_archival.md
Base branch: main
plan_verified: []
---

# t635_5 — Ledger-driven re-entry

## Context

Phase 2 of the gate-framework roadmap (`aidocs/gates/integration-roadmap.md`),
the #1-priority pain point (D3): re-running a task that is already
`Implementing` should **skip what's done and resume from the first unmet
checkpoint**, instead of restarting at planning. Today re-entry state lives
only in the conversation; the crash-recovery path (Step 4) reclaims the lock
but the workflow then re-runs Step 6 (for child tasks, re-verifies the plan)
and Step 7 from the top — wasteful and lossy.

The substrate is already here:
- **t635_2** makes task-workflow *record* its five checkpoints as `## Gate
  Runs` ledger blocks (`plan_approved`, `risk_evaluated`, `review_approved`,
  `build_verified`, `merge_approved`), live on the `fast` profile
  (`record_gates: true`).
- **t635_4** established the deferred-archival in-flight shape (`Implementing`
  + ledger entries + lock held) and the profile-invariant, ledger-keyed
  Step-3 check precedent (Check 4).

This task makes **task-workflow itself re-entrant**: Step 3 reads the ledger,
derives the resume point (respecting the framework's back-to-front
last-block-wins rule), and the post-reclaim flow jumps to the right step. The
crash-recovery procedure is generalized to use the ledger as its source of
truth.

**Blast-radius note (differs from t635_4):** t635_4 was *dormant* (keyed off
the unpopulated `gates:` field). This task keys off the **recorded `## Gate
Runs` ledger**, which `record_gates: true` already populates (confirmed: all 5
most-recently archived tasks carry `plan_approved`/`risk_evaluated`/`review_approved`
runs) — so re-entry goes **live immediately for the `fast` profile**. It is inert
elsewhere: an empty ledger derives to `PLAN` = exactly today's flow, and every
resume is still gated by the existing reclaim confirmation. This is the intended
Phase-2 behavior, surfaced explicitly in Risk below.

## Design decisions (rationale + rejected alternative)

1. **Resume point = a 3-state derivation `PLAN | IMPLEMENT | POSTIMPL`**, keyed
   off the *recorded checkpoint* ledger (not declared `gates:`):
   - `PLAN` — `plan_approved` not `pass` (incl. empty ledger) → plan from
     scratch (today's flow; not really re-entry).
   - `IMPLEMENT` — `plan_approved` pass, `review_approved` not pass → resume at
     **Step 7** (plan approved; implement/review pending).
   - `POSTIMPL` — `review_approved` pass → resume at **Step 9** (code committed
     & reviewed; merge/build/archive pending). Step 9 itself handles
     worktree-vs-current-branch and gate-guarded archival, so `merge_approved`
     doesn't need its own resume stage. *Rejected:* a finer stage per gate —
     `risk_evaluated`/`build_verified` are not workflow re-entry boundaries
     (risk is a quick post-approval write; build lives inside Step 9), so they
     add states the workflow can't act on distinctly.

2. **Derivation lives in `gate_ledger.py` (`resume_point()`), parallel to
   `archive_status()`/`dependents_status()`** — single source of truth, reuses
   the existing `derive_status()` (back-to-front last-wins). Surfaced as
   `aitask_gate.sh resume-point <id>` (python-delegated, degrades to `PLAN` if
   Python absent — safe = today's behavior). *Rejected:* awk-implementing it in
   `aitask_gate.sh` — `deps-unblock`/`archive-ready` set the precedent that
   low-frequency decisions are python-delegated.

3. **Skill edits are profile-INVARIANT (no new Jinja gate)**, exactly like
   t635_4 Check 4. The check reads the ledger at runtime; an empty ledger →
   `PLAN` → no-op. Making it `record_gates`-gated would be wrong (the resume is
   keyed off ledger *presence*, not the recording profile key) and would churn
   only the `fast` golden. *Rejected:* `record_gates` Jinja guard.

4. **Resume routing folds into the existing reclaim confirmation — no new
   prompt.** Step 3 Check 5 only *detects + sets* `resume_point`; Step 4's
   crash-recovery reclaim prompt (which already asks "Reclaim and continue?"
   and surveys uncommitted changes) is enriched to show the resume target. On
   `reclaim`, the flow routes by `resume_point`. *Rejected:* a separate
   "resume here?" AskUserQuestion — redundant with the reclaim prompt the user
   already answers.

5. **Conservative resume targets.** `IMPLEMENT` lands at Step 7's implementation
   body, which re-runs implementation anyway (no work is silently skipped — only
   planning). `POSTIMPL` lands at Step 9, whose merge approval is **NON-SKIPPABLE**.
   So a stale ledger cannot cause an unreviewed merge.

## Deliverables (file by file)

### 1. `.aitask-scripts/lib/gate_ledger.py` (extend; stdlib-only)

Add `resume_point(task_file) -> "PLAN"|"IMPLEMENT"|"POSTIMPL"` next to
`archive_status` (reuses `derive_status`; keys off recorded `plan_approved` /
`review_approved`). CLI verb `resume-point <task-file>`; add to docstring CLI list.

### 2. `.aitask-scripts/aitask_gate.sh` (extend)

Add `cmd_resume_point` mirroring `cmd_archive_ready`: resolve file,
`delegate_python resume-point "$file" || echo "PLAN"` (degrade to PLAN). Register
in `main()` case, header-comment subcommand list, and `show_help`. No `ait`
dispatcher entry; no whitelist change (subcommand of already-whitelisted script).

### 3. `task-workflow/SKILL.md` Step 3 — Check 5 (profile-invariant)

Add **Check 5 — In-flight task, resume from first unmet checkpoint** after Check 4.
Reads status (skip if not `Implementing`), runs `aitask_gate.sh resume-point`,
`PLAN` → skip (today's flow; default/remote unchanged), `IMPLEMENT`/`POSTIMPL` →
set `resume_point`, show banner, proceed to Step 4. Update closing Note (Check 5
runs Step 4, does NOT skip it).

### 4. `task-workflow/SKILL.md` Step 4 + new "Re-entry Routing" (profile-invariant)

Routing hooked at END of Step 4 on ANY ownership-success path (not crash-recovery's
`reclaim` branch — closes the plain-`OWNED` takeover gap). New **Re-entry Routing**
subsection (between Step 4 and Step 5): plan-existence guard (fall back to PLAN if
no plan), worktree reuse, `IMPLEMENT` → Step 7 "Follow the approved plan" body
(re-run only ownership guard + Agent Attribution; skip non-idempotent post-approval
gates), `POSTIMPL` → Step 9.

### 5. `task-workflow/crash-recovery.md` — generalize to ledger-driven (static, no golden)

Inputs gain `resume_point` (from context or computed). Step 1 Survey adds
`aitask_gate.sh status` + resume target (ledger is primary signal; plan-marker
fallback). Step 2 prompts append the resume target. Step 3 return contract
unchanged (routing decoupled, driven by context var per §4).

### 6. `aidocs/gates/ledger-driven-reentry.md` (new design doc)

Mirror `gate-guarded-archival.md`. Covers 3-state derivation, recorded-vs-declared
keying, fold-into-reclaim, becomes-live blast radius, conservative targets,
crash-recovery generalization, rejected alternatives. Back-link from
`integration-roadmap.md` Phase 2.

### 7. `website/content/docs/workflows/crash-recovery.md` (current-state update)

Short subsection: re-picked in-flight task with recorded checkpoints resumes from
the first unmet checkpoint; reclaim prompt shows the resume target.

### 8. Tests — `tests/test_gate_reentry.sh` (new, self-contained)

Model on `test_gate_guarded_archival.sh`. resume_point bash/python parity: empty →
PLAN; plan_approved → IMPLEMENT; +risk_evaluated → IMPLEMENT; +review_approved →
POSTIMPL; +merge_approved → POSTIMPL. Derivation last-wins (fail→pass, pass→fail,
pending). Child path. Degrade → PLAN.

### 9. Goldens + render verification (same commit)

Regenerate all 3 `SKILL-{default,fast,remote}.md` goldens identically; other proc
goldens diff empty; `aitask_skill_verify.sh` + `aitask_skill_rerender.sh remote`.

### 10. Coordination notes (post-approval)

Bidirectional links via `./ait git` to t635_6 (resume skill consumes resume-point)
and t635_7 (gate-aware pick routes through resume logic).

### Out of scope

t635_6 resume skill; t635_7 pick section; t635_14 `gates:` population; lock
semantics beyond existing reclaim; t635_9/_10 TUI surfacing; t635_11 orchestrator.

## Edge cases reviewed (re-entrant skill correctness)

1. Plain-`OWNED` takeover (no reclaim signal) → routing at end of Step 4 on any
   success path, gated on `resume_point`, not on the `reclaim` branch.
2. Double-creation on `IMPLEMENT` resume → resume at "Follow the approved plan"
   body, past the non-idempotent Cross-Repo / before-mitigation gates (which end
   the workflow when they fire, so a still-`Implementing` task is past them).
3. Missing plan on resume → plan-existence guard falls back to `PLAN`.
4. Empty ledger / non-`record_gates` profiles → `PLAN` → today's flow unchanged.
5. `manual_verification` in-flight → handled by Check 3; resume-point `PLAN` anyway.
6. `decline` on reclaim → workflow ends before routing gate.
7. Derivation last-wins via `derive_status()` → re-opened checkpoint demotes the
   resume stage (tested).

## Risk

### Code-health risk: medium
- Editing shared `task-workflow/SKILL.md` Step 3 + Step 4 (rendered × 3 agents ×
  3 profiles) risks Jinja/golden churn · severity: medium · → mitigation:
  profile-invariant prose (mirror t635_4 Check 4); regenerate all 3 SKILL goldens;
  `test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh` green;
  `aitask_skill_rerender.sh remote`; other proc goldens diff empty.
- New `resume_point()`/`resume-point` is additive, parallels
  `archive_status`/`archive-ready` (stdlib, python-delegated, degrades to PLAN) ·
  severity: low · → mitigation: `test_gate_reentry.sh` bash/python parity;
  `shellcheck`; macOS static sweep (no new awk).
- `crash-recovery.md` is a static read-on-demand procedure (no Jinja, no golden) ·
  severity: low.

### Goal-achievement risk: medium
- Re-entry goes live immediately on `record_gates` (fast) profiles; a
  stale/contradictory ledger could route to the wrong step · severity: medium ·
  → mitigation: fires only for `Implementing` + recorded checkpoints (empty ledger
  = `PLAN` = today's flow); gated by the existing reclaim confirmation (surveys
  uncommitted changes, shows resume target); conservative targets (`IMPLEMENT` =
  Step 7 re-runs implementation, `POSTIMPL` = Step 9 with NON-SKIPPABLE merge).
- Worktree reuse on resume must not recreate an existing branch/worktree ·
  severity: low · → mitigation: `git worktree list --porcelain` detection before
  Step 5 create; current-branch profiles are a no-op.

### Planned mitigations
None — risks are bounded and mitigated in-task by the test/golden/verify
deliverables.

## Verification

1. `shellcheck .aitask-scripts/aitask_gate.sh`; macOS sweep (python-delegated, no new awk).
2. `bash tests/test_gate_reentry.sh` — resume_point parity, last-wins, child, degrade.
3. Regression: `test_gate_ledger.sh`, `test_gate_guarded_archival.sh`,
   `test_gate_record.sh`, `test_skill_render_task_workflow.sh`.
4. `aitask_skill_verify.sh` + `aitask_skill_rerender.sh remote` green; `SKILL-*`
   golden diffs match intended adds; other proc goldens empty; remote prerender un-drifted.
5. Manual smoke: append plan_approved pass → resume-point IMPLEMENT; append
   review_approved pass → POSTIMPL; empty → PLAN.

## Step 9 reference

Post-implementation cleanup and archival follow the shared **Step 9
(Post-Implementation)** flow (current branch — `fast` profile; no worktree/merge).
This task declares no `gates:`, so its own archival is unaffected.

## Final Implementation Notes

- **Actual work done:** Made task-workflow re-entrant. `lib/gate_ledger.py`
  gained `resume_point()` (3-state `PLAN`/`IMPLEMENT`/`POSTIMPL`, keyed off the
  recorded `plan_approved`/`review_approved` checkpoints via `derive_status()`)
  + CLI verb `resume-point`. `aitask_gate.sh` gained a `resume-point <task-id>`
  subcommand (python-delegated, degrades to `PLAN` if Python is absent).
  `task-workflow/SKILL.md` (profile-invariant): Step 3 **Check 5** detects an
  in-flight task and sets the `resume_point` context var; a new **Re-entry
  Routing** subsection at the end of Step 4 routes `IMPLEMENT`→Step 7
  implementation body / `POSTIMPL`→Step 9, with plan-existence and
  worktree-reuse guards. `crash-recovery.md` generalized to treat the gate
  ledger as the primary progress signal (survey shows recorded checkpoints +
  resume target; routing decoupled — it only displays). New design doc
  `aidocs/gates/ledger-driven-reentry.md` + roadmap backlink; website
  `crash-recovery.md` current-state section. New `tests/test_gate_reentry.sh`
  (14/14: resume_point bash/python parity, last-wins demotion, child path,
  degrade shape). Regenerated all 3 `SKILL-*` goldens (identical profile-invariant
  adds) + rerendered the committed `task-workflow-remote-` prerenders
  (claude/codex/opencode — `crash-recovery.md` is part of the rendered closure,
  so it propagated too). Render 99/99; `aitask_skill_verify.sh` OK; shellcheck +
  python parse clean.

- **Deviations from plan:** One wording fix forced by the render suite. The
  Re-entry Routing prose originally used the literal phrase `Risk-mitigation
  "before" creation`, which `test_skill_render_task_workflow.sh` Test 5 asserts
  is **absent** from the default-profile render (the real Step 7 hook is gated
  behind `risk_evaluation`). Reworded to "the risk-mitigation pre-task creation
  (the post-approval 'before' follow-ups)" — same meaning, no literal collision.
  Caught and fixed before commit.

- **Issues encountered:** During review (at the user's request to be extra
  careful), two real control-flow bugs were caught in the *plan* before coding:
  (1) routing tied to crash-recovery's `reclaim` branch would silently lose the
  resume on the plain-`OWNED` force-unlock-takeover path (`aitask_pick_own.sh`
  only emits `RECLAIM_*` when `prev_assigned == EMAIL`) → moved the routing gate
  to end-of-Step-4 on any ownership-success path; (2) resuming `IMPLEMENT` at
  Step 7's top would re-fire the non-idempotent Cross-Repo / "before"-mitigation
  creators → resume at the "Follow the approved plan" body instead.

- **Key decisions:** (1) Keyed off the *recorded* checkpoint ledger, not the
  declared `gates:` field — a separate `resume_point` function from
  `archive_status`/`dependents_status` (do not conflate). (2) 3-state collapse
  (risk_evaluated/build_verified/merge_approved are not re-entry boundaries).
  (3) Profile-invariant skill edits (empty ledger → `PLAN` → today's flow;
  inert without a ledger). (4) Folds into the existing reclaim confirmation —
  no new prompt. (5) Conservative targets (`IMPLEMENT`=Step 7 re-runs
  implementation, `POSTIMPL`=Step 9 with NON-SKIPPABLE merge). (6) Becomes
  **live immediately** on `record_gates` (fast) profiles — confirmed the 5
  most-recently archived tasks all carry recorded checkpoints, so re-entry is
  genuinely active, not dormant like t635_4.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t635_6 (aitask-resume skill):** consume `aitask_gate.sh resume-point` /
    `gate_ledger.resume_point` and the generalized `crash-recovery.md` as the
    programmatic re-entry engine — do NOT fork the derivation. The 3-state
    contract (`PLAN`/`IMPLEMENT`/`POSTIMPL`) is the resume API.
  - **t635_7 (gate-aware aitask-pick):** the in-flight pick section should route
    a picked in-flight task through Step 3 Check 5 + Re-entry Routing
    (`resume_point`), not re-derive resume logic.
  - **`resume_point` vs `archive_status` vs `dependents_status`:** three distinct
    decisions in `gate_ledger.py`. resume_point = recorded workflow progress
    (`plan_approved`/`review_approved`); archive_status = ALL declared gates pass;
    dependents_status = `blocks_dependents` gates pass. Do not conflate.
  - **Routing gate placement:** routing is keyed on the `resume_point` context
    var at end of Step 4 (any ownership-success path), NOT on crash-recovery's
    `reclaim` return — preserves resume across the plain-`OWNED` takeover path.
