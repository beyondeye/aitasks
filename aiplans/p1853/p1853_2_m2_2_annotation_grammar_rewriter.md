---
Task: t1853_2_m2_2_annotation_grammar_rewriter.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1853_2 — M2.2 Annotation grammar and rewriter

## Context

Parent goal: M2 — Registry and map model (everything that reads and writes
`aitestmap/` without running a test). This is **M2.2 Annotation grammar and rewriter**, wave
**A**: the `testmap:` grammar, the stamp format and the only writer of `testmap:` lines. Providers: M2.1 (`t1853_1`).

This coarse plan records what the proposal fixes for M2.2. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No verb, load rule or check rule shipped here may make a human
action a precondition of any path; `by: human:<email>` is an optional recorded
value, never a gate. A human-only step met in the proposal is reported to its
owning parent (note), never encoded here.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md` (M2 cut fixed in `3bc0de8ac`): Module Map row M2.2; *Annotation scanner and rewriter (M2.2)*; *Architecture → Vocabulary* (Edge, stamp); *The Adoption Model → Placement: comment lines only*; *Invariants* (6); `assumption_annotation_is_comment_only`; *Architecture → The
registry directory, Where state lives, Line-protocol index*; *Invariants every
module honours*; *Assumptions → The map and freshness (M2, M4)* and *Variants,
broad tests and runners (M2, M3)*; *Tradeoffs → Map and registry structure
(M2, M3)*. Parent plan `aiplans/p1853_testmap_m2_registry_and_map_model.md`
(Deviations from the proposal). Engine rules: `goengines/README.md` ("Rules
for engine submodules", "Interfaces"). Owns cells read `internal/<pkg>` as
`goengines/internal/testmap/<pkg>`.

## Owned files / provides / consumes

- **Owns:** `goengines/internal/testmap/annot/**` except the `--suggest` / `--from-body` arms (M2.3) and `--author` (M7.4); the `annotate` and `verify` rows in `verbs.go`; placement goldens per language; the annotation-source wiring into M2.1's `scan` (named extension of M2.1).
- **Provides:** the `testmap:` grammar, the stamp format `@<date>/<blob10>`, the rewriter API (M4.2, M6.3, M7.2, M7.4); the annotation source `scan` reads; the post-re-stamp hook M2.6 fills.
- **Consumes:** M2.1: the id grammar, the injection point for the annotation source; M1.2: `internal/gitx` (`BlobDigest`), fixtures.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M2.2, its component
   subsections, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge target
   — verbs, line protocols, files, hooks and tests — and name the task and
   commit that landed each. The proposal and this coarse plan are claims to
   verify, never facts. Specifically:
- M2.1 as landed: the annotation-source injection point's actual interface, the id-grammar API, the sorted writer.
- Whether M2.6 has landed (normally not — wave B): if it has, wire the hook to it now.
   - The parent plan's *Repository reality anchors* (verified 2026-10-11 at
     `2fe3f8cb7`) — re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or decision breaks, hedging what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M2.2 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. Grammar v3 parser: `testmap:unit` member blocks (file-level block first), every key (`kind`, `covers`, `area`, `scope`, `trigger`, `reads`, `axis`, `reviewed`, `runner` / `needs` / `batch`), per-language comment leaders, Python module docstrings read-only, unknown keys refused with a line number, `# Covers:` prose never matched.
3. Stamp format `@<date>/<blob10>` (parse + produce from `gitx.BlobDigest`).
4. Line-targeted rewriter by `(file, line, current text)` with `REWRITE_CONFLICT`; fixed per-language insertion positions.
5. `annotate <test> <source>…` and `verify` (re-stamps); a post-re-stamp hook in both carrying the re-stamped edges and the actor (no-op until M2.6 fills it).
6. Plug the annotation scanner into M2.1's `scan` as the annotation source.
7. Replace the `annotate` and `verify` stub rows; placement goldens.

## Verification

- Grammar parse goldens per language incl. the Python docstring read and `testmap:unit` block ownership.
- Unknown key refused with a line number.
- `REWRITE_CONFLICT` on a changed line.
- Placement goldens per language (bash after shebang + leading `#` block; Python `#` lines after the docstring, never inside it; Go after the package clause; Kotlin after imports / inside the member block).
- `git diff -w --ignore-blank-lines` on every rewritten fixture shows comments only.
- `# Covers:` prose never matched or rewritten.
- `verify` re-stamps; the hook fires with the re-stamped edges and the actor.
- `scan` over a fixture repo yields edges from annotations.
- `ait engine test` (`go vet` + `go test` over `goengines/`) green; the
  Invariants 4–5 tripwire in `goengines/guards_test.go` passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
