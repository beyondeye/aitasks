---
priority: high
effort: medium
depends: [t1405_4]
issue_type: documentation
status: Ready
labels: [documentation, docs]
gates: [risk_evaluated]
anchor: 1405
created_at: 2026-08-04 13:46
updated_at: 2026-08-04 13:46
---

## Context

Fifth child of t1405. Promotes the **planning & plan-review** cluster (~20
memories) into `aidocs/framework/planning_conventions.md`.

Read first:
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan,
   which owns the per-memory decision gate, the store-concurrency rules, and the
   journal schema. Binding here; do not re-derive.
2. `aiplans/archived/p1405/p1405_1_*.md` — the frozen manifest and the triage
   table naming exactly which memories this child owns.

The store is outside the repo, so its deletions and `MEMORY.md` edits appear in
no git diff — say so in the Final Implementation Notes.

## Scope

`planning_conventions.md` is currently 7 KB with 8 sections and already carries
the right remit ("read when writing or reviewing an implementation plan"). It
grows to ~28 sections with:

plan review for distributed-state correctness (publish ordering, empty-state
bootstrap, retry staleness, identity-vs-existence, absent-vs-occupied);
re-derive every constant and re-read every shared helper's real semantics before
pinning them in a plan; child plans must be self-contained (resolved paths,
inline schemas, no "..." placeholders); testability-first decomposition (each
child owns its tests; extract pure headless units early); decomposition
sequences the riskiest-assumption spike first, with a crash-ownership /
orphan-reaper story; every v1 exclusion gets an explicit disposition and
multi-step ordering is single-sourced in the caller; never deviate silently from
a task's acceptance criteria — update the AC first; a coordination dependency
gets a reverse pointer in the other task; interrogate cleanliness / safety /
blast radius before approving an approach; defer a removal when the feature
being removed models upcoming dependent work; update ALL parallel surfaces
(shipped config + in-code fallback) and thread existing context params through
new paths; verify relative-vs-absolute path and "shared renderer / both surfaces
for free" assumptions against the actual code; enumerate every sink in an
injection-surface plan, not a representative subset; a missed performance gate
is evidence for the user to act on, never an instruction to auto-revise tasks;
a fallback is only a fix if its trigger state is reachable; when a task's own
pick-time safety gate fails, revert to Ready and hand off rather than offering
execution.

Plus one framework behaviour: a **decomposing parent never auto-creates Step-8d
"after" risk mitigations** — they must be created at decomposition time, with a
`depends:` edge on the parent.

**Check the sibling docs before adding a section** — several of these border on
`testing_conventions.md` and `code_conventions.md`. Grep first so cluster drift
across six promotion children does not document the same rule twice.

## Key files

- `aidocs/framework/planning_conventions.md` — the promotion target.
- `.aitask-memtriage/t1405_5.tsv` — the rulings journal (git-ignored).

Note the existing CLAUDE.md trigger for this doc says these rules "are a
candidate for future promotion into the task-workflow planning procedure" —
leave that judgement alone; this task moves memories into the doc, it does not
move the doc into a skill.

## House style (non-negotiable)

One `##` per rule, the heading being **the rule stated as a full sentence** —
`planning_conventions.md`'s existing headings (`## Dead code goes into the
sibling refactor task — never a vague follow-up`) are the model. Rule paragraph,
then rationale paragraph naming the failure mode. Drop the "surfaced in tNNN /
the user pushed back at ExitPlanMode" narrative.

## Verification

- Every claim re-verified against current source before promotion; UNVERIFIABLE
  items are structurally ineligible for promotion and are listed as dropped.
- Every cited source path still exists:

```bash
missing=$(grep -o '`[^`]*\.\(sh\|py\|md\|json\|yaml\)`' aidocs/framework/planning_conventions.md |
          tr -d '`' | sort -u | while read -r f; do [ -e "$f" ] || echo "$f"; done)
[ -z "$missing" ] || { printf 'DEAD REFS:\n%s\n' "$missing" >&2; exit 1; }
```

- `bash tests/test_aidocs_pointer_parity.sh` passes.
- Every ruling journalled `state=done`, each PROMOTE/MERGE row carrying a
  verbatim >=40-char excerpt of the text actually written.
- Promoted memory files deleted and their `MEMORY.md` lines removed by matching
  the link target after re-reading the file — never by wholesale regeneration.
