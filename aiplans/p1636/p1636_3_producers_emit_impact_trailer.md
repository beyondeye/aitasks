---
Task: t1636_3_producers_emit_impact_trailer.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_1_concern_dimension_vocabulary_module.md, aitasks/t1636/t1636_2_concern_parser_impact_trailer.md, aitasks/t1636/t1636_4_picker_trade_profile_rendering.md, aitasks/t1636/t1636_5_delta_scoped_auto_recheck.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_*_*.md
Branch: main
Base branch: main
Output branch: main
---

# p1636_3 — Producers emit the impact trailer + grounded rubric + guards

Extends the four producer docs to emit the impact trailer, grounds the
disposition rubric in the vector, gives the plan-side producers a disposition
trailer for the first time, and installs the producer-rule guards. Depends on
t1636_1 (vocabulary) and t1636_2 (parser support). The producers are prompt
files read at runtime: every load-bearing rule uses the **two-placement
discipline** (bolded pre-emit directive at the head of the emit step AND a
rules-list entry), modeled on the existing round-header and
rejection-suppression rules.

## Steps

1. **[state_magnitudes_advisory_in_producers — risk mitigation, FIRST]** Add
   to every producer (`plan-challenge.md`, `impl-challenge.md`,
   `plan-assumptions.md`, `plan-diagnose-errors.md`) the statement that the
   **dimensions are the load-bearing part and the magnitudes are advisory**
   (calibration is noisy; a named dimension is the signal), and add
   `TestProducerMagnitudeFramingRule` to `tests/test_concern_parser.py` over
   the same `KNOWN_PRODUCERS` / `PRODUCER_MARKER` set as
   `TestProducerShortRegionRule`, with a **negative control** proving the
   predicate fails on synthetic text lacking the framing.

2. **Impact-trailer emit rules in all four producers**, two-placement each:
   - trailer sentences terminal in the body, after any Disposition/Verified
     sentence order is free: `Improves: <dim>(<mag>)[, …].` — **mandatory**
     `Worsens:` sentence, `Worsens: nothing.` when genuinely costless (the
     bolded directive states WHY: pricing your own suggestion is the
     anti-overengineering mechanism; a concern improving only non-obligated
     dims at a simplicity cost self-identifies as a bad trade) —
     `Effort: low|medium|high.`;
   - dimensions ONLY from the closed vocabulary (enumerate it, with one-line
     rubrics, sourced from `concern-format.md`'s new section);
   - **priority-mapping rule** (parent decision 2): a vector-bearing concern's
     marker priority MUST equal `derive_priority(improves)` — max known
     improve magnitude, `low` when empty — so marker and vector cannot
     contradict;
   - update the embedded example concern lines in `plan-challenge.md` and
     `impl-challenge.md:393-395` to carry full trailers (keep them inside
     ``` fences; never a contiguous open→items→close block — t1123; confirm
     `TestShadowDocsNotParserLive` stays green).

3. **Ground the disposition rubric** in
   `.claude/skills/aitask-shadow/impl-review-angles.md` ("Disposition
   rubric"): add the vector grounding as a re-expression of the existing
   impact-vs-obligations rubric (blocking = improve side touches an
   obligation dimension per the task's AC/plan goal; follow-up = net-positive
   but non-obligated; informational = no proposed delta / already settled).
   The existing prose stays authoritative; do not weaken "informational is
   never a parking slot".

4. **Plan-side disposition adoption**: `plan-challenge.md`,
   `plan-assumptions.md`, `plan-diagnose-errors.md` gain the
   `Disposition: …` trailer sentence (grounded per step 3) — today they emit
   none and every plan concern lands undifferentiated in "Needs addressing".
   Update `tests/test_shadow_disposition_surfaces.py` `SITES` for each new
   enumeration site (site-granular, anchored to headings, per that file's
   discipline).

5. **`TestProducerImpactVectorRule`** in `tests/test_concern_parser.py`,
   mirroring `TestProducerRoundHeaderRule` (line 1364): every producer states
   the trailer rule in BOTH placements (whitespace-normalized predicates), the
   producer set is the known set, plus a negative control. Rendered-variant
   coverage comes free via `TestRenderedShadowDocsKeepTheGuarantees`
   (line 1570) — extend its checked-guarantees list to include the new rule.

6. **Website doc**: `website/content/docs/workflows/shadow-agent.md` — the
   findings description (~line 70) and the concern-block description
   (~line 98) gain the impact vector (improve/worsen/effort, mandatory
   pricing, dimensions-load-bearing framing). Current-state prose only, no
   version history.

7. Run `./.aitask-scripts/aitask_skill_verify.sh`; regenerate any affected
   goldens in the same commit.

## Verification

- `python -m pytest tests/test_concern_parser.py tests/test_shadow_disposition_surfaces.py`
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last
  line.

## Post-Implementation

Standard Step 9. Suggest (per CLAUDE.md) separate aitasks for porting the
skill changes to the other supported code agents if the shadow trees there
carry more than the SKILL.md wrapper (they currently do not — verify at
implementation time).
