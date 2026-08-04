---
priority: high
effort: high
depends: [t1405_3]
issue_type: documentation
status: Ready
labels: [documentation, docs]
gates: [risk_evaluated]
anchor: 1405
created_at: 2026-08-04 13:46
updated_at: 2026-08-04 13:46
---

## Context

Fourth child of t1405. Promotes the **derived-state & concurrency** cluster
(~21 memories) into a NEW doc,
`aidocs/framework/state_and_concurrency_conventions.md`.

Read first:
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan,
   which owns the per-memory decision gate, the store-concurrency rules, and the
   journal schema. Binding here; do not re-derive.
2. `aiplans/archived/p1405/p1405_1_*.md` — the frozen manifest and the triage
   table naming exactly which memories this child owns.

The store is outside the repo, so its deletions and `MEMORY.md` edits appear in
no git diff — say so in the Final Implementation Notes.

## Why a new doc

`code_conventions.md` is 1.7 KB about source-trace comments; absorbing 21
runtime-state rules would give it a mixed remit. `testing_conventions.md`
already owns *testing* a threading/asyncio migration — this doc owns *designing*
the state and concurrency itself. Cross-reference both, in both directions.

The new-file-vs-new-`##`-section rule written by t1405_1 in
`aidocs/framework/agent_memory_conventions.md` governs this decision — follow it
and cite it.

## Scope

Derived-state provenance stamps (persist the inputs alongside the values);
derived-tuple integrity (atomicity, digests, one validated reader); a per-tick
derived set is the sole source for every surface reading it, and counters
partition on the same precedence ladder; ephemeral derived per-task state stays
out of the task record (git-ignored registry instead); adding a human edit
surface over derived state (fallback asymmetry, resolver provenance, lock
reentrancy); partial-edit writer merge contracts (nested subkeys survive, omit
is not clear); replay/refresh rebuilds from the persisted record, never the
initiating arguments; a dedup key derived through two pipelines can differ for
identical content; merge/dedup degrades to conflict rather than a silent guess;
atomicity is not serialization (temp+replace removes torn reads, not lost
updates); fail-safe owner-token mutexes that never proceed unlocked; a fail-safe
arms where the lock is *acquired* and retires the generation; supersession-token
completeness (bump on every re-entry); prevent superseded work, do not merely
discard it; async seen/offered markers snapshot their trigger state before the
await; deferred-launch lifecycle (arm only on confirmed launch); reaper
ownership is repo-scoped; trigger/marker and invalid-state hygiene; passive
observation must not refresh staleness stamps; bounded recovery envelopes with
at-bound and over-bound tests.

**Check the sibling docs before adding a section** — grep `code_conventions.md`,
`testing_conventions.md` and `tui_conventions.md` for the rule first, so cluster
drift across six promotion children does not document it twice.

## Key files

- `aidocs/framework/state_and_concurrency_conventions.md` (NEW).
- `aidocs/framework/README.md` — add it to the **entrypoint-advertised** list.
- `CLAUDE.md` + the out-of-marker appendices in `AGENTS.md`,
  `.codex/instructions.md`, `.opencode/instructions.md` — add its trigger to all
  four surfaces, or `tests/test_aidocs_pointer_parity.sh` fails. The appendices
  go **after** the closing `<<<aitasks` marker only; never inside, and never in
  `seed/aitasks_agent_instructions.seed.md`.
- `.aitask-memtriage/t1405_4.tsv` — the rulings journal (git-ignored).

## House style (non-negotiable)

H1 title, then a preamble paragraph stating scope and pointing at sibling docs
for what lives elsewhere. Then one `##` per rule, the heading being **the rule
stated as a full sentence**, followed by a rule paragraph and a rationale
paragraph naming the failure mode. Drop the "surfaced in tNNN" narrative. See
`aidocs/framework/code_conventions.md` for the canonical entry shape and
`aidocs/framework/tmux_gateway.md` for a well-formed small doc.

## Verification

- Every claim re-verified against current source before promotion; UNVERIFIABLE
  items are structurally ineligible for promotion and are listed as dropped.
- Every cited source path still exists:

```bash
missing=$(grep -o '`[^`]*\.\(sh\|py\|md\|json\|yaml\)`' aidocs/framework/state_and_concurrency_conventions.md |
          tr -d '`' | sort -u | while read -r f; do [ -e "$f" ] || echo "$f"; done)
[ -z "$missing" ] || { printf 'DEAD REFS:\n%s\n' "$missing" >&2; exit 1; }
```

- `bash tests/test_aidocs_pointer_parity.sh` passes **with the new doc present**
  — that is the assertion proving all four surfaces got its trigger.
- `bash tests/test_agent_instructions.sh` passes (T21 marker survival).
- Every ruling journalled `state=done`, each PROMOTE/MERGE row carrying a
  verbatim >=40-char excerpt of the text actually written.
- Promoted memory files deleted and their `MEMORY.md` lines removed by matching
  the link target after re-reading the file — never by wholesale regeneration.
