---
Task: t1853_1_m2_1_registry_core.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1853_1 — M2.1 Registry core

## Context

Parent goal: M2 — Registry and map model (everything that reads and writes
`aitestmap/` without running a test). This is **M2.1 Registry core**, wave
**A**: the loaded registry every other engine package reads, and the `scan` and `check` verbs. Providers: M1.2 (`t1852_2`, `33012bff7`, archived — not in `depends:`).

This coarse plan records what the proposal fixes for M2.1. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No verb, load rule or check rule shipped here may make a human
action a precondition of any path; `by: human:<email>` is an optional recorded
value, never a gate. A human-only step met in the proposal is reported to its
owning parent (note), never encoded here.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md` (M2 cut fixed in `3bc0de8ac`): Module Map `#### M2` row M2.1; *Registry loader and writer (M2.1 core)*; *Enumeration and reconciliation (M2.1)*; *Engine binary identity and budget* (the `scan` / `check` < 300 ms budget); *Architecture → The
registry directory, Where state lives, Line-protocol index*; *Invariants every
module honours*; *Assumptions → The map and freshness (M2, M4)* and *Variants,
broad tests and runners (M2, M3)*; *Tradeoffs → Map and registry structure
(M2, M3)*. Parent plan `aiplans/p1853_testmap_m2_registry_and_map_model.md`
(Deviations from the proposal). Engine rules: `goengines/README.md` ("Rules
for engine submodules", "Interfaces"). Owns cells read `internal/<pkg>` as
`goengines/internal/testmap/<pkg>`.

## Owned files / provides / consumes

- **Owns:** `goengines/internal/testmap/registry/**` (core: loader, merge rule, id grammar, edges / rules / waivers tables, `config.yaml` schema, sorted writer, `check` framework); the `scan` and `check` rows in `goengines/cmd/ait-testmap/verbs.go`; the `scan` / `check` lines in `goengines/bench/baseline.txt`.
- **Provides:** the loaded registry and id grammar (every engine package); `check`; two injection points — the annotation source (filled by M2.2) and the unit lister (filled by M3.1); table / rule registration points for M2.4, M2.5, M2.6.
- **Consumes:** M1.2: `internal/testmap` (`Contract`, `CheckContract`), `internal/lineproto`, `internal/gitx`, `internal/testmap/fixture`, `internal/benchgate`.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M2.1, its component
   subsections, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge target
   — verbs, line protocols, files, hooks and tests — and name the task and
   commit that landed each. The proposal and this coarse plan are claims to
   verify, never facts. Specifically:
- M1.2 provider surface: `testmap.CheckContract` signature, `lineproto` exit helpers, `fixture.New`, the verb-table row shape, `guards_test.go` rules, and whether `doublestar/v4` is already in `go.mod` (this child is likely its first importer for `exclude:` / `owns:` globs).
- Whether M3.1 or M2.2 have landed by pick time (if either has, wire its input instead of only a fixture).
   - The parent plan's *Repository reality anchors* (verified 2026-10-11 at
     `2fe3f8cb7`) — re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or decision breaks, hedging what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M2.1 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. Package `registry`: the id grammar `<path>[#<member>][@<variant>]` with a parser and golden table.
3. `config.yaml` schema with every key and default from *The registry directory* (canonical block), incl. `exclude:`, `docs:`, `notes:` (≤ 10 lines), `broad_threshold_s`, and the `completion` / `agent_review` / `readiness` / `conventions` / `helper_roots` blocks as typed data (their consumers come later).
4. Loader + one merge rule over `aitestmap/registry/*.yaml`; the edges / rules / waivers tables; `owns:` routing by glob; per-file `contract:` refusal through `CheckContract`; registration points for later tables.
5. Deterministic sorted writer that writes only on change.
6. `check` rule framework and the owned rules `STALE_PATH`, `UNSTAMPED` (past `bootstrap_until` under `require_stamp`), `UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNREGISTERED`, `UNMAPPED_ARTIFACT`; `exclude:` honoured; `--strict` semantics per the proposal.
7. `scan --apply` persisting `variants:` to `_scanned.yaml` over the two injected inputs (annotation source, unit lister), with fixture implementations for tests.
8. Replace the `scan` and `check` stub rows with `{Name, Run, Exits}`; add benchmarks and record their baselines (`go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`).

## Verification

- Golden tests for the core merges and the id grammar (member and variant fragments).
- One fixture per owned check rule.
- A newer `contract:` → `CONTRACT_MISMATCH` exit 3.
- Re-`scan --apply` with no change is byte-identical (sorted, written only on change).
- `exclude:` paths never listed and never `UNREGISTERED`.
- `scan --apply` persists `variants:` via a fixture lister; `UNMAPPED_ARTIFACT` via a fixture `artifact_glob:`.
- Bench `scan` / `check` < 300 ms on the aitasks shape, baseline recorded.
- `ait engine test` green; `go vet` clean; `guards_test.go` passes.
- `ait engine test` (`go vet` + `go test` over `goengines/`) green; the
  Invariants 4–5 tripwire in `goengines/guards_test.go` passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
