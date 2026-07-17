---
Task: t1157_chatlink_multi_workflow_remote_explore.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157 — Chatlink multi-workflow remote explore

## Summary

Turn Chatlink into one provider-neutral workflow host, validated on Discord,
while preserving focused bug intake and adding a separate channel-driven remote
explore workflow. The parent is intentionally decomposed: central contracts and
compatibility land before behavior changes, then UI/docs and broad verification
close the loop.

## Delivery order

1. `t1157_1` defines layered configuration, global host state, project lookup,
   and legacy compatibility.
2. `t1157_2` separates durable workflow sessions from sandbox attempts and
   adds checkpoints/proposals.
3. `t1157_3` routes one adapter connection across configured projects,
   workflows, and guilds; it incorporates folded t1127.
4. `t1157_4` migrates bug intake to budget-aware, explicit-approval,
   resumable behavior.
5. `t1157_5` adds channel-driven remote explore core.
6. `t1157_6` adds file selection, fold discovery, and cross-repo shaping.
7. `t1157_7` extends t1149's shipped panel/wizard; it must not overlap the
   in-flight t1149_2 implementation.
8. `t1157_8` documents the shipped behavior.
9. `t1157_9` adds deterministic soak and live-validation coverage; it
   incorporates folded t1144.
10. `t1157_10` is the aggregate manual-verification checklist for the
    Discord/TUI behaviors produced by the implementation children.

## Shared contracts

- Project-owned workflow definitions are checked in; per-machine host settings
  select registered projects and keep Discord secrets out of YAML.
- A workflow session is durable and thread-scoped. A sandbox attempt is
  disposable, has its own relay id/snapshot/deadline, and cannot mutate source
  or task data.
- A proposal is not an approval. Only a fresh, initiator-owned gateway action
  may create a task. Proposals and checkpoints are retained for seven days.
- Bug attempts use 20 minutes active work plus 10 minutes synthesis; explore
  uses 45 plus 15. Question waits consume active budget and visibly state their
  deadline/default. Approval never keeps a sandbox alive.
- Resume uses latest committed HEAD and revalidates findings. Restart uses the
  source/thread context but discards findings. Revision runs a bounded new
  attempt from proposal/transcript/change request.

## Risk

### Code-health risk: high

- The daemon, persistence, flow pump, configuration, and launcher are central
  concurrent paths; broad refactoring can break existing intake or violate the
  single-writer invariant · severity: high · → mitigation: embedded in
  t1157_1, t1157_2, t1157_3, and t1157_9 compatibility, migration, fault, and
  seeded-soak coverage.
- The t1149 UI/wizard work is currently in flight and shares Chatlink surfaces
  · severity: medium · → mitigation: t1157_7 reads the shipped t1149 records
  first and extends rather than overlaps those changes.

### Goal-achievement risk: high

- Durable asynchronous proposals, timeout semantics, and resume/revision must
  remain understandable on Discord and must never auto-create work · severity:
  high · → mitigation: embedded in t1157_2, t1157_4, t1157_5, and t1157_9
  state-machine, permission, deadline, and live interaction tests.
- Multi-project routing and advanced parity may create the wrong task or fold
  stale work if gateway validation is incomplete · severity: high · →
  mitigation: embedded in t1157_3 and t1157_6 authoritative routing and
  immediately-before-mutation revalidation.

## Step 9 reference

After every child, preserve its final implementation notes for the next
sibling. Once all children and aggregate manual verification complete, archive
the folded references with the parent through the standard post-implementation
workflow.
