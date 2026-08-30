---
Task: t1636_3_producers_emit_impact_trailer.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_4_picker_trade_profile_rendering.md, aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md, aitasks/t1636/t1636_6_manual_verification_shadow_concern_impact_vector_model.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_1_concern_dimension_vocabulary_module.md, aiplans/archived/p1636/p1636_2_concern_parser_impact_trailer.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-30 18:22
---

# p1636_3 — Producers emit the impact trailer + grounded rubric + guards

Extends the four producer docs to emit the impact trailer, grounds the
disposition rubric in the vector, gives the plan-side producers a disposition
trailer for the first time, and installs the producer-rule guards. Depends on
t1636_1 (vocabulary) and t1636_2 (parser support) — both landed and verified
against the tree below.

## Context

The shadow's four review producers classify every concern on a single
`high/medium/low` severity scale that no rubric defines — the reader cannot tell
*on which dimension* a concern is "high". t1636 replaces that scalar with a
signed **impact vector** over one closed quality-dimension vocabulary, where the
**mandatory** worsen side forces the reviewer to price its own suggestion (the
anti-overengineering mechanism).

Siblings 1 and 2 built the substrate and nothing consumes it yet:

- `.aitask-scripts/monitor/concern_dimensions.py` — the closed 7-dimension
  vocabulary, `MAGNITUDES`, `OBLIGATION_DIMENSIONS`, `normalize_magnitude`,
  `derive_priority`, `dimensions_pipe`;
- `concern_parser.py` — `_TRAILER_SPAN` already accepts
  `Improves:` / `Worsens:` / `Effort:` in the terminal run, with
  `Concern.improves` / `.worsens` / `.effort` and the three-state
  priced/unpriced/absent distinction;
- `concern-format.md` §"Derived fields: the impact vector" — the authoritative
  prose spec (vocabulary table, grammar, magnitudes-advisory framing, mandatory
  Worsens, effort scalar, disposition grounding, priority derivation).

This child makes the **producers** actually emit it. It also closes a second
gap: the three `plan-*` producers emit **no disposition trailer at all**, so
every plan concern lands undifferentiated in the picker's "Needs addressing"
bucket.

The producers are **prompt files read at runtime**. Every load-bearing rule uses
the **two-placement discipline** — a bolded pre-emit directive at the head of the
emit step AND an entry in the rules list — because a single placement is a rule
the agent may skip. `TestProducerRoundHeaderRule` and
`TestProducerRejectionSuppressionRule` are the existing model.

## Verification of the pre-existing plan (2026-08-30)

Re-checked every assumption against the current tree.

- All four producers carry `PRODUCER_MARKER` ("load-bearing for minimonitor's
  parser") and have the identical emit-step shape. ✅
- Test anchors are exact: `TestProducerShortRegionRule` :1033,
  `TestProducerRoundHeaderRule` :1364,
  `TestRenderedShadowDocsKeepTheGuarantees` :1570. ✅
- `impl-challenge.md` example fence is 391–396; the three concern lines are
  393–395. ✅
- Website sites: the findings paragraph (~line 68) and the concern-block
  paragraph in "### Forward concerns to the followed agent" (~line 98). ✅
- `.agents/skills/aitask-shadow/` and `.opencode/skills/aitask-shadow/` carry
  **only** `SKILL.md` — the producer docs are Claude-tree-only, so **no port
  task is needed** for this change. ✅

Six corrections the pre-existing plan did not carry:

1. **`ALL_SURFACES`, not just `SITES`.** `tests/test_shadow_disposition_surfaces.py`
   has two lists: `SITES` (anchored per-heading three-value checks) and
   `ALL_SURFACES` (the whole-file stale-two-value sweep, which also drives
   `TestRenderedSurfaces`). Today `ALL_SURFACES` is
   `[impl-review-angles, impl-challenge, SKILL.md, website]`. Once the plan
   producers enumerate dispositions they must join **both** lists, or the new
   enumerations are unguarded. Verified safe: the three plan producers currently
   trip zero `stale_enumerations` windows.
2. **Two prose claims become untrue** and must be corrected in the same commit:
   - `concern_parser.py:347-348` — "the three `plan-*` producers emit no trailer
     at all";
   - `concern-format.md:178-179` — "(the three plan-review producers emit none)".
   The *rule* ("unspecified is not informational") stays true; only the
   parenthetical example is falsified.
3. **A contradiction the plan must actively resolve — and it is eight sites, not
   one phrase.** `concern-format.md` now says a vector-bearing concern's marker
   priority MUST equal `derive_priority(improves)`. Every producer already
   carries its own, independently-worded policy for the same field:

   | file | lines | shape |
   |---|---|---|
   | `plan-challenge.md` | 43, 98 | prose severity → "reuse the severity you assigned in Step 3" |
   | `plan-assumptions.md` | 68-71, 102 | an **exposure matrix** (load-bearing ∧ unverified → `high`; load-bearing ∧ verified, or peripheral ∧ unverified → `medium`; peripheral → `low`) plus "(mapped as above)" |
   | `plan-diagnose-errors.md` | 51, 92 | prose "by severity" → a bare `priority` bullet that **names no source at all** |
   | `impl-challenge.md` | 344, 416 | prose severity bullet → "reuse the severity you assigned" |

   A guard written against the literal string "reuse the severity you assigned"
   would leave `plan-assumptions.md`'s matrix and `plan-diagnose-errors.md`'s
   sourceless bullet fully intact while staying green — two live alternate
   sources of marker priority. Resolution and a proximity-based guard below.
4. **All four producers carry fenced example concerns, not two.** The
   pre-existing plan named only `plan-challenge.md` and `impl-challenge.md`.
   `plan-assumptions.md:80-81` and `plan-diagnose-errors.md:70-71` carry their
   own fenced samples. Leaving those two stale means a runtime-read prompt whose
   *rules* demand a mandatory impact trailer while its *copyable example* shows
   concerns without one — contradictory guidance, and the example is the part an
   agent imitates. All four are updated, and the intended shape is put under
   regression coverage rather than left to review.
5. **A numbered-item anchor in `SITES` would not bound the site.**
   `extract_section` derives its end boundary from *markdown heading depth*: it
   computes `level` from the leading `#` run and breaks on the next line with
   `0 < depth <= level`. A numbered-list anchor (`6. **Also emit …`) yields
   `level = 0`, so that condition is never true and the slice runs to **EOF**.
   Measured: anchoring `plan-challenge.md` on its item 6 captures 92 of 145
   lines. `plan-diagnose-errors.md` is worse — its emit block is step **4 of 5**,
   so the slice would additionally swallow step 5. An unbounded site passes on a
   disposition enumeration living anywhere later in the file, which is exactly
   the vacuous coverage `SITES`' site-granularity exists to prevent. Fixed
   structurally (step 5 below), not by hedging the anchor.
6. **Risk section.** The task is `risk_evaluated`-gated and the pre-existing plan
   had no `## Risk` section and no canonical `### Pre-phase (risk mitigations)`
   block. Both are added below.

## Design decisions taken during verification

- **The vocabulary is inlined per producer as a compact 7-line name+rubric
  list**, not as `concern-format.md`'s full three-column table. The dimension
  *names* are load-bearing (an invented name fails the parser's alternation
  outright), the one-line rubrics are the minimum needed to pick correctly, and
  the `label` column is picker-side only. This keeps the added prose ~9 lines
  per producer instead of ~30.
- **Priority reconciliation — one source, and the old heuristics feed the
  vector rather than the marker.** After this change exactly one sentence in the
  repo maps anything to the marker priority: it is
  `derive_priority(improves)` — the strongest known magnitude on the improve
  side, `low` when that side is absent, empty, or all-unspecified; a concern
  carrying no vector keeps its assigned severity, exactly as before.

  The producers' existing severity heuristics are **not deleted** — they carry
  real judgement — they are **re-pointed at the vector**, which then derives the
  priority. The outcomes are unchanged; the number of mappings drops from two to
  one. Concretely for `plan-assumptions.md`'s exposure matrix: exposure now
  selects the *improve entries and their magnitudes*, not the marker —
  load-bearing ∧ unverified → a `goal`/`correctness` improve entry at `high`;
  load-bearing ∧ verified, or peripheral ∧ unverified → `medium`; peripheral →
  `low` — and `derive_priority` then yields the same `high`/`medium`/`low` the
  matrix used to write directly. `plan-diagnose-errors.md`'s bare bullet gains
  the derivation it never had. The prose-list severity and the marker priority
  become the same value by construction.

  **Authoring constraint the guard imposes:** in every rewritten bullet, keep
  the `derive_priority(improves)` sentence *adjacent* to any `high`/`medium`/`low`
  enumeration, so a compliant site cannot be split across the proximity window.
- **Plan-side producers get the disposition trailer but no `Verified:`** —
  verdicts are an impl-review artifact of the Advanced/Deep verification pass,
  which has no plan-side analogue.
- `plan-challenge.md` Step 4 ("Separate fatal from fixable") is rewritten as the
  three-way disposition split, so the prose list and the block agree.

## Implementation steps

### Pre-phase (risk mitigations)

**P1 — `state_magnitudes_advisory_in_producers`** (goal-achievement).
Add to all four producers the statement that **the dimensions are the
load-bearing part and the magnitudes are advisory** (calibration is noisy; a
named dimension is the signal that the old bare scalar never carried), in both
placements. Add `TestProducerMagnitudeFramingRule` to
`tests/test_concern_parser.py`, mirroring `TestProducerRoundHeaderRule`: the
`_states_magnitude_framing_rule` predicate collapses whitespace and requires the
bolded directive literal plus `flat.count("magnitudes are advisory") >= 2`
(counting a phrase that cannot appear in an example line, and **not**
"load-bearing" alone, which `PRODUCER_MARKER` itself contains). Include the
`test_producer_set_is_the_known_set` sibling and a **negative control** proving
the predicate fails on directive-only and bullet-only synthetic text.

**P2 — `single_source_the_marker_priority`** (goal-achievement).
Written before the trailer rules land, so the doc edits are driven by a failing
guard. Named for what it actually enforces: not "the mapping is mentioned" but
"no *other* mapping survives anywhere in the file". Two halves, in
`TestProducerImpactVectorRule`:

- **positive** — every producer states the derivation in both placements:
  `flat.count("derive_priority(improves)") >= 2`.
- **negative** — `_assigns_priority_from_another_source(text) -> list[str]`,
  built as a **proximity rule, not a phrase list**, reusing the design
  `test_shadow_disposition_surfaces.py::stale_enumerations` already documents
  ("matching literal phrasings would miss the next shape someone writes"):
  collapse whitespace, find every *assignment-shaped cue* — an alternation over
  ``set `priority` ``, `assign`, `reuse the severity`, `mapped as above`,
  `` `priority` by ``, `` `priority` is one of ``, and the matrix arrow shape
  `→ \`?(high|medium|low)\`?` — take a ±160-char window around each, and flag any
  window that does **not** contain `derive_priority`. Return the offending
  windows so the failure message shows the text, as `stale_enumerations` does.

  This catches an alternate policy by its *shape*, so `plan-assumptions.md`'s
  exposure matrix and `plan-diagnose-errors.md`'s sourceless bullet both trip it
  today, and a future hand-written policy trips it too.

Negative controls must prove the predicate flags shapes it was **not** written
against, not just the one legacy phrase: (a) the literal
"reuse the severity you assigned"; (b) an arrow-matrix line
("load-bearing and unverified → `high`"); (c) a novel wording never used in this
repo ("choose `priority` from the blast radius: wide → `high`"); and (d) a
compliant window naming `derive_priority`, which must **not** be flagged.
Include the `test_producer_set_is_the_known_set` sibling so a new producer
cannot slip past either half.

Note `impl-review-angles.md` is not a producer (it lacks `PRODUCER_MARKER`) and
its `severity-ordered` mentions are *ordering*, not assignment — they carry no
assignment cue and are correctly out of scope.

### Main steps

1. **Impact-trailer emit rules in all four producers**, two-placement each:
   - bolded pre-emit directive (proposed literal:
     `**Price your own suggestion: emit the impact vector.**`) stating *why* the
     worsen side is mandatory — a concern is a proposed delta, not a demand with
     externalised costs;
   - rules-list bullet with the grammar in **placeholder form**
     (`Improves: <dimension>(<magnitude>)[, …].`,
     `Worsens: <dimension>(<magnitude>)[, …].` or `Worsens: nothing.`,
     `Effort: <high|medium|low>.`) so the concrete examples cannot inflate a
     guard's placement count — the lesson `_states_round_header_rule` records;
   - `the Worsens sentence is mandatory` (verbatim, both placements — the token
     the guard counts), including the priced-nothing-vs-not-priced distinction;
   - the closed 7-dimension list, dimensions only from it, an unknown name
     failing the whole sentence and staying visibly in the body;
   - trailer sentences **terminal in the body**, order within the run free;
   - the priority-mapping rule (see Design decisions).

   **Rewrite all eight legacy priority-assignment sites in the same edit** —
   this is what makes the P2 guard pass, and leaving any one of them is a live
   second source for the marker:
   - `plan-challenge.md:43` (prose severity) and `:98` ("reuse the severity you
     assigned in Step 3");
   - `plan-assumptions.md:68-71` — the exposure matrix, re-pointed at the
     *improve entries and magnitudes* per Design decisions — and `:102`
     ("(mapped as above)"), which must name the derivation rather than the
     matrix;
   - `plan-diagnose-errors.md:51` (prose "by severity") and `:92` (the bare
     bullet that names no source — it gains the derivation);
   - `impl-challenge.md:344` (prose severity bullet) and `:416` ("reuse the
     severity you assigned").

   Ordering rules ("Order items by severity/priority, matching the prose list")
   are untouched — they order, they do not assign.
2. **Update the embedded example concern lines in ALL FOUR producers** —
   `plan-challenge.md:76-77`, `plan-assumptions.md:80-81`,
   `plan-diagnose-errors.md:70-71`, `impl-challenge.md:393-395` — so every
   sample carries a full trailer. An example is the part an agent imitates, so a
   stale one contradicts the rule it sits next to. Each example's marker priority
   must equal `derive_priority(improves)` for its own vector, and each must carry
   a `Worsens:` sentence (at least one sample per producer using
   `Worsens: nothing.`, so the priced-empty form is demonstrated). Plan-side
   samples gain `Disposition:` (step 4) but no `Verified:`. Keep them inside the
   ``` fences; never emit a contiguous open→items→close block (t1123).
   `TestShadowDocsNotParserLive` and
   `test_no_rendered_doc_embeds_any_contiguous_block` must stay green.
3. **Ground the disposition rubric** in `impl-review-angles.md`
   ("## Disposition rubric"): add the vector grounding as a **re-expression** of
   the existing impact-vs-obligations rubric — blocking = the improve side
   touches an obligation dimension (`goal`/`correctness` categorically;
   `robustness`/`performance` only when the task's own AC or plan obligates
   them); follow-up = net-positive, no obligation dimension touched;
   informational = no proposed delta, or already settled. The existing prose
   stays authoritative; do not weaken "`informational` is never a parking slot".
4. **Plan-side disposition adoption** — `plan-challenge.md`,
   `plan-assumptions.md`, `plan-diagnose-errors.md` gain the `Disposition:`
   trailer sentence, grounded per step 3, in both placements; rewrite
   `plan-challenge.md` Step 4 as the three-way split.
5. **Hoist each plan producer's emit step into a real `##` section** — the
   prerequisite for bounded `SITES` coverage (correction 5). In all three plan
   producers, move the emit-block content out of the numbered `## Procedure`
   item into its own top-level
   `## Also emit the structured concern block (for pick-and-forward)` section
   placed after the `## Procedure` list, leaving a one-line numbered pointer in
   the list. This mirrors `impl-challenge.md`, which already has exactly that
   heading and whose site `extract_section` bounds correctly (112 lines, not to
   EOF) — so the change is structural parity, not new structure.
   - In `plan-diagnose-errors.md` the emit block is item **4 of 5**: the pointer
     must state that the block is emitted before continuing to step 5, so
     hoisting does not reorder the procedure.
   - Choose the `SITES` prefix `"## Also emit the structured concern block"`: the
     numbered pointer starts with `6. ` / `4. `, so `extract_section`'s
     exactly-one-match tripwire still holds.
   - These three files are in `PROC_FILES_INVARIANT` (no committed goldens), so
     the restructure needs no golden regeneration; the render-invariance sweep
     (Test 1i) and the content predicates are unaffected by heading level.
6. **Guards and stale prose:**
   - finish `TestProducerImpactVectorRule` (trailer-rule placements + the P2
     halves + negative controls);
   - add `TestProducerExampleTrailerShape` — the regression coverage for the
     examples themselves, not just the rule prose. For each producer, collect its
     fenced example concern lines (`^\s*- \[` inside a ``` fence), strip the
     indent, assemble them **in memory** into a synthetic block (`OPEN` + round
     header + lines + `CLOSE`; never in a doc, so no t1123 hazard) and run the
     real `parse_concerns`. Assert per concern: `improves is not None`,
     `worsens is not None` (priced, including the `()` empty form),
     `effort != ""`, `derive_priority(c.improves) == c.priority`, and — for the
     plan producers — `disposition != ""`. Include a negative control on a
     synthetic trailer-less line proving each assertion can fail, and assert the
     collected line count is non-zero per producer so a renamed fence cannot
     reduce the test to checking nothing;
   - extend `TestRenderedShadowDocsKeepTheGuarantees` with
     `test_every_rendered_producer_states_the_impact_vector_rule` and the
     magnitude-framing equivalent — rendered coverage of the `fast` variant;
   - `tests/test_shadow_disposition_surfaces.py`: add the three plan producers to
     **`SITES`** (anchored at the new `##` heading from step 5) and to
     **`ALL_SURFACES`** — the latter also gives them rendered coverage free, via
     `TestRenderedSurfaces`, which filters `ALL_SURFACES` on the shadow dir;
   - correct the two falsified prose claims (`concern_parser.py:347-348`,
     `concern-format.md:178-179`).
7. **Website doc** — `website/content/docs/workflows/shadow-agent.md`: the
   findings paragraph (~68) and the concern-block paragraph (~98) gain the
   impact vector (improve/worsen/effort, mandatory pricing,
   dimensions-load-bearing framing), and the fact that **plan-review** concerns
   now also carry a disposition and are grouped/dimmed like implementation ones.
   Current-state prose only, no version history.
8. **Regenerate goldens in the same commit.** `impl-challenge.md` is the one
   producer with committed render goldens
   (`tests/golden/procs/aitask-shadow/impl-challenge-{default,fast,remote}.md`);
   the other three are covered by the invariance sweep and have none. Then run
   `./.aitask-scripts/aitask_skill_verify.sh`.

## Verification

- `python -m pytest tests/test_concern_parser.py tests/test_shadow_disposition_surfaces.py`
  — including the new `TestProducerExampleTrailerShape`, which is what proves the
  four updated examples actually parse into the intended trailer shape
- `bash tests/test_skill_render_aitask_shadow.sh` (golden diff — review it, don't
  rubber-stamp it)
- `./.aitask-scripts/aitask_skill_verify.sh` passes
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  line (`PYTHON SUITE: PASSED|FAILED`)

## Risk

Levels are the **post-inline reassessment** — the plan as approved, with both
confirmed pre-phase mitigations in it.

### Code-health risk: medium
- Four runtime-read prompt docs each gain a bolded directive, several rules
  bullets and the closed vocabulary; prompt bloat is itself the failure mode the
  two-placement discipline exists to counter, now applied to a larger payload ·
  severity: medium · → mitigation: none (bounded by the compact 7-line
  vocabulary form rather than the full table — see Design decisions)
- `impl-challenge.md` carries three committed render goldens; a stale golden
  fails `test_skill_render_aitask_shadow.sh` Test 1p · severity: low ·
  → mitigation: none — step 7 regenerates them in the same commit
- The three plan producers gain disposition enumerations while sitting outside
  `ALL_SURFACES`, leaving the new enumerations unguarded against two-value drift ·
  severity: low · → mitigation: none — step 6 adds them to both lists
- A `SITES` entry anchored on a numbered list item is unbounded to EOF
  (`extract_section` derives its end from heading depth), so the site check would
  pass on any disposition enumeration later in the file — vacuous coverage that
  looks green · severity: medium · → mitigation: none — step 5 hoists the emit
  step into a real `##` heading so the slice is bounded, rather than accepting a
  hedged anchor
- Hoisting the emit step out of the numbered procedure in three runtime-read
  prompt files reorders what the agent reads; in `plan-diagnose-errors.md` the
  block sits at step 4 of 5, so a careless hoist detaches it from step 5's
  "let the user choose which concerns to act on" · severity: low ·
  → mitigation: none — step 5 requires an explicit numbered pointer stating the
  block is emitted before step 5
- Editing the example concern lines in four files can produce a parser-live or
  contiguous open→items→close block (t1123) · severity: low · → mitigation: none —
  `TestShadowDocsNotParserLive` and the rendered contiguous-block test already
  guard it

### Goal-achievement risk: medium
- The guards prove the docs *state* the rules; nothing here proves a live shadow
  run *emits* a well-formed trailer — the standing limit of prompt-file work ·
  severity: medium · → mitigation: none — covered by sibling t1636_6, the
  aggregate manual-verification task, which is a named artifact with a real
  dependency edge
- A producer's copyable *example* is what an agent imitates; an example left
  without the mandatory trailer contradicts the rule beside it, and prose-only
  guards cannot see that · severity: low (residual — all four examples are
  updated and `TestProducerExampleTrailerShape` parses them with the real parser,
  asserting priced Worsens, effort, and marker/`derive_priority` agreement) ·
  → mitigation: none — step 6 puts the example shape under regression coverage
- LLM magnitude calibration is noisy; if the "dimensions load-bearing,
  magnitudes advisory" framing is lost the trailer becomes noise the user learns
  to ignore · severity: low (residual — required in every producer and guarded
  with a negative control) · → mitigation: inline pre-phase
  state_magnitudes_advisory_in_producers
- Each producer already carries its own independently-worded policy for the
  marker priority — eight sites in three shapes, including
  `plan-assumptions.md`'s exposure matrix and `plan-diagnose-errors.md`'s
  sourceless bullet. Adding `derive_priority(improves)` beside them leaves two
  live mappings for one field: the agent gets contradictory guidance and the
  picker flags a marker/vector disagreement on every concern · severity: low
  (residual — all eight sites are rewritten, the surviving heuristics feed the
  *vector* instead of the marker, and a **proximity-based** guard flags any
  window that assigns priority without naming the derivation, so a shape it was
  not written against is still caught) · → mitigation: inline pre-phase
  single_source_the_marker_priority
- The proximity guard is window-based, so a compliant site whose derivation
  sentence drifts more than ~160 chars from its `high`/`medium`/`low`
  enumeration would false-positive · severity: low · → mitigation: none — the
  adjacency requirement is stated as an authoring constraint in Design
  decisions, and control (d) pins the compliant shape

### Planned mitigations
- timing: pre-phase | name: state_magnitudes_advisory_in_producers | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — noisy magnitude calibration turning the trailer into ignorable noise | desc: every producer states dimensions are load-bearing / magnitudes advisory in both placements, with TestProducerMagnitudeFramingRule and a negative control
- timing: pre-phase | name: single_source_the_marker_priority | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — eight independently-worded policies for the marker priority field, including plan-assumptions' exposure matrix and plan-diagnose-errors' sourceless bullet | desc: positive guard that every producer states derive_priority(improves) in both placements, plus a proximity-based negative guard flagging any window that assigns priority without naming the derivation, with negative controls covering the legacy phrase, the arrow-matrix shape, a novel unseen wording, and a compliant window

## Post-Implementation

Standard Step 9. **No port task needed** for the other code agents: their
`aitask-shadow` trees carry only the `SKILL.md` wrapper (verified above), so the
producer docs edited here have no counterpart to port.

## Final Implementation Notes

- **Actual work done:** All four producers now emit the impact trailer
  (`Improves:` / `Worsens:` / `Effort:`) with the two-placement discipline, plus
  the closed 7-dimension vocabulary inline. The three `plan-*` producers gained a
  `Disposition:` trailer and a three-way rubric for the first time.
  `impl-review-angles.md` grounds `blocking` / `follow-up` / `informational` in
  the vector as a re-expression of the obligation rubric. All eight legacy
  priority-assignment sites were rewritten so `derive_priority(improves)` is the
  only mapping to the marker. Guards added to `tests/test_concern_parser.py`
  (`TestProducerMagnitudeFramingRule`, `TestProducerImpactVectorRule`,
  `TestProducerExampleTrailerShape`) plus three rendered-variant tests; the three
  plan producers joined `SITES` and `ALL_SURFACES` in
  `tests/test_shadow_disposition_surfaces.py`. Website doc and the three
  `impl-challenge` goldens updated.

- **Deviations from plan:** Two, both additive.
  1. The plan said each plan producer's *emit step* would be hoisted into a `##`
     section; in `plan-diagnose-errors.md` the old step 5 had to become a
     heading too (`## Step 5 — …`), because it followed the hoisted block and
     would otherwise have been absorbed into it.
  2. The hoisted sections were dedented by 3 columns after the move. Left as-is
     they carried leftover list indentation that no longer had a list, which in
     strict markdown risks code-block interpretation.
  Also: the plan's `TestProducerExampleTrailerShape` sketch used inline
  assertions. Review found that shape could not prove the marker/vector check
  can fail, so the checks were factored into a shared
  `_trailer_shape_violations` predicate the negative control drives directly.

- **Issues encountered:**
  - The first `TestProducerMagnitudeFramingRule` negative control passed
    spuriously: its directive fixture restated `magnitudes are advisory`, so the
    directive-only case reached count 2 on its own. Each placement must carry
    the counted phrase exactly once — noted in the fixture.
  - `plan-assumptions.md`'s exposure list tripped the new proximity guard: the
    trailing `peripheral → \`low\`` sat beyond the 160-char window from
    `derive_priority`. Fixed by keeping the derivation adjacent, which is the
    authoring constraint the guard imposes and the plan recorded.
  - The first website rewrite pushed `informational` outside the
    `stale_enumerations` window from `blocking`; the sentence was tightened.
  - Review (round 1) found two examples emitting `Improves: correctness` with
    `Disposition: follow-up`, contradicting the obligation rubric added in the
    same change. Both bodies genuinely describe correctness defects, so they
    became `blocking` rather than having their vectors weakened; each producer
    gained a `follow-up` example with a non-obligated improve side to keep the
    partition demonstration. The semantic rule is now asserted.

- **Key decisions:**
  - The vocabulary is inlined per producer as a compact 7-line name+rubric list,
    not `concern-format.md`'s three-column table — the names are load-bearing
    (an invented one fails the parser's alternation), the `label` column is
    picker-side only.
  - The existing severity heuristics were **re-pointed at the vector**, not
    deleted: `plan-assumptions.md`'s exposure matrix now selects improve entries
    and magnitudes, and `derive_priority` yields the same `high`/`medium`/`low`
    it used to write directly. Outcomes unchanged; mappings reduced from two to
    one.
  - The single-source guard is a **proximity rule** over assignment-shaped cues,
    not a list of stale phrasings — the same reasoning `stale_enumerations`
    documents. Its controls include an arrow-matrix shape and a wording that
    appears nowhere in this repo, so it is shown to catch shapes it was not
    written against.
  - `robustness` / `performance` are deliberately **not** asserted by the
    obligation check: they are obligations only when a task's own AC says so, a
    per-task judgement no static check can make.
  - Plan-side producers get `Disposition:` but no `Verified:` — verdicts are an
    artifact of the impl review's verification pass, which has no plan analogue.

- **Upstream defects identified:** None

- **Notes for sibling tasks:**
  - **t1636_4 (picker):** every producer now emits `derive_priority(improves)`
    as the marker, so the picker's "flag a disagreeing marker" path will be
    exercised only by pre-t1636_3 blocks and malformed trailers — not by
    freshly-emitted ones. The short labels (`corr`, `robus`, …) are unused so
    far; `concern_dimensions.label_for` is their only source.
  - **Behavior change t1636_4 will surface:** plan-review concerns now carry a
    disposition, so `informational` plan concerns land in the picker's dimmed
    section instead of all plan concerns landing in "Needs addressing".
  - **Adding a producer rule:** the two-placement predicates count a phrase that
    must appear **exactly once per placement**. Use placeholder grammar
    (`Improves: <dimension>(<magnitude>)`) as the counted token, never the
    concrete example, or an example line inflates the count and masks a deleted
    rule site.
  - **Adding a `SITES` entry:** anchor on a real `##`/`###` heading.
    `extract_section` derives its end bound from heading depth, so a
    numbered-list anchor computes `level = 0` and slices to EOF.
