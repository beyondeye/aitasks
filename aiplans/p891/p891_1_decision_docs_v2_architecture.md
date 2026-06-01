---
Task: t891_1_decision_docs_v2_architecture.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_2_ops_agents_removal.md, aitasks/t891/t891_3_schema_data_tui_cleanup.md, aitasks/t891/t891_4_finalize_proposal_export.md
Worktree: (decide at pick time)
Branch: aitask/t891_1_decision_docs_v2_architecture
Base branch: main
---

# Plan — t891_1: proposal-only architecture v2 doc, archive v1

> **⚠️ DEFERRED — gated on `depends: 756`. Re-verify all section refs against the
> as-landed `brainstorm_engine_architecture.md` before editing.** Section ranges
> below are a 2026-06-01 pre-modules snapshot; t756 will have added module
> sections (those belong in v2, kept).

## Goal
Ratify proposal-only by authoring a NEW v2 architecture doc and archiving the
current two-level doc (don't rewrite in place). Per user direction.

## Steps
1. Re-read as-landed `aidocs/brainstorming/brainstorm_engine_architecture.md`.
2. `mkdir -p aidocs/brainstorming/old` and
   `git mv aidocs/brainstorming/brainstorm_engine_architecture.md aidocs/brainstorming/old/`.
3. Write `aidocs/brainstorming/brainstorm_engine_architecture_v2.md`. Carry
   forward proposal nodes, dimensions, section markers (t873), explore/compare/
   synthesize, agent-crew infra, and the module ops/sections landed by t756. OMIT
   the plan-layer sections (v1 snapshot anchors):
   - §3 node triad (~L27-32): three files → **two** (metadata + proposal).
   - §4.4 Plan Template (~L431-474): omit.
   - §7.5 Detail (~L1181-1260), §7.6 Patch (~L1262-1347): omit.
   - §7.7 Finalize (~L1349-1359): becomes **proposal export** (mirror t891_4).
   - Top-Down/Bottom-Up flow (~L1360-1400): redraw without Detailer boxes /
     IMPACT_FLAG→Patcher→Detailer chain.
   - §6 Detailer/Patcher Input Assembly (~L823-889), §8.4/§8.5 detailer/patcher
     subagent prompts (~L1634-1788): omit.
   - Mark `plan_file`/`br_plans/`/`read_plan`/`PLANS_DIR` as not part of the model.
4. Edit `aidocs/brainstorming/module_decomposition_design.md`: add t891 cross-ref;
   drop the `detail` lifecycle step (§4.6 ~L415 `n012_plan.md`) and the existing
   "detailer/patcher templates" note (§4.10 ~L523).
5. Repoint references:
   `grep -rn "brainstorm_engine_architecture" --include='*.md' --include='*.py' --include='*.sh' .`
   → point at v2 (or `old/` where the ref is specifically about the retired design).
6. Commit (`aiplans/` via `./ait git`; aidocs via regular `git`).

## Doc convention
v2 describes only the current proposal-only state — no "previously…" prose
(CLAUDE.md documentation conventions). The two-level history lives in `old/`.

## Verification
- `aidocs/brainstorming/old/brainstorm_engine_architecture.md` exists; v2 exists,
  no Detail/Patch/plan-template/detailer/patcher sections.
- `grep -rn "brainstorm_engine_architecture\.md" .` — no dangling links.
- `module_decomposition_design.md` references t891, no `detail` lifecycle step.
