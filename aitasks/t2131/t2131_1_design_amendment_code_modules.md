---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [testmap, testing, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-23 11:50
updated_at: 2026-10-24 23:18
---

## Context

Child 1 of t2131 (test-map **code-module tier**: module → submodule, between "tests mapped to the changed files" and "the full suite").

- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`. Its section "Design defaults this pass fixes" lists defaults 1–14.
- **Coarse plan:** `aiplans/p2131/p2131_1_design_amendment_code_modules.md`.
- **Wave:** now. It consumes no unlanded provider.

This child writes **defaults 1–13** into the proposal `aidocs/testing_engine/n014_explorer_006_proposal.md`. Every later child then implements against proposal text, not against the parent plan.

The proposal has no module or tier concept today: "tier" occurs 0 times, and every "widen" in it means something else.

The prose rename of M1–M10 to "work packages" (default 14) is **not** in this child; t2131_2 does it. New prose written here already uses "work package" for M1–M10 and Mx.y (user decision: "work package" for both tiers).

**Automation-first:** no verb, rule or gate may require a human action, and agent output keeps its `by:` provenance (memory `feedback_testmap_automation_first_no_human_review`).

**Reach is deliberately simple in the initial scope** (user decision, 2026-10-23):
- it uses the current dependency graph only;
- it falls back to the full suite on any deletion, rename, unmapped path, in-repo dependency uncertainty (indirect included) or stale table;
- the absence of a resolved edge is never proof of independence;
- every fallback reason is recorded and measured;
- smarter analysis is a **named follow-up**, gated on the measured fallback share.

## Key Files to Modify

`aidocs/testing_engine/n014_explorer_006_proposal.md` (5165 lines; line numbers as of main @ ee468201f):
- **Vocabulary** (~163-250): entries for *code module / submodule* and *work package*.
- **Design decisions** (~466-647): decision 20. Code modules are logical source groupings derived from data (build systems, packages, the codemap, agent proposals), not hand-typed labels and not profile tiers. Widening is a cut knob applied after the graded walk. This re-checks t1812:55-56 and states the result explicitly.
- **Registry tables:**
  - the registry tree (~346-365) gains `_modules.yaml`;
  - *Where state lives* (~416-430);
  - the "eight tables" mentions become nine (304, 826, 2197-2200);
  - "two generated files" becomes three (~4664);
  - the reserved-name list (2306-2309).
- **Line-protocol index** (~438-463): `MODULE:`, `MODULE_CONFLICT:`, `MODULE_UNRESOLVED:`, `MODULES_DRIFT`, `WIDENED:`, `WIDEN_FULL:`, with the fallback reasons `deleted_path`, `renamed_path`, `unmapped_path`, `uncertain_reference`, `modules_stale`.
- **Module Map, M2 table** (~694-705): add the row **M2.7 — Code modules**. It owns `registry/modules*.go` (schema, `_modules.yaml`, hand `modules:` table, membership, path lookup, `MODULE_*` rules) and `internal/testmap/modules/**` (providers, `modules --scan`, the reach/widening library). Add it to the waves table (~855-865).
- **The verb list** (~2040): add `modules` (`--list`, `--explain <path|test-id>`, `--scan [--apply]`).
- **A new M2 component *Code modules*** after *Scoped-row registry and areas* (~2941). It covers:
  - tables and ids (two tiers; `<module>/<submodule>`);
  - providers and precedence: hand > agent > codemap > Gradle > Go/Python; the root project `:` is not a module; `MODULE_CONFLICT:` is always reported;
  - module → module `deps:` (inspection only);
  - freshness (`MODULES_DRIFT`);
  - membership (default 8);
  - **reach** (default 7, verbatim rules);
  - widening (default 10).
- ***Scoped-row registry and areas*** (~2831-2941): areas may reference `modules:`. `areas --import-codemap` writes module references, and colliding child names are qualified `<parent>-<child>`. Record this as a deviation from the landed M2.5 contract.
- ***Selector*** (~3266-3295), ***Run Surface*** steps 7-8 and the output contract (~1665-1693):
  - `select` / `test --widen submodule|module`;
  - the reason token `module(<id>) <- <path>`;
  - widened tests are budget-exempt;
  - the **paired prediction record**: plain selection + widen outcome (level and added tests, or `full:<reason>`) + identity (base revision, change-surface digest, registry and modules-table digests).
- ***Feedback tools*** (~3388-3425): `score` scores the plain and widened sets against the same full run and reports false negatives per set. `cadence_declared` applies to `module` too.
- ***Completion policy*** (1940-1960, 3847-3879), the config block (~370-409), the data-flow matrix (~922-941) and readiness `POLICY:` (~3414):
  - `completion.mode: full|selected|module|auto` and `completion.widen`;
  - **default 11's decision order:**
    1. readiness `NOT_YET` → full;
    2. the first `ADMISSIBLE` → engine approval in `costs/policy.yaml`;
    3. a due cadence trigger → full;
    4. an unmet criterion → `POLICY_DEMOTED:module->full|<criterion>`;
    5. a reach fallback → full with `widen_full:<reason>`;
    6. otherwise `module|next_full_in:<n>`.
  - every full run resets the counters;
  - a valid `full_run_every` is required for `module`;
  - `auto` never lands on `module` in v1.
- ***Runner contract*** (~2962+): the `group_by: module|submodule` value, plus `{module}` from the table's Gradle name.
- ***Onboarding verbs*** (~3605-3690): a `MODULES:` summary and `MODULE_UNRESOLVED:` to-dos. The onboarding skill writes `completion.mode: module` only once the engine supports it.
- ***Named follow-ups*** (~874-887): smarter reach, gated on the measured fallback share:
  - conservative inclusion of uncertain files;
  - per-language clearing to a fixed point;
  - a base-revision graph.

## Reference Files for Patterns

- `aiplans/p1859_testmap_m8_completion_policy_and_gates.md`, "Post-approval sequence" step 0: how a coarse pass edited the proposal in one change.
- `aiplans/archived/p1853/p1853_5_m2_5_scoped_rows_and_areas.md`: the area design, R3 (name rule) and R7 (unit-kind refusal).
- Every new `##` or component `###` must sit between `<!-- section: <id> [dimensions: …] -->` / `<!-- /section: <id> -->` markers, like its neighbours.

## Implementation Plan

1. **Step 0 — Reality check.** Follow the coarse plan's checks:
   - grep that `M2.7`, the verb `modules` and every new prefix are free;
   - confirm which notes t1855, t1857 and t1859_4 already hold from t2131;
   - re-verify the cited line numbers.
2. Edit the sections above in one change. Each new rule lives in exactly one component; other sections cross-reference it.
3. Commit (`documentation: … (t2131_1)`).
4. Send **contract notes** that point at the amended sections and carry the commit SHA, via `/aitask-note` (`--from 2131_1`), to: t1853 (M2), t1855 (M4), t1857 (M6), t1859_4 (M8.4), t1859_5 (M8.5) and t1854_11 (gradle-class adapter). Add only what is new relative to the notes those tasks already hold.

## Verification Steps

- Every new prefix appears in the line-protocol index, and the verb list, the registry tree and the table/file counts agree.
- Default 7's fallback rule (current graph, full on uncertainty, recorded reasons, no historical graph, no clearing) is in the component text, with smarter analysis under *Named follow-ups*.
- Default 10's paired record and default 11's decision order are stated.
- `NOTE_APPENDED:` for every contract note.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-24T20:18:01Z status=pass attempt=1 type=human
