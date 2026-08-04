---
priority: high
effort: high
depends: [t1405_1]
issue_type: documentation
status: Ready
labels: [documentation, docs, testing]
gates: [risk_evaluated]
anchor: 1405
created_at: 2026-08-04 13:45
updated_at: 2026-08-04 13:45
---

## Context

Second child of t1405. Promotes the **testing & verification** cluster (~25
memories) from the per-user auto-memory store into
`aidocs/framework/testing_conventions.md`.

Read first, in this order:
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan.
   It owns the **per-memory decision gate** (three phases: re-verify -> user
   rules on every memory -> journal-then-execute), the **store-concurrency
   rules**, and the journal schema. All are binding here; do not re-derive them.
2. `aiplans/archived/p1405/p1405_1_*.md` — t1405_1's archived plan, which
   carries the frozen manifest and the triage table naming exactly which
   memories this child owns.

The store is at `~/.claude/projects/-home-ddt-Work-aitasks/memory/`, **outside
the repo** — its deletions and `MEMORY.md` edits appear in no git diff. Say so
in the Final Implementation Notes.

## Scope

`testing_conventions.md` is currently 3.6 KB with two sections
(threading/asyncio coverage; golden-file regression tests). It grows to ~25.

**The negative-control family is a MERGE, not six promotions.** Six near-
duplicate memories collapse into one coherent progression — harness-can-fail ->
test-discriminates -> one-mutation-per-test -> restore-without-`git checkout`:
`feedback_prove_test_harness_can_fail`,
`feedback_negative_control_for_structural_guards`,
`feedback_negctrl_proves_test_discriminates`,
`feedback_negctrl_failing_for_the_wrong_reason`,
`feedback_negctrl_one_mutation_per_test`,
`feedback_negctrl_restore_without_git_checkout`.
Record the source -> merged `doc#heading` mapping for every one of them; t1405_7
needs it to rewrite `[[wikilinks]]`.

Also in this cluster: independent ground truth; probe the real class not a
replica; test the real entry point + live acceptance; test a universal claim at
its weakest surface; test specs must be executable; run every verification
command before relying on it; seed state before asserting cleanup; drive the
uninstalled backend deterministically; isolation needs a refusal guard; guard/
probe robustness; impact surveys must discriminate on the changed dimension;
behavioral verify fixtures + autonomous manual verification; characterization
flip contract with deterministic contention; shell-command tests + subprocess
hygiene; real-platform semantics over fake-shaped tests; perf-gate measurement
contract.

### The known-stale exemplar

`project_python_runner_k_filter_runs_nothing` is the memory that motivated
t1405: it asserted the framework venv has no pytest, which became false when the
dev tier landed. Promote **only the half that is still true** (`-k` silently runs
zero tests on the `unittest` fallback; a positional test path *widens* the run
rather than narrowing it), drop the pytest-absent premise, and check what
CLAUDE.md's Testing section already documents so the rule is not written twice.

## Key files

- `aidocs/framework/testing_conventions.md` — the promotion target.
- `.aitask-memtriage/t1405_2.tsv` — the rulings journal (git-ignored).

## House style (non-negotiable)

One `##` per rule, the heading being **the rule stated as a full sentence**
(e.g. `## Dead code goes into the sibling refactor task — never a vague
follow-up`), then a rule paragraph, then a rationale paragraph naming the
failure mode. Drop the "surfaced in tNNN / the user rejected X at ExitPlanMode"
narrative — convention docs cite task ids sparingly, as evidence anchors only.
See `aidocs/framework/code_conventions.md` for the canonical single-entry shape.

## Verification

- Every claim re-verified against current source before promotion; anything
  UNVERIFIABLE is structurally ineligible for promotion (see the parent plan's
  gate) and is listed as dropped in the Final Implementation Notes.
- Every cited source path still exists:

```bash
missing=$(grep -o '`[^`]*\.\(sh\|py\|md\|json\|yaml\)`' aidocs/framework/testing_conventions.md |
          tr -d '`' | sort -u | while read -r f; do [ -e "$f" ] || echo "$f"; done)
[ -z "$missing" ] || { printf 'DEAD REFS:\n%s\n' "$missing" >&2; exit 1; }
```

- `bash tests/test_aidocs_pointer_parity.sh` still passes (t1405_1 widened the
  `testing_conventions.md` trigger in CLAUDE.md; confirm it still matches).
- Every ruling journalled `state=done`, each PROMOTE/MERGE row carrying a
  verbatim >=40-char excerpt of the text actually written.
- Promoted memory files deleted and their `MEMORY.md` lines removed **by
  matching the line's link target after re-reading the file** — never by
  regenerating the index from a remembered list (a concurrent writer may have
  added lines).
