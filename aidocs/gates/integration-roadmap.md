---
title: aitasks Gate Framework — Integration Roadmap
category: design
tags: [aitasks, gates, integration, roadmap, task-workflow, aitask-pick, board, re-entry, ledger-first]
sources: [aitask-gate-framework.md, risk-evaluation-gate-seam.md]
confidence: high
created: 2026-06-10
updated: 2026-06-10
---

# Gate Framework Integration Roadmap

How the gate framework ([[aitask-gate-framework]]) gets integrated **gradually
into the existing task workflows** (aitask-pick / task-workflow, the TUIs, and
the autonomous lanes) instead of landing as a parallel, disconnected system.

The framework design doc stays the contract for the substrate (data model,
registry, orchestrator, verifier contract, remote projection). This document
fixes the **sequencing, the integration decisions, and the unification end
state**, and maps each phase onto the t635 child decomposition.

## Why integration, not coexistence

The framework doc deliberately describes a self-contained mechanism
(`aitask-run-gates` + verifier skills) that could run beside today's
aitask-pick/task-workflow. In practice:

- aitask-pick is the user-facing front door, already integrated in the board
  TUI (`/aitask-pick <n>` agent launches).
- task-workflow already contains many *pseudo-gates*: plan approval
  (ExitPlanMode), Step 8 code review, Step 9 merge approval, build
  verification, risk evaluation, manual-verification follow-up (8c), upstream
  defect follow-up (8b), risk-mitigation follow-ups (Step 7 / 8d).
- Long-run, two ways of "working a task" is a split we do not want.

The pseudo-gates fall into three families that map differently onto the
framework:

1. **Verifications** (build, tests, lint) — clean fits for `machine` gates.
2. **Approvals** (plan / review / merge) — synchronous, in-conversation,
   NON-SKIPPABLE today; the framework's human gates are asynchronous and
   signal-based. These are *not* the same interaction model.
3. **Artifact-producing follow-ups** (manual-verification task creation,
   upstream-defect tasks, risk mitigations) — not pass/fail checks; their
   "pass" is "considered, and an artifact was created or explicitly waived".

Notably **absent** from today's pseudo-gates: a documentation checkpoint.
Nothing in task-workflow asks "do the docs need updating for this change?".
The framework's `docs_updated` gate fills this gap as a *new* gate rather
than a conversion (t635_19).

## Locked decisions (design session 2026-06-10)

| # | Decision | Rejected alternatives |
|---|---|---|
| D1 | **Ledger-first.** The marker format + `ait gate` append/derive tooling lands first; task-workflow starts *recording* its existing checkpoints as gate-run blocks with zero behavior change. Orchestrator and verifiers come later on a proven ledger. | Full substrate first (longest two-workflow coexistence); verify-step-first (couples t635 to task-workflow churn immediately). |
| D2 | **Hybrid-by-mode approvals.** Attended sessions keep ExitPlanMode / AskUserQuestion exactly as today — the interactive answer *is* the signal, recorded as a gate-run block. In headless/remote lanes the same gates become async signal-based human gates. One gate definition, two signal transports. | Ledger-only forever (no async story); converge on async everywhere (breaks the single-conversation flow). |
| D3 | **Priority order:** safe re-entry → TUI state visibility → async/remote review → autonomous-lane rigor. |
| D4 | **First conversions:** risk evaluation (seam already designed, see [[risk-evaluation-gate-seam]]; formerly t912, reparented as t635_13) and build verification / tests. | Manual-verification family and 8b/8d follow-ups stay pseudo-gates initially. |
| D5 | **Archival defers until all gates pass.** task-workflow Step 9's archive becomes gate-guarded; workflow-end no longer implies archive. Consequence: dependency-unblock semantics need explicit design (see open problems). | Archive-then-unarchive; re-entry from archive (fights "archived = immutable record"). |
| D6 | **Derive state from the ledger only.** No new coarse `status` value, no cached frontmatter summary. TUIs/scripts parse Gate Runs markers via a shared helper. | `status: Verifying` (drift risk); denormalized `gates_summary` field (stale-cache risk). |
| D7 | **Board UX: action-grouped In-Flight view.** A dedicated view grouping in-flight tasks by *next required action* (needs-your-sign-off / agent-can-continue / blocked) with per-task operations. | Filter + gate badge in kanban (doesn't answer "which operation"); phase swimlanes (big refactor, next-action still implicit). |
| D8 | **Re-entry path: gate-aware aitask-pick is the user-facing unified flow**, plus a separate `aitask-resume` skill as the programmatic surface — for initial testing, TUI invocation, and any interaction surface that needs direct "run these gates" control. | Board-driven gate ops only (no conversational resume). |

## Phases

Each phase is independently shippable and leaves the framework consistent.

### Phase 1 — Ledger substrate (no behavior change)

- Marker-first Gate Runs block format + `ait gate append` / `ait gates
  status` / `ait gates list` (bash + awk per the framework doc; Python
  fallback as escape hatch).
- `gates:` frontmatter field registered per the extension-points procedure.
- Minimal `aitasks/metadata/gates.yaml` registry: names, `type`,
  `description` only — no verifiers yet.
- task-workflow **records** existing checkpoints as gate-run blocks:
  plan approved, review approved, merge approved, build verified, risk
  evaluated. Purely additive appends; the interactive prompts are unchanged
  (this is the D2 seed: in attended mode the prompt outcome is the signal).

### Phase 2 — Re-entry (priority #1)

- **Dependency-unblock semantics** designed and implemented (see open
  problem 1) — must land before or with the archival change.
- **Gate-guarded archival**: Step 9 archives only when every declared gate is
  pass; otherwise the task stays active and re-enterable. Archival is offered
  (or profile-gated auto-applied) in a later session when the last gate
  passes.
- **Ledger-driven resume**: task-workflow Step 3 learns to read the ledger
  and resume from the first unmet checkpoint instead of restarting —
  a generalization of the existing crash-recovery procedure.
- **`aitask-resume` skill**: thin re-entrant orchestration scoped to "resume
  this task / run these gates"; the programmatic surface TUIs call.
- **Gate-aware aitask-pick**: in-flight tasks appear in their own pick-list
  section with derived gate state; picking one routes through the resume
  logic. The board's existing `/aitask-pick <n>` launch gains re-entry for
  free.

### Phase 3 — TUI visibility (priority #2)

- Shared **Python gate-ledger parser** (single derivation module; the bash
  `ait gates status` and the TUIs must not fork the logic).
- **Board In-Flight action-grouped view** (D7) with per-task operations wired
  to `ait gate pass`, `aitask-resume` (headless or in a pane), and
  pick-resume.
- **Monitor gate-status column** (framework doc integration table).
- **Stats redesign for multi-stage completion** (t635_20, design pass
  first): `ait stats` / `ait stats-tui` currently count only archived
  tasks and date them via `completed_at`/`updated_at` — deferred archival
  (Phase 2) makes both misleading. Settle which event is "completion",
  whether implementation-complete-but-gated tasks get their own series,
  which ledger-enabled metrics to add (time-in-phase, gate pass/retry
  rates, pending-human wait), and how mixed pre-/post-gates populations
  stay honest.

### Phase 4 — Orchestrator + first true conversions

- Verifier contract, `aitask-gate-template` skill, full registry schema
  (verifier, retries, unlocks DAG), `aitask-run-gates` orchestrator — the
  engine behind `aitask-resume`.
- Convert **build verification / tests** (Step 9 `verify_build` + ad-hoc test
  runs → machine gates).
- Convert **risk evaluation** per [[risk-evaluation-gate-seam]] (t635_13,
  formerly t912).
- Ship the **`docs_updated` gate** (t635_19) — a new gate, not a
  conversion: the documentation checkpoint missing from today's
  task-workflow. Change-scoped (`skip` when the diff touches no
  doc-relevant surface, distinct from `pass`); doc roots come from project
  config, not hardcoded.
- **Configuration unification principle** lands here: profiles stop being the
  *runtime* toggle for converted checkpoints. Instead, profiles (and
  `default_gates`) choose which gates get **declared** in `gates:` at
  planning time; the registry defines how gates run. Jinja profile-gating of
  converted pseudo-gates retires gradually — never configure the same
  checkpoint in two places.

### Phase 5 — Async human gates + remote projection

- `signal: file-touch` human gates, `ait gate pass`, and the D2 hybrid
  switch: headless lanes treat review/merge approval as genuine
  pending-human gates and stop cleanly.
- Remote projection (framework doc Appendix A: label mirror, singleton
  comment, comment signals) — gated on the dispatcher backend gaps
  (`edit_comment`, `list_comments`).

### Phase 6 — Autonomous-lane rigor

- aitask-pickrem / aitask-pickweb run `ait gates run` as their
  non-skippable verify step; stop at pending-human without escalating.
- Archive guard profile-enforced; `auto_complete_on_all_gates_pass` for the
  autonomous lane.

### Documentation track (cross-phase)

The gates work is a comprehensive redesign of how tasks are worked and must
be documented on the website across every affected surface — concepts,
workflows, skills, TUIs, commands, configuration:

- **Incremental**: every child that lands a user-facing surface updates its
  own website pages in the same task (current-state-only rule — never
  document unlanded behavior).
- **Comprehensive sweep** (t635_18): new "Gates" concept page, new workflow
  pages (working with gates / resuming in-flight tasks / human review
  sign-off), `aitask-resume` + updated aitask-pick skill pages, board
  In-Flight view + monitor column TUI docs, `ait gates`/`ait gate` command
  reference, `gates.yaml` + profile-declaration configuration reference.
- **Permanent enforcement** (t635_19): once the `docs_updated` gate ships,
  documentation drift becomes a gated checkpoint — including for the
  remaining t635 children themselves (the framework dogfooding its own
  documentation gate).

## Open design problems

### 1. Dependency unblocking (t635_3 — blocks the archival change)

Today `depends:` effectively unblocks when the upstream task completes and
archives. With deferred archival (D5), a task whose machine gates pass but
whose human review pends for days would block dependents *longer than today*
— a regression unless the unblock point is explicit. The framework doc only
brushes this (open question 4, cross-task gates, deferred from v1).

Candidate shapes to evaluate:
- Unblock at **all-gates-pass** (strict, simple, but inherits the regression
  for slow human gates).
- Per-task declared subset (`unblock_after: [tests_pass]`) — flexible,
  per-task noise.
- **Registry-level `unblocks_dependents:` flag per gate** (e.g. machine
  gates unblock, human gates don't) — declared once where the gate semantics
  live. *Current lean, not yet decided.*

### 2. Record-by-default vs opt-in (t635_2)

The framework doc says "no `gates:` field = behaves exactly like today", but
Phase 1's checkpoint recording is what makes Phase 2 re-entry work for
*every* task, not just gate-declaring ones. Proposal to evaluate: a
`gate_ledger` profile flag, default on for the core checkpoints
(plan/review/merge/build), so resume is universal. This deliberately bends
the doc's opt-in stance and must be decided when t635_2 is planned.

## t635 child decomposition

| Child | Phase | Depends | Scope |
|---|---|---|---|
| t635_1 gate ledger substrate | 1 | — | Marker format, `ait gate` CLI, `gates:` field, minimal registry |
| t635_2 checkpoint recording | 1 | 1 | task-workflow records checkpoints; record-by-default decision |
| t635_3 dependency-unblock semantics | 2 | 1 | Design + implement unblock point (open problem 1) |
| t635_4 gate-guarded archival | 2 | 2, 3 | Step 9 defers archive until all gates pass |
| t635_5 ledger-driven re-entry | 2 | 2 | Step 3 resume from first unmet checkpoint |
| t635_6 aitask-resume skill | 2 | 5 | Programmatic resume/run-gates surface |
| t635_7 gate-aware aitask-pick | 2 | 5, 6 | In-flight pick section + resume routing |
| t635_8 Python gate-ledger parser | 3 | 1 | Shared derivation module for TUIs |
| t635_9 board In-Flight view | 3 | 6, 8 | Action-grouped view + per-task gate ops |
| t635_10 monitor gate column | 3 | 8 | Per-task gate status in monitor |
| t635_11 orchestrator + verifier contract | 4 | 6 | `aitask-run-gates`, template skill, full registry |
| t635_12 build/tests machine gates | 4 | 11 | Convert `verify_build` + test runs |
| t635_13 risk-evaluation gate (ex-t912) | 4 | 11 | Convert per [[risk-evaluation-gate-seam]] |
| t635_14 profile→declaration unification | 4 | 12, 13 | Profiles declare gates; retire duplicated Jinja toggles |
| t635_15 async human gates | 5 | 11 | file-touch signals, `ait gate pass`, headless hybrid switch |
| t635_16 remote projection (Appendix A) | 5 | 15 | Label/comment mirror, comment signals; needs dispatcher backends |
| t635_17 autonomous-lane rigor | 6 | 12, 15 | pickrem/pickweb gate verify step, enforced archive guard |
| t635_18 website documentation | docs | 7, 9, 10, 12, 14 | Comprehensive website sweep: concepts, workflows, skills, TUIs, commands, config |
| t635_19 docs_updated gate | 4 | 11 | New documentation gate (no pseudo-gate ancestor); change-scoped skip |
| t635_20 stats multi-stage completion | 3 | 4, 8 | Design pass + implement: redefine completion stats under deferred archival; ledger-enabled metrics |

## See also

- [[aitask-gate-framework]] — the substrate contract this roadmap sequences.
- [[risk-evaluation-gate-seam]] — the ready-made first conversion (t635_13).
- t635 — parent implementation task; children mirror the table above.
