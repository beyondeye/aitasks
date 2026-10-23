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
updated_at: 2026-10-23 11:51
---

## Context

Child 7 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 7 and 10.
- **Coarse plan:** `aiplans/p2131/p2131_7_selector_module_widening.md`.
- **Wave:** D (after M4.4).

This child wires the reach/widening library (t2131_6) into the selector. It adds the on-demand **widening tier** (user priority 1a): `select --widen submodule|module` and `test --widen submodule|module`.

**Automation-first:** no human step.

**What it adds:**
- `--widen` on `select` / `explain` (M4.1) and `test` (M4.5).
- The reason token `module(<id>) <- <path>`.
- A `WIDENED:<level>|<modules_n>|<added_n>` line ahead of the rows. The `SELECTED:` shape is unchanged.
- `WIDEN_FULL:<reason>|<path>` passed through from t2131_6, whose fallback runs the full suite.
- The widening stage after the graded walk. Widened tests are **budget-exempt** (never `DEFERRED`), so each affected module runs its complete test set (user decision 2).
- Explain-table rows for widened tests.
- **The paired prediction record** (needed for t2131_12's comparison):
  - **Content.** A widened task-scoped selection writes **one** record holding:
    - the **plain** selection (pre-widening);
    - the **widen outcome**: level + added tests, or `full:<reason>`;
    - the **identity**: base revision, change-surface digest, registry and modules-table digests.
  - **Scoring contract.** M4.4 `score` scores the plain and the widened sets against the same later full run and reports false negatives per set.
  - **Compatibility.** A record without the widened part scores exactly as today. Newest-wins per task keeps the pair together.
  - **Why here.** If widening stored only the final set, what plain selection would have missed could never be reconstructed.

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M4.1** (change-surface intake, the selector, `select` / `explain`, the prediction record; `internal/selectr`), in t1855;
- **M4.4** (`score`, `predictions.yaml` writes, `readiness`; `internal/feedback`), in t1855;
- **M4.5** (the engine `test` composite), in t1855.

Each provider parent's coarse pass adds the ids and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_6` (the library). When wiring, keep the existing deps: `aitask_update.sh --deps` replaces the list.

## Key Files to Modify (as M4 lands them)

- `goengines/internal/selectr/` (M4.1/M4.5): the `--widen` flag, the widening stage, reasons and lines, and the prediction-record fields.
- `goengines/internal/feedback/` (M4.4): `score` reads the paired record.
- `goengines/cmd/ait-testmap/`: flag wiring and CLI tests.

## Reference Files for Patterns

- Proposal *Selector* (~3266-3295), *Run Surface* steps 7-8 and the output contract (~1665-1693), the prediction record (~245, ~917), *Feedback tools* (~3388-3425). Read the versions as amended by t2131_1.
- `goengines/internal/testmap/modules/` (`Reach`, `Widen`, from t2131_6).

## Implementation Plan

1. **Step 0 — Reality check.** Read these as landed:
   - M4.1's walk, reason grammar and prediction-record schema;
   - M4.4's `score` and `predictions.yaml` rows;
   - the `explain --sources --format table` columns;
   - how `test` forwards `--widen`.

   **Stop if M4.1/M4.4/M4.5 have not landed.**
2. Add the widening stage and output lines.
3. Add the paired prediction record and its scoring.
4. Tests.

## Verification Steps

- Exact lines for `select --widen`.
- The reasons appear in `explain`.
- The `SELECTED:` shape is unchanged.
- Widened tests are never `DEFERRED`.
- The record carries plain + widen outcome + identity.
- `score` against one full run reports false negatives per set: a miss the plain set has and the widened set catches.
- A record without widening scores byte-identically to today.
- Newest-wins keeps the pair together.
- `ait engine test` is green.
