---
priority: medium
effort: medium
depends: [t1853_1, t1853_2]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-11 17:42
updated_at: 2026-10-11 17:42
---

## Context

Child **M2.6 — Adoption tables** of t1853 (test map, module M2). Wave **B**
(moved from E in the M2 cut fix: its consumers M4.1, M4.2, M4.4 and M8.2 are
waves C–D). The seeded-edge and adopted-edge rows the selector, `stale`,
`readiness` and the `onboard` verbs read and write. **Providers:** M2.1
(`t1853_1`) and M2.2 (`t1853_2`).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M2 cut fixed in `3bc0de8ac`) — Module Map row M2.6, components *Registry
loader and writer (M2.6 adoption tables)* and *Adoption ledger (M2.6 data)*,
*Architecture → Where state lives* (seed queue, adopted-edge provenance, phase
ledger rows), *The Adoption Model → The three states, with `by:`*. Parent
plan: `aiplans/p1853_testmap_m2_registry_and_map_model.md` (Deviations 1, 3, 8).

**Coarse plan only.** `aiplans/p1853/p1853_6_m2_6_adoption_tables.md` records
what the proposal fixes; its **Step 0 — Reality check** (mandatory, before any
code, recorded in the plan) inspects M2.1 and M2.2 as they landed, incl. the
post-re-stamp hook's actual shape.

## Scope (from the proposal, after the M2 cut fix)

- The `seeds` table (`registry/seeded.yaml`) and the `adopted` table
  (`registry/adopted.yaml`) in M2.1's loader, each with its own `contract:`.
- `onboard.yaml`'s `rejections[]`, `reviews[]`, `kind_proposals[]`,
  `calibration[]` as read tables.
- Load rules: `SEED_SHADOWED` (a seed whose `(test, covers)` is also a stamped
  edge is dropped and reported), `ADOPTED_ORPHAN`, absent-`by:`-is-human.
- The write routing API for every verb that touches the three files (`onboard
  seed`, `onboard adopt` forms, `annotate --author`, `onboard reject`,
  `attribute --propose`, re-stamps) — later verbs call it, never write around it.
- `SEEDED:<n>` and `ADOPTED:<n>|human <h>|agent <a>|auto <m>` on `check`.
- **Fills M2.2's post-re-stamp hook** in `annotate` / `verify` (named extension
  of M2.2): an automated re-stamp (agent or engine) refreshes the matching
  `adopted.yaml` row and keeps its `by:` — a machine claim is never turned into
  a reviewed edge; only an explicit human actor deletes the row.

## Key files to modify

- The two tables and the `onboard.yaml` reader in
  `goengines/internal/testmap/registry/` (named extension of M2.1).
- The hook fill in `goengines/internal/testmap/annot/` (named extension of M2.2).
- M2.1's `check` (the two count lines and the two load-rule reports).

## Reference files for patterns

- M2.1's `registry` (loader, merge, sorted writer); M2.2's `annot` (hook);
  `goengines/internal/testmap/contract.go`.

## Provides / consumes

- **Provides:** the seeded / adopted rows and the `seeded.yaml` schema (M4.1,
  M4.2, M4.4, M6.2, M6.3, M7.1, M7.2, M8.2); the write routing.
- **Consumes:** M2.1, M2.2.

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. Tables + `onboard.yaml` reader + load rules.
3. Write routing API; `check` lines.
4. The hook fill; command-level tests.

## Verification

- Goldens for the two adoption-table merges, the `by:` merge, the absent-`by:`
  rule and the shadow rule; `ADOPTED_ORPHAN`; per-file `contract:` refusal;
  the `SEEDED:` / `ADOPTED:` lines on `check`; write-routing unit tests per
  verb row.
- **Command-level re-stamp cases** through the real `verify` and `annotate`
  verbs, on a fixture with two `adopted.yaml` rows (the re-stamped edge and an
  unrelated one): an automated actor refreshes the matching row and keeps its
  `by:`; an explicit human actor deletes it; in both the unrelated row is
  byte-identical; re-stamping an edge with no provenance row leaves
  `adopted.yaml` untouched.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. `by: human:<email>` is an optional
recorded value, never a gate; no path shipped here waits on a person. The
absent-`by:`-is-human reading and person-only rejection are flagged to their
owning parents (M6, M7) for automation.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1853_1** id=2026-10-12T08:28:06Z.be97eda202d26ccbdfa49815 from=t1853_1 from_verified=yes at=2026-10-12T08:28:06Z base=c07193265578ec723aa5994ca4bf20ed5116222e base_branch=main dirty=yes host=omg16
>
> | M2.1 (registry core) landed in 0d04347ab; the proposal contract is at c07193265. Advisory, as of that tree; re-verify in your Reality check.
> | 
> | Registration points (goengines/internal/testmap/registry):
> | - Tables in hand files: RegisterHandTable(key, TableLoader). Until a submodule registers them, the keys scopes/areas are refused as REGISTRY_INVALID ("table ... not supported by this engine").
> | - Reserved files: RegisterFile(name, FileLoader). _scoped.yaml, areas.yaml, observed.yaml, seeded.yaml and adopted.yaml (and any other _-prefixed name) are refused until registered, never read as hand files. Each file passes testmap.CheckContract before its loader runs.
> | - Keep loaded data in Registry.Ext (map[string]any).
> | - Check rules: RegisterRule(CheckRule{Name, Patterns, Run}) from an init() in your own file; rules run in registration order. Run returns ([]Finding, error). Return an error, never a guess, when you cannot inspect: the run aborts with CHECK_ERROR exit 3 and never prints CHECK:. A rule that judges declared globs lists them in Patterns so it shares the run's single MatchFiles pass: a strict GlobWalk over an exclude-aware, no-follow view; existing files only.
> | - Severity: Always | StrictPastBootstrap | Info (an absent bootstrap_until means no bootstrap window).
> | - The one merge rule: a union of every file's rows in file-name order. owns: globs apply to source paths and are judged over concrete existing files.
> | 
> | For M2.6: seeded.yaml/adopted.yaml are reserved files, so register them. SEEDED:/ADOPTED: lines on check can be Info-severity findings or extra lines. The CHECK: summary line is printed last by cmd/ait-testmap/scancheck.go.

> **✉ note:t1853_2** id=2026-10-12T14:30:39Z.0a6ea01ed099fbc0dfd430ae from=t1853_2 from_verified=yes at=2026-10-12T14:30:39Z base=7229dee868985aafae8cd16e493614d1904311b5 base_branch=main dirty=no host=omg16
>
> | M2.2 (annotation grammar and rewriter) landed in f096db065; its contract is in the proposal at 7229dee86 (*Annotation scanner and rewriter*). Advisory, as of that tree — your Step 0 should re-verify.
> | 
> | The post-re-stamp hook you fill:
> | - annot.RegisterRestampHook(func(ctx context.Context, root string, actor annot.Actor, edges []annot.Restamp) error). Register it from an init in your own file under goengines/internal/testmap/annot: registry cannot import annot (annot imports registry).
> | - Restamp{Test registry.ID; Source, File string; Line int; Before, After annot.Stamp; State}, where State is added | restamped | current. "current" means the stamp already named the current blob, so the file was not touched — but a human `verify` still confirmed it.
> | - Actor{Kind: Unspecified|Human|Agent|Auto; Value}, from `--by human:<email>|agent:<s>|auto`. The default is agent:$AIT_AGENT_STRING, else Unspecified. Only Kind==Human is a person, so an absent actor never deletes provenance.
> | - The hook runs once per annotate/verify invocation, after every file was written, and does not run after any earlier error. A hook error is RESTAMP_HOOK_ERROR:<detail>, exit 3, and the test files stay written.
> | - For through-run() cases, cmd/ait-testmap/annotate_test.go registers a recording hook in an init (hookCalls / hookFail); reuse it.
> | 
> | No human-only step was met.

> **✉ note:t1853_3** id=2026-10-13T12:53:16Z.c584a001b50b8c3bd6cc1dfc from=t1853_3 from_verified=yes at=2026-10-13T12:53:16Z base=2c04a9639cc377ce62858e5af12bbc3a0f76412b base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_3 (M2.3), as landed in 2c04a9639. Verify against the code.
> | 
> | For M2.6 (the restamp hook): `annot.Restamp` now carries `Origin string` (json `origin,omitempty`). `annotate --from-body` stamps through `annot.AnnotateWith(…, AnnotateOptions{Origin: "scanner:from-body", Snapshot})`:
> | - the actor is `--by` if given, else `agent:$AIT_AGENT_STRING`, else `auto` (never human, never unspecified)
> | - every edge the hook receives has `Origin = scanner:from-body`
> | 
> | Plain `annotate` / `verify` pass an empty `Origin`. The hook could record the provenance so adoption tables can tell scanner-seeded covers from hand-written ones. No human-only step was needed in M2.3.

> **👁 note:read** id=2026-10-18T19:50:15Z.7cb33da91a0081cd6fa42dc9 by=t1853_6 at=2026-10-18T19:50:15Z mode=explicit ids=2026-10-12T08:28:06Z.be97eda202d26ccbdfa49815,2026-10-12T14:30:39Z.0a6ea01ed099fbc0dfd430ae,2026-10-13T12:53:16Z.c584a001b50b8c3bd6cc1dfc
