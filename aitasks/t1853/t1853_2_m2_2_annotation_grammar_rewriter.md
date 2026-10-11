---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-11 17:42
updated_at: 2026-10-11 17:42
---

## Context

Child **M2.2 — Annotation grammar and rewriter** of t1853 (test map, module
M2). Wave **A**. The only writer of `testmap:` lines and the owner of the stamp
format. **Provider:** M2.1 (`t1853_1`).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M2 cut fixed in `3bc0de8ac`) — Module Map row M2.2, component *Annotation
scanner and rewriter (M2.2)*, *Architecture → Vocabulary* (Edge, stamp),
*The Adoption Model → Placement: comment lines only*, *Invariants* (6),
*Assumptions → `assumption_annotation_is_comment_only`*. Parent plan:
`aiplans/p1853_testmap_m2_registry_and_map_model.md` (Deviations 2, 4, 8).

**Coarse plan only.** `aiplans/p1853/p1853_2_m2_2_annotation_grammar_rewriter.md`
records what the proposal fixes; its **Step 0 — Reality check** (mandatory,
before any code, recorded in the plan) inspects M2.1 as it landed.

## Scope (from the proposal, after the M2 cut fix)

- Grammar v3: `testmap:unit <Member>` blocks (a file-level block precedes the
  first unit) and every key — `kind`, `covers <path> @<date>/<blob10>`, `area`,
  `scope`, `trigger`, `reads <glob>`, `axis <axis>.<facet>=<value>`, `reviewed`,
  `runner` / `needs` / `batch`; per-language comment leaders; Python module
  docstrings read, never written; unknown keys refused with a line number.
- The stamp format `@<date>/<blob10>`.
- The line-targeted rewriter editing by `(file, line, current text)`,
  `REWRITE_CONFLICT`; fixed per-language insertion positions (bash after the
  shebang and leading `#` block; Python `#` lines after the module docstring;
  Go after the package clause; Kotlin after the import block or inside the
  member's `testmap:unit` block).
- `annotate <test> <source>…` and `verify` (re-stamps).
- A **post-re-stamp hook** in `annotate` and `verify`, carrying the re-stamped
  edges and the actor, which M2.6 fills (provenance rule by actor).
- The annotation source that M2.1's `scan` reads.
- `# Covers:` prose headers never matched and never rewritten.
- Not here: `annotate --suggest` / `--from-body` (M2.3's arms), `--author`
  (M7.4's arm).

## Key files to modify

- `goengines/internal/testmap/annot/**` — new package (owned, minus the three
  later arms).
- `goengines/cmd/ait-testmap/verbs.go` — replace only the `annotate` and
  `verify` stub rows.
- The annotation-source wiring into M2.1's `scan` (named extension).

## Reference files for patterns

- M2.1's `registry` package (id grammar, injection points);
  `goengines/internal/gitx/blob.go` (`BlobDigest`);
  `goengines/internal/testmap/fixture/`.

## Provides / consumes

- **Provides:** the `testmap:` grammar, the stamp format, the rewriter API
  (M4.2, M6.3, M7.2, M7.4); the annotation source for `scan`; the hook M2.6
  fills.
- **Consumes:** M2.1.

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. Grammar parser per language; stamp format.
3. Rewriter + placement; `annotate`, `verify`, the hook; `scan` wiring.
4. Goldens.

## Verification

- Grammar parse goldens per language incl. the Python docstring read and
  `testmap:unit` block ownership; unknown key refused with a line number;
  `REWRITE_CONFLICT` on a changed line; placement goldens per language;
  `git diff -w --ignore-blank-lines` shows comments only; `# Covers:` prose
  never matched or rewritten; `verify` re-stamps; the hook fires with the
  re-stamped edges and the actor.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. No path shipped here may make a
human action a precondition; the actor passed to the hook is data, not a gate.
