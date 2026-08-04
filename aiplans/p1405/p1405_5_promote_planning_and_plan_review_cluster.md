---
Task: t1405_5_promote_planning_and_plan_review_cluster.md
Parent Task: aitasks/t1405_triage_agent_memory_store_into_aidocs.md
Sibling Tasks: aitasks/t1405/t1405_*.md
Archived Sibling Plans: aiplans/archived/p1405/p1405_*_*.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# p1405_5 — Promote the planning & plan-review cluster

## Context

Child 5 of t1405. Promotes ~20 memories into `aidocs/framework/planning_conventions.md`.

**Read first, in order:**
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan.
   It owns the **per-memory decision gate** (re-verify → user rules on every
   memory → journal-then-execute), the **store-concurrency rules**, and the
   journal schema. All binding here; do not re-derive them.
2. `aiplans/archived/p1405/p1405_1_*.md` — the frozen manifest and the triage
   table naming exactly which memories this child owns.
3. The archived plans of earlier siblings — for the destination headings they
   already created, so a rule is not documented twice.

The task file carries the full per-memory content list. The store is outside the
repo: its deletions and `MEMORY.md` edits appear in no git diff — say so in the
Final Implementation Notes.

## Steps

1. **Re-verify (gate Phase 1).** For the whole cluster at once, check each
   memory's claim against current source and print the verdict table
   (HOLDS / FLIPPED / UNVERIFIABLE) with real path:line or command-output
   evidence. Draft the target `##` entry for each as you go.
2. **Rule (gate Phase 2).** Paginated `AskUserQuestion`, four memories per call,
   options Promote / Merge into `<doc>#<heading>` / Delete — no promotion /
   Keep as memory / Show me the drafted entry. UNVERIFIABLE items are offered
   only Delete / Keep / Show. Collect all rulings before writing anything.
3. **Execute (gate Phase 3).** Per ruling: journal to
   `.aitask-memtriage/t1405_5.tsv` → apply the doc edit and the deletion and
   the `MEMORY.md` line removal → flip `state` to `done`.
4. Leave the existing CLAUDE.md trigger's "candidate for future promotion into
   the task-workflow planning procedure" judgement alone — this task moves
   memories into the doc, it does not move the doc into a skill.

## House style (non-negotiable)

One `##` per rule, the heading being **the rule stated as a full sentence**;
rule paragraph, then rationale paragraph naming the failure mode. Drop the
"surfaced in tNNN / the user rejected X" narrative — convention docs cite task
ids sparingly, as evidence anchors only. `aidocs/framework/code_conventions.md`
is the canonical single-entry shape.

**Grep the sibling docs before adding a section** — cluster boundaries drift
across six promotion children, and the same rule written into two docs is a
defect this task exists to prevent.

## Verification

- Every claim re-verified before promotion; UNVERIFIABLE items are structurally
  ineligible and are listed as dropped in the Final Implementation Notes.
- Every cited source path in the edited doc(s) still exists (the dead-reference
  check in the task file — it exits 1, not merely prints).
- `bash tests/test_aidocs_pointer_parity.sh` passes.
- Every ruling journalled `state=done`; each PROMOTE/MERGE row carries a
  verbatim, single-line, tab-free excerpt of **≥40 characters** taken from the
  text actually written, and that excerpt is findable inside the journalled
  section's span.
- `MEMORY.md` lines removed by matching the line's link target **after
  re-reading the file** — never by regenerating the index from a remembered
  list, because a concurrent writer may have added lines.

## Risk

### Code-health risk: medium
- A claim whose premise has since flipped lands in a shared repo doc under false
  authority · severity: high · → mitigation: Phase 1 re-verification against
  current source, with UNVERIFIABLE structurally ineligible for promotion
- The same rule is written into two docs as cluster boundaries drift ·
  severity: medium · → mitigation: grep the sibling docs before adding a section

### Goal-achievement risk: medium
- An interrupted run leaves the store, index and audit inconsistent · severity:
  medium · → mitigation: journal-before-mutate with an idempotent replay of
  `ruled` rows only
- A promoted entry is condensed so far it loses the rule's actionable content ·
  severity: medium · → mitigation: the user rules on every memory and can ask to
  see the drafted entry before deciding

### Planned mitigations
None as separate tasks — each mitigation is an in-scope step above.
