---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [gates]
children_to_implement: [t635_15, t635_16, t635_17, t635_18, t635_19, t635_20, t635_21, t635_22, t635_23, t635_24, t635_25]
created_at: 2026-04-23 20:21
updated_at: 2026-06-29 09:21
boardcol: now
boardidx: 10
---

Parent task for implementing the aitasks gate framework AND its gradual
integration into the existing workflows (aitask-pick / task-workflow, TUIs,
autonomous lanes).

## Design docs (read in this order)

- `aidocs/gates/integration-roadmap.md` — **sequencing + locked integration
  decisions (D1–D8)**; maps every phase to the children below. The child
  decomposition mirrors its table exactly.
- `aidocs/gates/aitask-gate-framework.md` — the substrate contract: data
  model, marker format, registry, orchestrator, verifier contract, remote
  projection (Appendix A).
- `aidocs/gates/risk-evaluation-gate-seam.md` — ready-made first conversion
  (t635_13, formerly standalone t912).

## Phases → children

1. **Ledger substrate** (no behavior change): t635_1, t635_2
2. **Re-entry** (priority #1): t635_3 (dependency-unblock design — blocks
   t635_4), t635_4 (gate-guarded archival), t635_5 (ledger-driven resume),
   t635_6 (aitask-resume skill), t635_7 (gate-aware aitask-pick)
3. **TUI visibility**: t635_8 (Python ledger parser), t635_9 (board
   In-Flight action-grouped view), t635_10 (monitor gate column),
   t635_20 (stats redesign for multi-stage completion — design pass first;
   deferred archival breaks today's archived-only completion counting)
4. **Orchestrator + first conversions**: t635_11 (orchestrator + verifier
   contract), t635_12 (build/tests machine gates), t635_13 (risk-evaluation
   gate, ex-t912), t635_14 (profile→gate-declaration unification),
   t635_19 (docs_updated gate — new, fills the documentation checkpoint
   missing from today's task-workflow)
5. **Async human gates + remote projection**: t635_15, t635_16
6. **Autonomous-lane rigor**: t635_17

**Documentation track** (cross-phase): incremental website updates in each
user-facing child + t635_18 (comprehensive website sweep: concepts,
workflows, skills, TUIs, commands, configuration) + t635_19 as the permanent
docs-drift checkpoint thereafter.

Children carry explicit `depends:` (sibling auto-deps disabled) matching the
roadmap's dependency table — the phases overlap deliberately (e.g. t635_8
only needs t635_1).

## Coordination — artifact-producing gate family (t1076_4)

The integration roadmap names a **third gate family** — "artifact-producing
follow-ups" — alongside verifications and approvals, but leaves it as a
pseudo-gate with no child here. The unified artifact design
(`aidocs/unified_artifact_design.md` §8) formalizes it as the **artifact-producing
gate archetype**, tracked under **t1076_4** (parent t1076), which `depends: [.., 635]`
and builds on the orchestrator/verifier contract (t635_11). When that work plans,
decide whether it ultimately lands as a t635 child or stays under the artifact
umbrella; either way it is the concrete realization of this framework's third gate
family.
