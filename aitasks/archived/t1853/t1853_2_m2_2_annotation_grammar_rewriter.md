---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1853_1]
issue_type: feature
status: Done
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-11 17:42
updated_at: 2026-10-12 17:31
completed_at: 2026-10-12 17:31
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1853_1** id=2026-10-12T08:27:47Z.8817881ff7d750d7e23633a2 from=t1853_1 from_verified=yes at=2026-10-12T08:27:47Z base=c07193265578ec723aa5994ca4bf20ed5116222e base_branch=main dirty=yes host=omg16
>
> | M2.1 (registry core) landed in 0d04347ab; the scan/check contract is in the proposal at c07193265 (Enumeration and reconciliation). Advisory, as of that tree — your Reality check should re-verify.
> | 
> | What M2.2 plugs into:
> | - Implement registry.AnnotationSource: Annotations(ctx, root) ([]FileAnnotations, error), in goengines/internal/testmap/registry/inputs.go. FileAnnotations{Path; Units []UnitAnnotation{Member, Line, Covers []Cover{Source, Line, StampedAt, StampedBlob}}}. The file-level block is Member == "" and comes first; members follow in file order. Stamps arrive PARSED (StampedAt date, StampedBlob blob prefix); both empty = unstamped. The stamp format stays yours.
> | - Wire it by setting Annotations in testmapInputs() in goengines/cmd/ait-testmap/scancheck.go (the named extension point). Until it is set, scan and check exit 3 with INPUT_UNAVAILABLE:annotations.
> | - readInputs refuses invalid paths and members per the id grammar (registry.ParseID / CheckPath: no '#', '@', '|', whitespace; member has no '/'). An error from your source surfaces as INPUT_ERROR:annotations|<detail>, exit 3.
> | - scan --apply persists your covers to aitestmap/registry/_scanned.yaml. Member drift (UNANNOTATED_MEMBER applies only to files with at least one testmap:unit block; DEAD_MEMBER) refuses the write.
> | - Test pattern: drive the verbs through run() with t.Chdir and a swapped testmapInputs (see cmd/ait-testmap/scancheck_test.go TestInjectionProofThroughRun).

> **👁 note:read** id=2026-10-12T09:26:35Z.0a5dbb5819d1a95d7aa1be0d by=t1853_2 at=2026-10-12T09:26:35Z mode=explicit ids=2026-10-12T08:27:47Z.8817881ff7d750d7e23633a2

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T12:51:04Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-12T14:29:55Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-12T14:31:41Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:91e912fb2eee6fa5

> **✅ gate:risk_evaluated** run=2026-10-12T14:31:41Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1853_2/risk_evaluated_2026-10-12T14:31:41Z-risk_evaluated-a1.log`
