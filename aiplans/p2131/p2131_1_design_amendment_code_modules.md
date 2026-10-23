---
Task: t2131_1_design_amendment_code_modules.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_2_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_1 — Proposal amendment for the code-module tier (coarse)

## Context

- **Parent goal.** t2131 adds a two-level code-module tier (module → submodule)
  to the test map. It is used as an on-demand selection widening and as a
  `module` completion mode.
- **This child.** It writes the parent plan's design defaults 1–13
  (`aiplans/p2131_testmap_code_modules_tier.md`) into the proposal
  `aidocs/testing_engine/n014_explorer_006_proposal.md`, so every later child
  implements against proposal text.
- **Wave:** now. It consumes no unlanded provider.

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first.** No verb, rule or gate may require a human action. Agent
output keeps `by:` provenance.

**Defaults consumed:** all of 1–13. The most delicate ones are **7** (reach)
and **11** (completion).

**Default 7 — reach.**
- **Mechanism.** The current graph only, and a transitive reverse closure over
  resolved edges.
- **Full fallback** on `deleted_path`, `renamed_path`, `unmapped_path`,
  `uncertain_reference` (any in-repo uncertainty, anywhere) or
  `modules_stale`.
- **Invariant.** The absence of a resolved edge is never proof of
  independence.
- **Recording.** Every fallback reason is recorded and measured.
- **Out of scope.** No historical graph and no per-language clearing. Smarter
  analysis goes under *Named follow-ups*, gated on the measured fallback share.

**Default 11 — `module` mode.**
- **Cadence.** A valid `full_run_every` is required; `cadence_declared`
  applies.
- **Decision order:**
  1. `NOT_YET` → full;
  2. the first `ADMISSIBLE` → engine approval in `costs/policy.yaml`;
  3. a due cadence trigger (ratio on the widened estimate) → full;
  4. an unmet criterion → `POLICY_DEMOTED:module->full|<criterion>`;
  5. a reach fallback → full with `widen_full:<reason>`;
  6. otherwise `module|next_full_in:<n>`.
- **Counters.** A full run resets them. M8.5's `cadence.go` is reused.
- **`auto`.** It never lands on `module` in v1.

The prose rename of M1–M10 (default 14) belongs to t2131_2. New prose here
already says "work package".

## Reading list

- The parent plan, sections *Design defaults* and *Decomposition*.
- Proposal: *Architecture* (Vocabulary ~163, registry directory ~344, *Where
  state lives* ~411, line-protocol index ~438).
- Proposal: *Design decisions* (~466).
- Proposal: *Module Map* (~650-889).
- Proposal: *Registry loader and writer* (~2195).
- Proposal: *Scoped-row registry and areas* (~2831-2941).
- Proposal: *Runner contract* (~2962).
- Proposal: *Selector* (~3266).
- Proposal: *Run Surface* (~1584-1805).
- Proposal: *Feedback tools* (~3388).
- Proposal: *Completion policy* (~1940, ~3847) and *Auto completion policy and
  cadence* (~3882).
- Proposal: *Onboarding verbs* (~3605).
- `aitasks/t1812_selective_testing_source_to_tests_map_graded_selection_runne.md:55-56`.
- The precedent: `aiplans/p1859_testmap_m8_completion_policy_and_gates.md`,
  "Post-approval sequence" step 0.

## Owned files / provides / consumes

- **Owns:** `aidocs/testing_engine/n014_explorer_006_proposal.md`, for this
  change.
- **Provides:** the proposal contract that every sibling reads. It also
  provides the contract notes to t1853, t1855, t1857, t1859_4, t1859_5 and
  t1854_11.
- **Consumes:** nothing unlanded.

## Step 0 — Reality check

1. Re-verify the cited line numbers. The proposal may have moved since
   ee468201f.
2. Grep that `M2.7`, the verb `modules` and the prefixes `MODULE:`,
   `MODULE_CONFLICT:`, `MODULE_UNRESOLVED:`, `MODULES_DRIFT`, `WIDENED:` and
   `WIDEN_FULL:` are unused.
3. Read the notes t1855, t1857 and t1859_4 already hold from t2131 (written at
   t2131's creation). The contract notes then add only what changed.
4. Check whether t2131_2 (the rename) has landed. If it has, use the new
   headings.
5. Record the outcome here before editing.

## Implementation steps (coarse)

1. **Vocabulary.** Add *code module / submodule* and *work package*.
2. **Design decision 20.** Code modules are data-derived logical groupings,
   not hand labels and not profile tiers. Widening is a cut knob applied after
   the graded walk. This is the re-check of t1812:55-56.
3. **Registry.**
   - the tree gains `_modules.yaml`;
   - *Where state lives*;
   - "eight tables" becomes nine; "two generated files" becomes three;
   - the reserved names.
4. **Line-protocol index rows.** Include the fallback-reason vocabulary.
5. **Work-package table.** Add the M2.7 row (`registry/modules*.go` +
   `internal/testmap/modules/**`) and the waves table entry.
6. **Verb list.** Add `+ modules`.
7. **New component *Code modules*.**
   - tables and ids;
   - providers and precedence (root `:` excluded; `MODULE_CONFLICT:`);
   - module → module `deps:`;
   - `MODULES_DRIFT`;
   - membership (default 8);
   - reach (default 7, verbatim rules);
   - widening (default 10).
8. **Areas.** `modules:` references; the codemap import writes refs and
   qualifies colliding child names. Record this as an M2.5 deviation.
9. **Selector / Run Surface / output contract.** `--widen`, the reason token,
   `WIDENED:` / `WIDEN_FULL:`, budget exemption, and the paired prediction
   record (plain + widen outcome + identity).
10. **Feedback tools.** Paired scoring per set, and `cadence_declared` for
    `module`.
11. **Completion policy.** The config block, the data-flow matrix, readiness
    `POLICY:`, and default 11's decision order.
12. **Runner contract.** `group_by: module|submodule` and `{module}`.
13. **Onboarding verbs.** A `MODULES:` summary and `MODULE_UNRESOLVED:` to-dos.
    The enabling write happens only after module-mode support exists.
14. **Named follow-ups.** Smarter reach, gated on the measured fallback share.
15. **Commit.** `documentation: Amend test-map proposal for the code-module
    tier (t2131_1)`.
16. **Contract notes** via `/aitask-note --from 2131_1`, carrying the commit
    SHA, hedged and advisory.

## Verification / acceptance

- Every new prefix appears in the line-protocol index.
- The verb list, the registry tree and the counts agree.
- Default 7's rule (current graph, full on uncertainty, recorded reasons, no
  historical graph, no clearing) is in the component text. Smarter analysis is
  listed under *Named follow-ups*.
- Default 10's paired record and default 11's decision order are stated.
- No section states a human-only step.
- `NOTE_APPENDED:` for every contract note.

## Step 9 reference

Shared post-implementation (task-workflow Step 9). Current branch, no merge.
