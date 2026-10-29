---
priority: medium
effort: high
depends: [t2131_6]
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-25 00:40
---

## Context

Child 7 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 7 and 10.
- **Coarse plan:** `aiplans/p2131/p2131_7_selector_module_widening.md`.
- **Wave:** D (after M4.4).

This child wires the reach/widening library (t2131_6) into the selector. It adds the on-demand **widening tier** (user priority 1a): `select --widen-modules` and `test --widen-modules`, a plain flag with no level.

**Automation-first:** no human step.

> **Revised 2026-10-24 (user decision): flat code modules, no submodules.** There is one widening behaviour and one spelling, `--widen-modules`, with no level anywhere in the flags, output or records. The contract is the proposal's component *Code modules*.

**What it adds:**
- `--widen-modules` on `select` / `explain` (M4.1) and `test` (M4.5).
- **The public flag.** M5.1's bash front `aitask_test.sh` parses `ait test --widen-modules` and forwards it unchanged to the engine `test` composite, alone or with `--explain`. This is a named extension of M5.1's flag table. The front adds no widening logic, because a `WIDEN_FULL` outcome is already the composite's `--all` path.
- The reason token `module(<name>) <- <changed path>[ via <reached path>]`.
- A `WIDENED:<modules_n>|<added_n>` line ahead of the rows. The `SELECTED:` shape is unchanged.
- `WIDEN_FULL:<reason>|<first path>|<more_n>` passed through from t2131_6.
- **Full fallback execution.** A `WIDEN_FULL` outcome of `test --widen-modules` runs through the **canonical full-run path**: exactly what `--all` runs, with `full: true` suites once, `subsumed_by`, the `full-` prefix, anchors, cost rows and the automatic `score`. It is never a re-listing of every row.
- **Recording wording.** `select` / `explain --widen-modules` never execute or score a test. Each writes exactly what its plain form writes, so a task-scoped `select` still writes the task's prediction record, now with the widen outcome. Nothing may prohibit that recording.
- The widening stage after the graded walk. Widened tests are **budget-exempt** (never `DEFERRED`), so each affected module runs its complete test set (user decision 2).
- Explain-table rows for widened tests.
- **The paired prediction record** (needed for t2131_12's comparison):
  - **Content.** A widened task-scoped selection writes **one** record holding:
    - the **plain** selection (pre-widening);
    - the **widen outcome**: the added tests, or `full:<reason>`;
    - the **identity**: base revision, change-surface digest, registry and modules-table digests.
  - **Scoring contract.** M4.4 `score` scores the plain and the widened sets against the same later full run and reports false negatives per set (`WIDEN_SCORED:`; `predictions.yaml` rows gain an optional `widened {added_n, fn, full?}`).
  - **Readiness judges the executed strategy** (M4.4 `readiness`):
    - `selected` / `auto` read plain sets only;
    - `module` reads widened sets. A record without a widened part counts its plain false negatives. A full run counts toward the run totals only when every scored record carries a widened part and at least one is not `full:`. A modules-table change is a map change;
    - the rule is in the proposal's *Feedback tools*.
  - **Automatic recording under `module`.** While `completion.mode` is `module`, every task-scoped selection records the widen outcome even without the flag.
  - **Compatibility.** A record without the widened part scores exactly as today. Newest-wins per task keeps the pair together.
  - **Why here.** If widening stored only the final set, what plain selection would have missed could never be reconstructed.

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M4.1** (change-surface intake, the selector, `select` / `explain`, the prediction record; `internal/selectr`), in t1855;
- **M4.4** (`score`, `predictions.yaml` writes, `readiness`; `internal/feedback`), in t1855;
- **M4.5** (the engine `test` composite), in t1855;
- **M5.1** (the `ait test` bash front `aitask_test.sh`, its flag parsing and the fake-engine `tests/test_ait_test_entrypoint.sh`), in t1856. Added 2026-10-25: the public `--widen-modules` flag is parsed and forwarded there.

Each provider parent's coarse pass adds the ids and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_6` (the library). When wiring, keep the existing deps: `aitask_update.sh --deps` replaces the list.

## Key Files to Modify (as M4 lands them)

- `goengines/internal/selectr/` (M4.1/M4.5): the `--widen-modules` flag, the widening stage, reasons and lines, and the prediction-record fields.
- `goengines/internal/feedback/` (M4.4): `score` reads the paired record; `readiness` applies the prediction-set rule.
- `goengines/cmd/ait-testmap/`: flag wiring and CLI tests.
- `.aitask-scripts/aitask_test.sh` (M5.1): parse `--widen-modules` and forward it to the engine `test` composite.
- `tests/test_ait_test_entrypoint.sh` (M5.1): the fake-engine invocation check.

## Reference Files for Patterns

- Proposal *Selector* (~3266-3295), *Run Surface* steps 7-8 and the output contract (~1665-1693), the prediction record (~245, ~917), *Feedback tools* (~3388-3425). Read the versions as amended by t2131_1.
- `goengines/internal/testmap/modules/` (`Widen`, from t2131_6).

## Implementation Plan

1. **Step 0 — Reality check.** Read these as landed:
   - M4.1's walk, reason grammar and prediction-record schema;
   - M4.4's `score` and `predictions.yaml` rows;
   - the `explain --sources --format table` columns;
   - how `test` forwards `--widen-modules`, and how its `--all` path is entered for a `WIDEN_FULL` outcome.

   - M5.1's landed flag parsing in `aitask_test.sh`, and the fake engine in `tests/test_ait_test_entrypoint.sh`.

   **Stop if M4.1/M4.4/M4.5 or M5.1 have not landed.**
2. Add the widening stage and output lines.
3. Add the paired prediction record and its scoring.
4. Tests.

## Verification Steps

- Exact lines for `select --widen-modules`.
- A `WIDEN_FULL` outcome of `test --widen-modules` runs the canonical `--all` path, scoring and accounting included. `select` / `explain --widen-modules` execute nothing, yet a task-scoped `select` still writes the prediction record.
- Readiness under `module` counts a miss the widened set caught as no false negative. Under `auto` it counts that same miss as one.
- The reasons appear in `explain`.
- The `SELECTED:` shape is unchanged.
- Widened tests are never `DEFERRED`.
- The record carries plain + widen outcome + identity.
- `score` against one full run reports false negatives per set: a miss the plain set has and the widened set catches.
- A record without widening scores byte-identically to today.
- Newest-wins keeps the pair together.
- `ait test --widen-modules`, and `ait test --explain --widen-modules`, reach the fake engine with the flag forwarded unchanged. A control run without the flag forwards none.
- `ait engine test` is green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:24:10Z.42b3fe7da8488b54a89cb927 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:10Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
