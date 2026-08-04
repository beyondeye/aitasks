---
Task: t1405_7_promote_docs_gates_shared_checkout_and_final_sweep.md
Parent Task: aitasks/t1405_triage_agent_memory_store_into_aidocs.md
Sibling Tasks: aitasks/t1405/t1405_*.md
Archived Sibling Plans: aiplans/archived/p1405/p1405_*_*.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# p1405_7 — Docs, gates, shared-checkout hazards, and the final sweep

## Context

The last child of t1405. It promotes three remaining clusters (~22 memories) and
then runs the **store-wide acceptance sweep** that closes the whole task.

**Read first, in order:**
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan.
   It owns the per-memory decision gate, the store-concurrency rules, the
   journal schema, the size-ceiling ladder, and the **verbatim acceptance
   script**. Binding here; do not re-derive.
2. `aiplans/archived/p1405/p1405_1_*.md` — the frozen manifest, the pinned 148
   baseline, and the named post-freeze arrivals.
3. The archived plans and journals of t1405_2..t1405_6 — they carry the
   `doc#heading` destinations this child needs for the wikilink rewrite.

The store is outside the repo: its deletions and `MEMORY.md` rewrite appear in
no git diff. Say so in the Final Implementation Notes.

## Part A — promotions

Run the parent plan's three-phase gate over this child's cluster, journalling to
`.aitask-memtriage/t1405_7.tsv`. Targets:

- `aidocs/framework/documentation_conventions.md` (~9). Its preamble currently
  scopes it to **user-facing** prose; if the additions widen that scope, update
  the preamble in the same edit rather than leaving it contradicted.
- `aidocs/gates/` (4). The directory exists — extend the right file there rather
  than minting a new one.
- `aidocs/framework/concurrent_agent_sessions.md` (NEW, 9). The five
  `project_concurrent_*` memories MERGE into one coherent doc, plus four related
  git/worktree hazards. Framework-level, not operator-level: the framework spawns
  parallel agents by design. Add it to `README.md`'s **entrypoint-advertised**
  list and give it a trigger in `CLAUDE.md` and all three out-of-marker
  appendices, or the parity guard fails.

## Part B — the final sweep

1. **Account for every manifest memory.** Diff executed dispositions against the
   `ruled` column across all seven journals. Anything unruled is **reported, not
   guessed at**. Post-freeze arrivals are listed separately as out of scope.
2. **Rewrite dangling `[[wikilinks]]`.** 140 of 149 files carried them across 82
   distinct targets, so mass deletion strands links that recall follows. Replace
   each link to a promoted/merged memory with its journalled `doc#heading` — the
   exact absorbing section, never a bare filename — and clear the 3 links that
   were already dangling before the task started. Verify every destination
   resolves: the file exists **and** the heading is present.
3. **Regenerate `MEMORY.md` from disk truth** (`ls *.md`), never from a
   remembered list. For the ≤10 KB criterion follow the parent plan's ladder:
   measure → hook-compaction (deletes nothing, overrides no ruling) → an explicit
   user choice between amending the ceiling and re-ruling. A KEEP ruling is never
   overridden to hit a number; an approved override is recorded as
   `.aitask-memtriage/size_override_approved`.
4. **Write and run the acceptance script.** Copy the parent plan's script
   verbatim to `.aitask-memtriage/t1405_accept.sh`. It uses an `rc` accumulator
   so every check sets a non-zero exit — printing a diagnostic and returning 0 is
   the exact failure mode this task guards against.

## Proving the checker can fail

**One mutation per run** — a run bundling several mutations only proves the
checks that happen to discriminate and lets the others pass inert. Drive it
through the `T1405_STORE` / `T1405_JOURNAL` / `T1405_REPO` env overrides against
throwaway fixture copies. **Never copy the repo**: every mutation lands in the
fixture store or fixture journal, so the `cp -a` worktree-pointer hazard never
arises. Reset from a pristine copy between runs — never `git checkout --`.

| # | Single mutation | Must exit 1 naming |
|---|---|---|
| 0 | none (baseline) | nothing — must exit **0**, or every result below is meaningless |
| 1 | delete one line from the fixture `MEMORY.md` | `MEMORY.md index vs disk mismatch` |
| 2 | add `[[no_such_memory]]` to one surviving file | `dangling wikilinks` |
| 3 | flip one journal row's `state` from `done` to `ruled` | `rulings never executed to completion` |
| 4 | corrupt one PROMOTE row's excerpt (col 6) | `excerpt for '<name>' not found under …` |
| 5 | delete one manifest name's journal row | `manifest entries with no ruling` |

A negative control that **passes** means the check is wrong, not the store — and
a failure must name *that* mutation, not merely exit non-zero, or a different
check is masking it.

## Verification

```bash
bash .aitask-memtriage/t1405_accept.sh     # prints "t1405 ACCEPTANCE: PASSED", exits 0
bash tests/test_aidocs_pointer_parity.sh
bash tests/test_agent_instructions.sh
./ait setup && git diff --stat AGENTS.md .codex/instructions.md .opencode/instructions.md
```

All six negative-control runs must have exited as specified before the passing
acceptance run is trusted.

## Risk

### Code-health risk: medium
- The new `concurrent_agent_sessions.md` misses one of the five merged sources,
  losing a hazard · severity: medium · → mitigation: the journal records the
  source → merged `doc#heading` mapping for each, and acceptance check 6 asserts
  every excerpt landed inside its section span
- Pointers land inside the `>>>aitasks` markers or in the seed · severity: high ·
  → mitigation: append after `<<<aitasks` only; the `./ait setup` diff is a
  required verification step

### Goal-achievement risk: high
- The acceptance script passes on a broken end state · severity: high · →
  mitigation: six one-mutation-per-run negative controls, each asserting its own
  message, plus a baseline that must exit 0
- Wikilinks are rewritten to destinations that do not resolve · severity:
  medium · → mitigation: acceptance check 6 requires the heading to exist and the
  excerpt to be inside its span, not merely somewhere in the file
- KEEP rulings push `MEMORY.md` over 10 KB and the task stalls · severity:
  medium · → mitigation: the decided three-step ladder ends on an explicit user
  decision, never silently over and never by overriding a ruling

### Planned mitigations
None as separate tasks — each mitigation is an in-scope step above.
