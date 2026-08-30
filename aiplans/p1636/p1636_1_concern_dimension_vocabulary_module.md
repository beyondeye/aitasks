---
Task: t1636_1_concern_dimension_vocabulary_module.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_2_concern_parser_impact_trailer.md, aitasks/t1636/t1636_3_producers_emit_impact_trailer.md, aitasks/t1636/t1636_4_picker_trade_profile_rendering.md, aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_*_*.md
Branch: main
Base branch: main
Output branch: main
---

# p1636_1 — Dimension vocabulary module + format spec (SSOT)

Creates the single source of truth every other t1636 child builds on: the
closed quality-dimension vocabulary, magnitude semantics, `derive_priority`,
and the `concern-format.md` spec section — plus the doc↔module drift guard.

Parent plan `aiplans/p1636_shadow_concern_impact_vector_model.md` settles the
design (7 dims, maintainability/simplicity split, grammar, priority mapping);
this plan implements, it does not re-decide.

## Steps

1. **Write `.aitask-scripts/monitor/concern_dimensions.py`** modeled on
   `.aitask-scripts/lib/followup_kinds.py` (dict = canonical order, derived
   frozenset, accessors, docstring explaining the closed/framework-semantic
   vocabulary). Contents:

   - `CONCERN_DIMENSIONS: dict[str, tuple[str, str]]` — name → (short label,
     one-line rubric), declaration order canonical:
     - `goal` (`goal`) — the task's AC / the user's stated intent is delivered
     - `correctness` (`corr`) — right behavior on reachable inputs
     - `robustness` (`robus`) — stability under failure/concurrency/hostile
       input (includes security)
     - `performance` (`perf`) — latency, throughput, resource cost
     - `verification` (`verif`) — testability; proof the change works
     - `maintainability` (`maint`) — readability, duplication, conventions;
       ease of safe change
     - `simplicity` (`simpl`) — amount of mechanism; the classic worsen-side
   - `VALID_DIMENSIONS: frozenset`, `dimensions_pipe()` (sorted alternation
     for regex builders — mirror `followup_kinds_pipe()`), `label_for()`,
     `rubric_for()`.
   - `MAGNITUDES = ("high", "medium", "low")` + `normalize_magnitude(raw)`:
     recognised (case-insensitive) → canonical; unrecognised/absent → `""`
     (unspecified) — **never `low`** (docstring: degrading the worsen side
     understates a cost, the unsafe direction).
   - `OBLIGATION_DIMENSIONS = frozenset({"goal", "correctness"})` — the
     categorical core; docstring records that robustness/performance become
     obligation-touching only when the task's AC or plan obligates them
     (per-task judgement, made by the producing agent, not this module).
   - `derive_priority(improves) -> str`: max magnitude over improve entries
     whose magnitude is **known** (`high` > `medium` > `low`); empty/absent
     improve side, or no known magnitudes → `low`. Accepts the parser's entry
     shape (`(dimension, magnitude)` tuples or objects with those attributes —
     keep it duck-typed on index/attr, decided with t1636_2's `ImpactEntry`;
     until then accept `(name, mag)` tuples).
   - **Label-width assertion at import time**: every short label ≤ 5 chars
     (`assert all(len(lbl) <= 5 …)` with a comment deriving the bound:
     narrow-picker core `▲label? ▼label? E:xx` must fit 21 cells at 24
     columns → `2·(W+2) + 2 + 4 ≤ 21 → W ≤ 5`).
   - Pure module: no I/O, no sys.path insertion, no tmux — importable by the
     contractually pure `concern_parser.py` as a sibling (same try/except
     relative/flat import pattern consumers already use).

2. **Add the spec section to `.claude/skills/aitask-shadow/concern-format.md`**,
   placed after "Derived fields: `disposition` and `verdict`", titled e.g.
   `### Derived fields: the impact vector (Improves / Worsens / Effort)`:
   - the trailer sentences and their grammar (closed dimension names;
     `name` or `name(magnitude)` entries; magnitudes high/medium/low,
     case-insensitive, unknown → unspecified, never dropped);
   - the **mandatory Worsens rule**: every vector-bearing concern prices its
     own suggestion — `Worsens: nothing.` is a *priced* empty set and is a
     different state from an absent sentence (the anti-overengineering
     mechanism);
   - magnitudes advisory / dimensions load-bearing framing;
   - `Effort:` as a separate one-time-cost scalar (never a vector dimension —
     quality deltas are permanent, effort is transient);
   - the **disposition grounding rubric**: `blocking` = improve side touches
     an obligation dimension per the task's AC/plan goal; `follow-up` =
     net-positive but non-obligated; `informational` = no proposed delta /
     already settled — cross-referencing `impl-review-angles.md` as the
     rubric's authoritative home (t1636_3 grounds it there);
   - the priority mapping (`derive_priority`) and the rule that the marker
     priority equals it for vector-bearing concerns;
   - enumerate the full dimension list with rubrics, matching the module.
   - **t1123 discipline**: any example lines stay inside ``` fences and never
     form a contiguous open→items→close block; run the authoring-safety check
     (`contains_any_concern_block`) via the existing
     `TestShadowDocsNotParserLive` which already sweeps `*.md` in the shadow
     dir — confirm it stays green.

3. **Write `tests/test_concern_dimensions.py`**:
   - module content: 7 dimensions in the settled order; labels ≤5; magnitude
     normalization (`HIGH`→`high`, `extreme`→`""`, `None`/`""`→`""`);
     `derive_priority` cases: `[("robustness","high")]`→`high`, mixed→max,
     `[]`→`low`, `None`-ish/absent→`low`, all-unknown→`low`.
   - **doc↔module drift guard**: parse the concern-format.md section and
     assert it enumerates exactly `VALID_DIMENSIONS` (whitespace-normalized
     matching, anchored to the new section heading — mirror the site-anchored
     approach of `tests/test_shadow_disposition_surfaces.py`).
   - **negative control**: the drift predicate fails on synthetic doc text
     missing one dimension and on text naming an extra one.

4. **Run** `./.aitask-scripts/aitask_skill_verify.sh` (concern-format.md is
   shadow-doc surface) and the targeted tests.

## Verification

- `python -m pytest tests/test_concern_dimensions.py tests/test_concern_parser.py` —
  the parser suite must stay green untouched (this child adds no parser code).
- `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last
  line (`PYTHON SUITE: PASSED|FAILED`).
- `./.aitask-scripts/aitask_skill_verify.sh` passes.

## Post-Implementation

Standard Step 9 (task-workflow): commit, archive task + this plan, `./ait git`
for task/plan files.
