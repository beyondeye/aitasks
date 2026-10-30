---
priority: high
effort: high
depends: [t1853_1, t1853_2, t1853_3, t1853_4, t1853_5, t1853_6, t1854_1, t1859_2, t1859_3]
xdeps: [t59_1]
xdeprepo: aitasks_go
issue_type: feature
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-11 23:43
updated_at: 2026-10-30 12:09
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t59_1
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Implement the full automatic check → repair → recheck loop so an existing
codebase can adopt `ait test` without a person fixing each test-map rule
failure. Requested by the user during the t1853_1 shadow discussion on
2026-10-11; this is a sibling under t1853 and genuine new feature work.

Since the t22 cutover the loop is split across two repositories:
- **Engine half, aitasks_go#t59_1 (aitasks_go):** the deterministic Go repair
  coordinator, the rule-to-repair matrix and the missing validated mutation
  primitives (`RouteRepair`, ownership correction, rename retarget,
  scan-drift apply, `MODULE_*` handling, terminal classes). It never invokes
  a model, launches agents or writes task / gate ledgers.
- **Framework half, this task:** the agent-reasoning lane and the
  integrations. It connects the coordinator to onboarding, explicit
  maintenance and ongoing task execution, and owns the gate handoff, skills,
  configuration, documentation and proposal updates.

This task holds `xdeps` on aitasks_go#t59_1 (`xdeprepo: aitasks_go`), which
unblocks only when that task is Done: the framework half wires and documents
the coordinator the engine half actually lands.

## Required behavior (framework half)

- **Agent-reasoning lane.** Let the coding-agent workflow reason about test
  assertions, intended coverage and ambiguous ownership, and feed its
  conclusions to the engine as proposals or verdicts. Static imports alone
  are insufficient evidence to assert semantic coverage or refresh a review
  stamp. Ownership inference from "test intent" is done here; deterministic
  structure-based inference is the engine half's.
- **Diagnostics from the `ait test` surface.** The `ait test` front
  diagnostics (such as `UNANNOTATED_TEST`, M5.1) reach the coordinator
  through the workflow; registry-check and enumeration diagnostics are
  consumed by the engine half directly.
- **Integration.** Integrate the same coordinator into existing-codebase
  onboarding (the M6.5 onboarding skill), explicit maintenance (the M9.3
  maintenance skill) and task completion (the M9.1 path and its gates) when
  test-map failures arise. Successful map repair proceeds to the normal test
  execution and gate checks; passing map rules does not imply tests pass.
- **Gate handoff and retries.** Wire the `testmap_check` / `testmap_fresh`
  handoff (t1859_2 / t1859_3). The gate's own retry count (including zero) is
  not a repair coordinator; avoid nested retry loops and stale success
  records. No run may produce a false gate success.
- **Unattended configuration.** Define the profile / `project_config.yaml`
  configuration, retry ownership and restart behaviour on the workflow side.
  The machine-readable outcomes, resume state and engine `config.yaml` keys
  are the engine half's; consume them as landed.
- **Legacy tests.** Support legacy tests through the onboarding / review /
  adoption skills. Preserve M7.4 author annotation's change-surface boundary;
  do not silently expand it to the whole repository to backfill legacy tests.
- **Never achieve green** by disabling checks / gates, weakening strictness,
  broadening ownership to catch-all globs, fabricating coverage / stamps or
  deleting valid tests. On this side that means: no skipped gate, no flipped
  `require_stamp`, no extended `bootstrap_until`.
- **Skills and docs.** Add the skill-wrapper ports and permission
  touchpoints for any new engine verb, the documented user-facing entry
  points, and user documentation (website).

## Dependencies and cross-references

Concrete `depends:` entries are t1853_1 – t1853_6 and t1854_1 (all archived,
kept as satisfied), and t1859_2 / t1859_3 (the M8.2 / M8.3 gate verifiers,
pending). The engine half is held through `xdeps` on aitasks_go#t59_1.

The following framework provider parents have not yet supplied their child
IDs. Resolve each module to its actual active or archived child; never infer
an ID from the module number. Add pending provider children to `depends:`
while preserving existing edges; record landed providers and commits as
satisfied.

| Required provider module | Parent task | Consumed seam / named extension |
|---|---|---|
| M5.1 | [t1856](../t1856_testmap_m5_run_surface.md) | `ait test`, unannotated-test diagnostics and test execution handoff |
| M6.5 | [t1857](../t1857_testmap_m6_onboarding.md) | Onboarding skill integration after its inventory, seeding and adoption providers |
| M7.5 | [t1858](../t1858_testmap_m7_agent_review_and_author_annotation.md) | Legacy review workflow (the review skill) |
| M8.2, M8.3 | [t1859](../t1859_testmap_m8_completion_policy_and_gates.md) → **`t1859_2`**, **`t1859_3`** (pending, in `depends:`; the seeds step `t1859_6` is not consumed) | Check/freshness verifiers, failure handoff and revalidation (e.g. `.aitask-scripts/aitask_gate_testmap_check.sh`) |
| M9.1, M9.3 | [t1860](../t1860_testmap_m9_workflow_integration_skills_and_docs.md) | Task-workflow integration and maintenance skill extension |

The engine providers this repair needs (M4.2 staleness / retargeting /
confirmation, M6.3 class `--auto`, M7.2 verdict intake, M7.4 author
annotation boundary) are consumed by aitasks_go#t59_1, not here; they live in
aitasks_go#t61, aitasks_go#t63 and aitasks_go#t64 (not yet decomposed). This task reaches
them through aitasks_go#t59_1.

**Dependency hold:** Postponed because the framework provider child graph
above cannot yet be fully encoded, and because the engine half must land
first (the `xdeps` above). During provider decomposition, fill the relevant
child edges. Set Ready after every row is resolved to an explicit pending
dependency or evidenced landed provider; Ready does not bypass those
dependencies, and the `xdeps` keeps it blocked until aitasks_go#t59_1 is Done. Do
not depend on whole module parents: their graph is cyclic and parent
completion is too coarse. Base provider tasks must not depend back on this
consumer; this task lands the later named integration extensions.

[t1863](../t1863_testmap_cross_linking_pass.md) must audit this supplementary
sibling and its table as well as the original module rows, across both
repositories. t1863 is a cross-reference, not an implementation dependency.
[t1861](../t1861_testmap_m10_rollout_to_target_repositories.md) is the
downstream rollout context; assess delivery requirements without rewriting
foreign task dependencies.

## Assigned case: `UNSTAMPED` past bootstrap (from t1859, Dev 14)

`check` treats an annotation edge without a stamp as an always-failing
`UNSTAMPED` finding under `require_stamp` once `bootstrap_until` has passed.
The two gates report it and hand it to this repair; neither repairs it:

- The autonomous lane of `testmap_fresh` (`t1859_3`) never invents a first
  stamp. It records `fail` with the `UNSTAMPED` pairs and a machine-readable
  handoff reason.
- `testmap_check` (`t1859_2`) fails with the same reason.

This task owns the workflow side of the repair: it routes the handoff to the
engine coordinator (aitasks_go#t59_1), which adopts through a legitimate
first-stamp route (`annotate --author` on the change surface (M7.4), verdict
adoption from engine-cut packets (M7.2), or class `--auto` (M6.3)). For the
M7.2 route, the agent that produces the verdicts runs here. Forbidden:
- inventing a stamp;
- extending `bootstrap_until` or flipping `require_stamp`;
- weakening or skipping the check or any gate.

**Rollout prerequisite:** unattended completion under `require_stamp: true`
past `bootstrap_until` requires both halves of this repair to have landed
before the t1861 rollout. Until then, that configuration fails loudly at the
gates and never passes silently.

## Planning and ownership

Read the authoritative proposal `aidocs/testing_engine/n014_explorer_006_proposal.md`,
the parent t1853 protocol, and the provider task/plan files above, plus the
landed aitasks_go#t59_1 in aitasks_go. This is user-requested cross-module
follow-through beyond the original six M2 module rows; do not silently label
it M2.7 or move workflow/model execution into registry code.

The implementation plan must begin with `Step 0 — Reality check`: inspect
the landed providers and commits (the engine coordinator in aitasks_go, the
gates and skills here), compare proposal/coarse plans/repository behavior,
take the finalized diagnostic-to-repair matrix from aitasks_go#t59_1 and
cross-check every skill-reachable rule against it, and record each file's
owning module and this task's named extension. Update the proposal's
module/interface cuts where needed and notify affected provider tasks (in
aitasks_go with `--project aitasks_go`). Include the documented user-facing
entry points and skill-wrapper ports required by the final skill changes.

## Acceptance

- **Handoff.** On the mixed existing-corpus fixture, the coordinator's clean
  result hands off to normal test execution (`ait test`) without
  person-by-person fixes.
- **Judgement.** Ownership choices and annotations made through the agent
  lane reflect assertions and actual ownership rather than merely suppressing
  diagnostics.
- **No false gate success.** An interrupted run never leaves a stale or false
  gate success record.
- Onboarding, maintenance and task-completion integration tests (bash /
  skill goldens) verify the same convergence semantics, legacy-file handling,
  change-surface boundaries and correct gate/test outcomes.
- **`UNSTAMPED` handoff integration scenario.** The fixture runs an
  autonomous profile with `require_stamp: true` past `bootstrap_until`:
  1. A task leaves an unstamped edge on its change surface.
  2. `testmap_fresh` records `fail` with the handoff.
  3. The coordinator (aitasks_go#t59_1) adopts the edge through a legitimate
     first-stamp route.
  4. The **real** `testmap_check` verifier passes.
  5. `tests_pass` runs.

  Negative controls: no run invents a stamp, extends `bootstrap_until`, flips
  `require_stamp` or skips a gate.
- User documentation explains adoption of an existing codebase, automatic
  repair behavior, configuration and residual failure reports.
- The dependency table and reciprocal references are reconciled with the
  final module ownership across both repositories (with t1863).
- This body points to aitasks_go#t59_1 (done above).

## Carried obligations (framework half)

- `## Goal` ¶1 — "Implement the full automatic check → repair → recheck loop" — *Goal*: the agent / workflow driver here, the loop engine in aitasks_go#t59_1.
- `## Goal` ¶2 — "then connect them to onboarding and ongoing task execution" — *Required behavior → Integration*.
- `## Required behavior` — "Consume structured diagnostics from registry checks, enumeration and the `ait test` surface" — *Required behavior → Diagnostics from the `ait test` surface*.
- `## Required behavior` — "Correct ownership at the file declaration/area/scope level … Infer narrow ownership from repository structure, test intent and existing declarations" — *Required behavior → Agent-reasoning lane* (test intent); structure-based inference is aitasks_go#t59_1's.
- `## Required behavior` — "Let the coding-agent workflow reason about test assertions, intended coverage and ambiguous ownership" — *Required behavior → Agent-reasoning lane*.
- `## Required behavior` — "Support legacy tests through the onboarding/review/adoption path. Preserve M7.4 author annotation's change-surface boundary" — *Required behavior → Legacy tests* (skill path); the engine route boundary is aitasks_go#t59_1's.
- `## Required behavior` — "Never achieve green by disabling checks/gates, weakening strictness, broadening ownership to catch-all globs, fabricating coverage/stamps or deleting valid tests" — *Required behavior → Never achieve green* and the *Acceptance* negative controls.
- `## Required behavior` — "Successful map repair proceeds to the normal test execution and gate checks" — *Required behavior → Integration* and *Acceptance → Handoff*.
- `## Required behavior` — "Integrate the same coordinator into existing-codebase onboarding, explicit maintenance and task completion" — *Required behavior → Integration*.
- `## Required behavior` — "Define unattended configuration, retry ownership, restart behavior and machine-readable outcomes" — *Required behavior → Unattended configuration* (profile / config, retry ownership, restart); outcomes and resume state are aitasks_go#t59_1's.
- `## Required behavior` — "The gate's own retry count … is not a repair coordinator; avoid nested retry loops and stale success records" — *Required behavior → Gate handoff and retries*.
- `## Dependencies` table — M5.1 (t1856) "`ait test`, unannotated-test diagnostics and test execution handoff" — *Dependencies* table, M5.1 row.
- `## Dependencies` table — M6.5 (t1857) "Onboarding skill integration" — *Dependencies* table, M6.5 row.
- `## Dependencies` table — M7.2, M7.4, M7.5 (t1858) "Agent verdict intake, author annotation boundary and legacy review workflow" — *Dependencies* table, M7.5 row (the review skill); M7.2 / M7.4 are consumed by aitasks_go#t59_1.
- `## Dependencies` table — M8.2, M8.3 → `t1859_2`, `t1859_3` "Check/freshness verifiers, failure handoff and revalidation" — *Dependencies* table, M8.2 / M8.3 row; kept in `depends:`.
- `## Dependencies` table — M9.1, M9.3 (t1860) "Task-workflow integration and maintenance skill extension" — *Dependencies* table, M9.1 / M9.3 row.
- `## Dependencies` — "**Dependency hold:** Postponed only because the provider child graph … cannot yet be fully encoded … Set Ready after every row is resolved" — *Dependency hold* (framework provider rows, plus the `xdeps` on aitasks_go#t59_1).
- `## Dependencies` — "Do not depend on whole module parents … Base provider tasks must not depend back on this consumer" — *Dependency hold*, last sentences.
- `## Dependencies` — "[t1863] must audit this supplementary sibling and its table" — *Dependencies and cross-references*, t1863 paragraph.
- `## Dependencies` — "[t1861] is the downstream rollout context" — *Dependencies and cross-references*, t1861 paragraph.
- `## Assigned case: UNSTAMPED` — "`testmap_fresh` (`t1859_3`) … records `fail` with the `UNSTAMPED` pairs and a machine-readable handoff reason" — *Assigned case*, first bullet.
- `## Assigned case: UNSTAMPED` — "`testmap_check` (`t1859_2`) fails with the same reason" — *Assigned case*, second bullet.
- `## Assigned case: UNSTAMPED` — "this task owns the repair" — *Assigned case*: the workflow handoff here, the engine adoption in aitasks_go#t59_1.
- `## Assigned case: UNSTAMPED` — route "verdict adoption from engine-cut packets (M7.2)" — *Assigned case*: the agent producing verdicts runs here; the engine intake is aitasks_go#t59_1's.
- `## Assigned case: UNSTAMPED` — "Forbidden: inventing a stamp; extending `bootstrap_until` or flipping `require_stamp`; weakening or skipping the check" — *Assigned case → Forbidden*.
- `## Assigned case: UNSTAMPED` — "**Rollout prerequisite:** unattended completion under `require_stamp: true` past `bootstrap_until` requires this task to have landed" — *Assigned case → Rollout prerequisite*: both halves before t1861; the gates fail loudly until then.
- `## Planning and ownership` — "Read the authoritative proposal … the parent t1853 protocol, and the provider task/plan files" — *Planning and ownership*, first paragraph.
- `## Planning and ownership` — "do not silently label it M2.7 or move workflow/model execution into registry code" — *Planning and ownership*, first paragraph.
- `## Planning and ownership` — "`Step 0 — Reality check`: inspect landed providers and commits … finalize the diagnostic-to-repair matrix, and record each file's owning module" — *Planning and ownership → Step 0* (this half's own; the matrix comes from aitasks_go#t59_1).
- `## Planning and ownership` — "Update the proposal's module/interface cuts where needed and notify affected provider tasks" — *Planning and ownership → Step 0*.
- `## Planning and ownership` — "Include the documented user-facing entry points and skill-wrapper ports" — *Planning and ownership* and *Required behavior → Skills and docs*.
- `## Acceptance` — "integration fixture representing an existing mixed test corpus … One unattended invocation repairs … reaches a fresh clean check, and hands off to normal test execution" — *Acceptance → Handoff*; reaching a clean `check` is tested in aitasks_go#t59_1.
- `## Acceptance` — "Every rule in the matrix has meaningful coverage … Ownership choices and annotations reflect assertions and actual ownership" — *Acceptance → Judgement*; rule coverage is aitasks_go#t59_1's.
- `## Acceptance` — "A second invocation on the clean fixture makes no changes. An interrupted run resumes without duplicate annotations, adoption rows or false gate success" — *Acceptance → No false gate success*; idempotence and resume are aitasks_go#t59_1's.
- `## Acceptance` — "Onboarding, maintenance and task-completion integration tests verify the same convergence semantics …" — *Acceptance*, fourth item.
- `## Acceptance` — UNSTAMPED scenario steps 1–5 (task leaves edge → `testmap_fresh` fail → coordinator adopts → **real** `testmap_check` passes → `tests_pass` runs) — *Acceptance → `UNSTAMPED` handoff integration scenario* (end to end; step 3's engine route is aitasks_go#t59_1's).
- `## Acceptance` — negative control "no run invents a stamp, extends `bootstrap_until`, flips `require_stamp` or skips a gate" — *Acceptance → `UNSTAMPED` scenario*, negative controls.
- `## Acceptance` — "User documentation explains adoption of an existing codebase, automatic repair behavior, configuration and residual failure reports" — *Acceptance*, documentation item.
- `## Acceptance` — "The dependency table and reciprocal references are reconciled with the final module ownership" — *Acceptance*, reconciliation item.

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t59_1 and is quoted for reference only.

> - A deterministic engine coordinator (a verb or verbs; the exact name is fixed at Step 0) does the following:
>   - inventories the whole test corpus through the M3.1 lister, including files with no annotations;
>   - consumes the structured `check` / enumeration diagnostics;
>   - applies a rule-to-repair matrix of exact diagnostic → provider operation;
>   - reloads and rechecks after each batch, with bounded attempts, repeated-state / no-progress detection and resumable on-disk progress;
>   - emits machine-readable outcomes and residual diagnostics with repair history.
> - New validated mutation primitives where only detection exists:
>   - `RouteRepair` in `registry/adoption_write.go` (`DeleteAdopted` / `RemoveSeed`, with the onboard.yaml `reviews[]` preservation);
>   - ownership correction at the declaration / area / scope level;
>   - path and member rename retarget;
>   - scan-drift apply;
>   - `MODULE_UNRESOLVED` / `MODULE_CONFLICT` handling as Info repair candidates.
> - All writes go through `annot.Apply` / `AnnotateWith` and M2.6 routing.
> - Terminal classification of `annot.ErrNoLeader` / `ErrUncertainContext` / `ErrByteOrderMark` files.
> - First-stamp adoption only through the legitimate engine routes (`annotate --author` M7.4, the M7.2 verdict intake, M6.3 `--auto`), never by inventing stamps or touching `bootstrap_until` / `require_stamp`.
> - The engine half never invokes a model, launches agents or writes task / gate ledgers.
> - Acceptance:
>   - A Go integration fixture (a mixed existing corpus: absent annotations, uncovered members, missing / ambiguous ownership, renamed paths, scan drift) reaches a fresh clean `check` in one unattended engine invocation.
>   - Every matrix rule has coverage for its automated repair or for a precisely classified terminal failure.
>   - A second run on the clean fixture is a no-op. An interrupted run resumes with no duplicate annotations or adoption rows.
>   - Conflicting rewrites, no-progress cycles, unreadable inputs and incompatible contracts terminate within the budget and keep failing diagnostics.
>   - Negative controls: no fabricated stamp, no `bootstrap_until` / `require_stamp` change, no catch-all ownership glob, no deleted valid test.
>   - The engine side of the UNSTAMPED scenario: an edge with no legitimate route stays failing with a precise residual.
>   - Bench, guards and the allowlist stay green in aitasks_go CI.


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

> **✉ note:t22_4** id=2026-10-30T10:11:09Z.5874610dc89cbdd02ffe13e3 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:09Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t59_1. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
> | It now waits on aitasks_go#t59_1 through xdeps, which
> | unblocks only when that task is Done.

> **✉ note:t22_4** id=2026-10-30T10:15:01Z.42bd467a60de1687575ced76 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:01Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task was split: its engine part is aitasks_go#t59_1; this task
> |   keeps the framework part (body trimmed, see "Relocated to aitasks_go").
