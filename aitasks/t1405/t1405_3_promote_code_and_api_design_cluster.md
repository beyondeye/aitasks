---
priority: high
effort: high
depends: [t1405_2]
issue_type: documentation
status: Ready
labels: [documentation, docs]
gates: [risk_evaluated]
anchor: 1405
created_at: 2026-08-04 13:45
updated_at: 2026-08-04 13:45
---

## Context

Third child of t1405. Promotes the **code & API design** cluster (~21 memories)
into `aidocs/framework/code_conventions.md`.

Read first:
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan,
   which owns the per-memory decision gate, the store-concurrency rules, and the
   journal schema. Binding here; do not re-derive.
2. `aiplans/archived/p1405/p1405_1_*.md` — the frozen manifest and the triage
   table naming exactly which memories this child owns.

The store is outside the repo, so its deletions and `MEMORY.md` edits appear in
no git diff — say so in the Final Implementation Notes.

## Scope

`code_conventions.md` is currently **1.7 KB with a single section** (source-trace
comments for condensed help text). It becomes the home for language-agnostic
code- and API-authoring rules:

abstraction-contract completeness; contract fields are never even temporarily
untrue; scope-honest helper naming + rich return values (which-items, not
booleans); a new optional param defaults from live state **inside** the helper,
not at call sites; multi-step cleanup is encapsulated in the model; reuse the
canonical seam instead of a parallel reimplementation; substrate-promotion
criteria; stable handle vs mutable manifest; bucketed check/config domains with
operation-qualified ids; name transitional duplication honestly; role-specific
eligibility (derive per role, exclude self); catch only the expected exception
and never fail open; enumerate every failure signal and assign the sentinel;
adding a mode means auditing the whole lifecycle; root-scoped APIs reject ambient
state; keys parsed from user-authored config are not strings; derive path
provenance lexically before `Path.resolve()`; derive lists from the canonical
site with a drift guard; prefer a structural fix over a fragile invariant;
per-surface labels over uniform identity; canonicalize identity keys on both
sides of a join.

**Add a preamble cross-pointer** to the new
`aidocs/framework/state_and_concurrency_conventions.md` (created by t1405_4),
matching how `code_conventions.md` already points at `sed_macos_issues.md` and
`shell_conventions.md`. The boundary: this doc is code/API authoring; that one is
runtime derived-state, locking and lifecycle.

**Check the sibling docs before adding a section.** Cluster boundaries can drift
across six promotion children — grep `testing_conventions.md`,
`planning_conventions.md` and `state_and_concurrency_conventions.md` for the rule
before writing it here, so the same convention is not documented twice.

## Key files

- `aidocs/framework/code_conventions.md` — the promotion target.
- `.aitask-memtriage/t1405_3.tsv` — the rulings journal (git-ignored).

## House style (non-negotiable)

One `##` per rule, the heading being **the rule stated as a full sentence**,
then a rule paragraph, then a rationale paragraph naming the failure mode. Drop
the "surfaced in tNNN / the user asked for X" narrative — cite task ids sparingly
as evidence anchors only. `code_conventions.md`'s existing single section is the
canonical shape to imitate.

## Verification

- Every claim re-verified against current source before promotion; UNVERIFIABLE
  items are structurally ineligible for promotion and are listed as dropped.
- Every cited source path still exists:

```bash
missing=$(grep -o '`[^`]*\.\(sh\|py\|md\|json\|yaml\)`' aidocs/framework/code_conventions.md |
          tr -d '`' | sort -u | while read -r f; do [ -e "$f" ] || echo "$f"; done)
[ -z "$missing" ] || { printf 'DEAD REFS:\n%s\n' "$missing" >&2; exit 1; }
```

- `bash tests/test_aidocs_pointer_parity.sh` passes.
- Every ruling journalled `state=done`, each PROMOTE/MERGE row carrying a
  verbatim >=40-char excerpt of the text actually written.
- Promoted memory files deleted and their `MEMORY.md` lines removed by matching
  the link target after re-reading the file — never by wholesale regeneration.
