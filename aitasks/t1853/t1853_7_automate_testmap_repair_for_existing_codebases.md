---
priority: high
effort: high
depends: [t1853_1, t1853_2, t1853_3, t1853_4, t1853_5, t1853_6, t1854_1, t1859_2, t1859_3]
issue_type: feature
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-11 23:43
updated_at: 2026-10-19 15:44
---

## Goal

Implement the full automatic check → repair → recheck loop so an existing codebase can adopt `ait test` without a person fixing each test-map rule failure. Requested by the user during the t1853_1 shadow discussion on 2026-10-11; this is a sibling under t1853 and genuine new feature work.

Existing plans provide validators, annotation writers, scanners and adoption/review tools, but those pieces alone do not guarantee convergence after missing annotations or invalid ownership. Deliver the coordinator and any missing validated repair operations, then connect them to onboarding and ongoing task execution.

## Required behavior

- Inventory the existing test corpus, including files with no testmap annotations. Do not rely only on `UNANNOTATED_MEMBER`, which is conditional on a file already opting into member annotations, or only on the current task's changed files.
- Consume structured diagnostics from registry checks, enumeration and the `ait test` surface. Build a rule-to-repair matrix covering every rule reachable through the supported onboarding and maintenance flows. Include missing file/member annotations, unregistered tests and unmapped artifacts, missing/ambiguous/wrong ownership, stale or renamed paths/members, missing/stale stamps, generated scan drift, and scoped/area/variant/adoption-table consistency. Record the exact diagnostic and provider operation instead of inventing rule names.
- Correct ownership at the file declaration/area/scope level that actually owns the path. Registry ownership errors concern declared paths outside the applicable ownership or ambiguous owners; an arbitrary unreferenced source file lacking ownership is not automatically a failure. Infer narrow ownership from repository structure, test intent and existing declarations.
- Reuse M2.2's sole annotation rewriter, M2.3's scanner suggestions, M2.5's area/scoped operations and M2.6's write routing. Add deterministic validated mutation primitives where a rule currently has only detection. Preserve comment placement, unrelated content, exclusions and provenance.
- Let the coding-agent workflow reason about test assertions, intended coverage and ambiguous ownership; keep the Go engine deterministic and free of model invocation, agent launching or task/gate-ledger writes. Static imports alone are insufficient evidence to assert semantic coverage or refresh a review stamp.
- Support legacy tests through the onboarding/review/adoption path. Preserve M7.4 author annotation's change-surface boundary; do not silently expand it to the whole repository to backfill legacy tests.
- After each repair batch, reload and recheck the actual repository; repeat until no blocking test-map rule failures remain. Use bounded attempts, repeated-state/no-progress detection and resumable progress. Supported repairable fixtures must reach clean automatically without routine human prompts. Unresolvable conflicts, unreadable files, incompatible contracts or exhausted budgets remain failures with precise residual diagnostics and repair history, never false success or an infinite loop.
- Never achieve green by disabling checks/gates, weakening strictness, broadening ownership to catch-all globs, fabricating coverage/stamps or deleting valid tests. Successful map repair proceeds to the normal test execution and gate checks; passing map rules does not imply tests pass.
- Integrate the same coordinator into existing-codebase onboarding, explicit maintenance and task completion when test-map failures arise. Define unattended configuration, retry ownership, restart behavior and machine-readable outcomes. The gate's own retry count (including zero) is not a repair coordinator; avoid nested retry loops and stale success records.

## Dependencies and cross-references

Concrete `depends:` entries are t1853_1 (registry/check), t1853_2 (annotation rewriter), t1853_3 (scanner facts), t1853_4 (axes/variants), t1853_5 (scopes/areas), and t1853_6 (adoption tables). These are real provider tasks, not placeholders.

The following provider parents have not yet supplied their child IDs at creation time. Resolve each module to its actual active or archived child; never infer an ID from the module number. Add pending provider children to `depends:` while preserving existing edges; record landed providers and commits as satisfied.

| Required provider module | Parent task | Consumed seam / named extension |
|---|---|---|
| M3.1 | [t1854](../t1854_testmap_m3_runners_scheduling_and_cost.md) → **`t1854_1`** (pending; in `depends:` since t1854's coarse pass) | Runner-backed enumeration and member identity for whole-corpus reconciliation |
| M4.2 | [t1855](../t1855_testmap_m4_selection_freshness_and_feedback.md) | Staleness, retargeting and confirmation operations |
| M5.1 | [t1856](../t1856_testmap_m5_run_surface.md) | `ait test`, unannotated-test diagnostics and test execution handoff |
| M6.5 | [t1857](../t1857_testmap_m6_onboarding.md) | Onboarding skill integration after its inventory, seeding and adoption providers |
| M7.2, M7.4, M7.5 | [t1858](../t1858_testmap_m7_agent_review_and_author_annotation.md) | Agent verdict intake, author annotation boundary and legacy review workflow |
| M8.2, M8.3 | [t1859](../t1859_testmap_m8_completion_policy_and_gates.md) → **`t1859_2`**, **`t1859_3`** (pending; in `depends:` since t1859's coarse pass; the seeds step `t1859_6` is not consumed) | Check/freshness verifiers, failure handoff and revalidation |
| M9.1, M9.3 | [t1860](../t1860_testmap_m9_workflow_integration_skills_and_docs.md) | Task-workflow integration and maintenance skill extension |

**Dependency hold:** Postponed only because the provider child graph above cannot yet be fully encoded. During provider decomposition, fill the relevant child edges. Set Ready after every row is resolved to an explicit pending dependency or evidenced landed provider; Ready does not bypass those dependencies. Do not depend on whole module parents: their graph is cyclic and parent completion is too coarse. Base provider tasks must not depend back on this consumer; this task lands the later named integration extensions.

[t1863](../t1863_testmap_cross_linking_pass.md) must audit this supplementary sibling and its table as well as the original module rows. t1863 is a cross-reference, not an implementation dependency. [t1861](../t1861_testmap_m10_rollout_to_target_repositories.md) is the downstream rollout context; assess delivery requirements without rewriting foreign task dependencies.

## Assigned case: `UNSTAMPED` past bootstrap (from t1859, Dev 14)

`check` treats an annotation edge without a stamp as an always-failing
`UNSTAMPED` finding under `require_stamp` once `bootstrap_until` has passed,
even without `--strict` (`goengines/internal/testmap/registry/rules_core.go`
`checkUnstamped`). The two gates report it and hand it here; neither repairs
it:

- The autonomous lane of `testmap_fresh` (`t1859_3`) never invents a first
  stamp. It records `fail` with the `UNSTAMPED` pairs and a machine-readable
  handoff reason.
- `testmap_check` (`t1859_2`) fails with the same reason.

No policy demotion or further test run can supply the missing adoption, so
this task owns the repair. **Legitimate first-stamp adoption routes**, each
writing the stamp together with its `adopted.yaml` provenance:
- `annotate --author` for pairs on the task's change surface (M7.4);
- verdict adoption from engine-cut packets (M7.2);
- class `--auto` over a rule or measurement class (M6.3).

`--confirm-evidenced` is **not** a first-stamp route: it only re-stamps an
existing claim. Forbidden:
- inventing a stamp;
- extending `bootstrap_until` or flipping `require_stamp`;
- weakening or skipping the check.

**Rollout prerequisite:** unattended completion under `require_stamp: true`
past `bootstrap_until` requires this task to have landed. Until then, that
configuration fails loudly at the gates and never passes silently.

## Planning and ownership

Read the authoritative proposal `aidocs/testing_engine/n014_explorer_006_proposal.md`, the parent t1853 protocol, and the provider task/plan files above. This is user-requested cross-module follow-through beyond the original six M2 module rows; do not silently label it M2.7 or move workflow/model execution into registry code.

The implementation plan must begin with `Step 0 — Reality check`: inspect landed providers and commits, compare proposal/coarse plans/repository behavior, finalize the diagnostic-to-repair matrix, and record each file's owning module and this task's named extension. Update the proposal's module/interface cuts where needed and notify affected provider tasks. Include the documented user-facing entry points and skill-wrapper ports required by the final skill changes.

## Acceptance

- An integration fixture representing an existing mixed test corpus starts with absent annotations, uncovered members, missing/ambiguous ownership, renamed paths and scan drift. One unattended invocation repairs the supported failures, reaches a fresh clean check, and hands off to normal test execution without person-by-person fixes.
- Every rule in the matrix has meaningful coverage for a supported automated repair or a precisely classified terminal failure. Ownership choices and annotations reflect assertions and actual ownership rather than merely suppressing diagnostics.
- A second invocation on the clean fixture makes no changes. An interrupted run resumes without duplicate annotations, adoption rows or false gate success.
- Conflicting rewrites, no-progress cycles, unreadable inputs and incompatible contracts terminate within the configured budget and retain actionable failing diagnostics.
- Onboarding, maintenance and task-completion integration tests verify the same convergence semantics, legacy-file handling, change-surface boundaries and correct gate/test outcomes.
- **`UNSTAMPED` handoff integration scenario.** The fixture runs an autonomous
  profile with `require_stamp: true` past `bootstrap_until`:
  1. A task leaves an unstamped edge on its change surface.
  2. `testmap_fresh` records `fail` with the handoff.
  3. The coordinator adopts the edge through a legitimate first-stamp route.
  4. The **real** `testmap_check` verifier passes.
  5. `tests_pass` runs.

  Negative controls:
  - an edge with no legitimate route stays failing, with a precise residual
    diagnostic;
  - no run invents a stamp, extends `bootstrap_until`, flips `require_stamp`
    or skips a gate.
- User documentation explains adoption of an existing codebase, automatic repair behavior, configuration and residual failure reports. The dependency table and reciprocal references are reconciled with the final module ownership.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1853_3** id=2026-10-13T12:53:19Z.e2217e36399421a82a6ecf89 from=t1853_3 from_verified=yes at=2026-10-13T12:53:19Z base=2c04a9639cc377ce62858e5af12bbc3a0f76412b base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_3 (M2.3), as landed in 2c04a9639. Verify against the code.
> | 
> | For automated testmap repair: `deps.Suggest(ctx, root, test, opts)` (verb `annotate --suggest [--json] <test>[#member]`) is a scanner-suggestion source.
> | - It lists the test's direct deps, walking `helper_roots:` helpers, with origins, an anchor and new/covered state.
> | - `SUGGEST_REFUSED` covers excluded, missing, not-a-file and no-scanner.
> | 
> | For Kotlin members, `annotate --from-body <test>#<member>` writes covers automatically:
> | - through `annot.AnnotateWith` with `Origin: scanner:from-body`
> | - it resolves receiver-position extensions too
> | - `--dry-run` previews
> | - there is no confirmation step (user decision)
> | 
> | Only `Static()` deps are direct facts; closure-only edges are reachability. No human-only step was needed in M2.3.

> **✉ note:t1954_4** id=2026-10-14T18:37:23Z.fe785b193765227544ec6ff2 from=t1954_4 from_verified=yes at=2026-10-14T18:37:23Z base=f8d4b2ef54e729ae6e7ee76c1ba3f63395660f14 base_branch=main dirty=yes host=omg16
>
> | t1954 (multi-language annotation parsers) is complete. Report: aidocs/testing_engine/t1954_annotation_parser_research.md (sections 11 and 12). Verdict for the repair loop: action.
> | - The rule-to-repair matrix must class these files as terminal, classified failures, never as repair targets:
> |   - unsupported-language test files (annot.ErrNoLeader);
> |   - lexically uncertain files (annot.ErrUncertainContext);
> |   - BOM files with no slot (annot.ErrByteOrderMark).
> | - Sidecar-only annotations were evaluated and NOT adopted (report section 4.8). annot.Apply stays the sole writer, and no second writer is needed.
> | - Known Kotlin defect (t1990): Kotlin 2.2 multi-dollar strings can make the reader accept a write inside a raw string. Until t1990 lands, treat such files as a risk in any automated Kotlin repair.

> **✉ note:t1853_6** id=2026-10-19T09:18:17Z.91b4a10ad83982c004345234 from=t1853_6 from_verified=yes at=2026-10-19T09:18:16Z base=093d98a197a65931bdd6f104d4a919f965dfc0ee base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_6 (M2.6 adoption tables). It describes the tree as of aaeb10b0f, so verify it against the code.
> | 
> | `ADOPTED_ORPHAN:<test>|<source>` (Info) reports an adopted.yaml provenance row whose edge carries no stamp, for example after someone removes a covers line by hand. No verb repairs it yet.
> | 
> | A repair must go through M2.6's write routing:
> | - add a dedicated route (e.g. `RouteRepair`) allowing `DeleteAdopted` / `RemoveSeed` in `registry/adoption_write.go` (`routeOps` + `routeFileOrder`);
> | - never write the file directly.
> | 
> | Note that the routing preserves an unrecorded review record (a `verifies` adoption's replay data) into onboard.yaml `reviews[]` before deleting its carrier. A repair that deletes such a row will therefore also write onboard.yaml.

> **✉ note:t22_3** id=2026-10-29T22:22:20Z.4e7a89119df82798f5450f28 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:20Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
