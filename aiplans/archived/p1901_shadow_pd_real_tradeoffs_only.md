---
Task: t1901_shadow_pd_real_tradeoffs_only.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Reworked the shadow `>pd` (plan decisions) sub-procedure from t1894. It now
reports only the plan's real design trade-offs, selected by an explicit test,
instead of filling a quota with a fixed per-decision template. The skill's
routing bullet, the three entry-point goldens, the website workflow page, the
aidocs design note and the render test's content assertions were aligned with
the new behaviour.

## Files Modified

- `.claude/skills/aitask-shadow/plan-decisions.md`: rewritten intro and
  procedure.
  - New **"Signal, not coverage."** paragraph.
  - Step 3 is now a three-part selection test (a competent engineer could have
    gone another way; each way gives up something real; it matters to the
    outcome). It has an explicit leave-out list (task-dictated,
    convention-dictated, routine docs/tests/renames/wiring, trivial-cost
    choices) and "There is no target number."
  - Step 4 writes the task in two or three sentences, then the decisions most
    consequential first. Each is a short paragraph with the realistic
    alternative, the plan's reason (or "the plan does not say why"), and plain
    `Pros:` / `Cons:`. "If you cannot name a real con, the choice was not a
    trade-off — drop it." It ends with an optional one-line note of what was
    left out.
  - The anti-invention rule is now an instruction: never claim the plan
    considered or rejected an option it does not mention, and flag your own
    alternatives in passing.
  - The audience rule is loosened (concrete names allowed); only
    `round-preamble.md` §6 source selection still applies.
- `.claude/skills/aitask-shadow/SKILL.md.j2`: the Step 3 `>pd` bullet now
  describes "only the choices that were real trade-offs … never a complete
  tour of the plan".
- `tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md`:
  regenerated (diff = the bullet text only).
- `tests/test_skill_render_aitask_shadow.sh`: the `>pd` content assertions
  were replaced.
  - They now pin "Signal, not coverage", "There is no target number.", the
    no-real-con drop rule, "the plan does not say why", the never-claim-a-
    rejection rule and "Not a concern producer".
  - New `assert_not_contains` guards fail if "three to six" or a "probable
    pros" hedge returns.
- `website/content/docs/workflows/shadow-agent.md`: the "Interrogate a plan"
  `>pd` bullet and the shortcode table row now describe real trade-offs only,
  with plain pros and cons.
- `aidocs/framework/shadow_agent.md`: the `plan-decisions.md` bullet now
  describes the selection test, and records why there is no target count or
  fixed template (they make the model pad). The sub-procedure count sentence
  was rewrapped.

## Probable User Intent

The user tried `>pd` live on t1894's plan in a Codex shadow pane. The output
gave equal weight to boring, obvious choices and real trade-offs, and wrapped
everything in "Probable benefit / Probable cost" fluff. Their original simple
prompt gave better results.

Diagnosis: the t1894 procedure itself caused the padding. It set a
"three to six" quota and a uniform per-decision template, asked for a cost on
every item, hedged everything as "probable", turned anti-invention guardrails
into visible output labels, and imposed a strict no-jargon rule. The intent of
the rework is to restore the judgement the simple prompt allowed (report what
matters, leave out the rest) while keeping the one guardrail that matters: no
invented rationale or rejection. The user confirmed the reworked output is
much better before wrapping.

## Final Implementation Notes

- **Actual work done:** As in Files Modified. All nine local shadow closures
  (claude/codex/opencode × 3 profiles) were force-re-rendered. Results: shadow
  render test 747/747, phase-advisory sweep 55/55, `aitask_skill_verify.sh` OK,
  `check_links.py --build` PASSED.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:**
  - A selection test instead of a count. Any target number or fixed
    per-decision template invites padding, and aidocs now says to keep it
    that way.
  - Requiring a real con doubles as the filter: a choice with no real con is
    not a trade-off.
  - The anti-invention rule stays as an instruction rather than output labels,
    because labels leak into the answer as noise.
