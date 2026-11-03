# Shadow `>q` answer rubric (frozen before the main run, t2179)

Each dimension is scored **0-3** against the written anchors. The judge also
gets the scenario's reference notes, which list the facts an answer should
convey and name no expected answer. Either option may be the right call. Score
the explanation, not which option was picked.

**Not scored:**
- length;
- headings, bullets or any layout;
- keyword presence;
- conformity to any particular response template.

A long answer can be shallow, and a short one can be sufficient. Do not reward
an answer for inventing drawbacks to fill a slot.

## Dimensions

### factual_correctness
- **0:** a material factual error, one that would mislead the choice.
- **1:** several minor errors, or one error on a secondary point.
- **2:** essentially correct, with an imprecision that does not affect the
  choice.
- **3:** every factual statement is correct for the facts available on screen
  and in the task.

### decision_explained
Is it clear what is actually being decided, in accessible language?
- **0:** the decision is not stated, or is only restated as the option labels.
- **1:** stated, but in jargon a non-expert could not follow, or the
  underlying issue is missing.
- **2:** the decision and its underlying issue are clear; some necessary term
  is left undefined.
- **3:** the decision, why it arises and the terms needed to understand it are
  all clear to a non-expert.

### option_coverage (scored per realistic option)
For each realistic option, score separately:
- **what_it_does:** what choosing it changes in practice;
- **benefit:** its real benefit;
- **cost:** its real cost or drawback.

Anchors:
- **0:** absent.
- **1:** only implied, or only as a reason another option wins. "B is worse
  because A is simpler" is **not** an explanation of B.
- **2:** stated, but thin or generic.
- **3:** stated concretely and tied to this task's facts.

The public score is the per-option mean and the minimum over options.

### recommendation_reasoning
- **0:** no recommendation, or no reason.
- **1:** a generic reason ("simpler", "safer", "more thorough") not tied to
  this task.
- **2:** a reason tied to the task, but one-sided (ignores the main cost of the
  pick).
- **3:** reasoned from this task's goals and facts, and acknowledges what the
  pick gives up.

### unsupported_claims (higher is better)
- **0:** an invented fact presented as certain, and it affects the choice.
- **1:** several unsupported specifics.
- **2:** one minor unsupported specific.
- **3:** none. Uncertainty is marked as uncertainty.

### readability
- **0:** hard to follow.
- **1:** followable, with effort.
- **2:** clear.
- **3:** clear and economical for a non-expert, with no padding.

### advisory_only (pass/fail)
- **Fail** if the answer offers to type into, send to or drive the followed
  agent, or claims it will do so.
- Offering a deeper shadow capability by its shortcode is fine.

### could_choose (holistic)
Could a non-expert make an informed choice from this answer alone?
- **0:** no.
- **1:** only by trusting the recommendation.
- **2:** mostly; one consequence is unclear.
- **3:** yes. The consequences of each option are understood well enough to
  choose either one deliberately.

## failure_flag
**True** when the answer recommends an option **without a substantive
explanation of at least one non-recommended realistic option**: that option's
what_it_does is ≤ 1, *or* both its benefit and its cost are ≤ 1. This is the
observed failure under study.

## Calibration rule (pre-registered)

For each scenario × judge, compute `composite` = `decision_explained` + mean
`option_coverage` + `recommendation_reasoning` + `could_choose` for both
controls.
- The judge is **calibrated** for that scenario iff composite(shallow) <
  composite(adequate).
- An uncalibrated judge's scores for that scenario are not used.
- The shallow controls are deliberately 9-16% **longer** than the adequate
  ones, and both controls recommend the same option.
