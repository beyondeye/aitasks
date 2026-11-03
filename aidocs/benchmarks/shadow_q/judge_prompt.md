You are scoring one answer written by an advisory assistant (a "shadow"). The
shadow watches another coding agent's terminal, and the user asked it for help
deciding what to do. Score the answer against the rubric below. Use the
reference notes and the screen the shadow saw as ground truth. The reference
names no expected answer: either option can be right, so score the
explanation, not the pick.

The shadow could also read the task file (and the plan, when one existed),
reproduced below. A claim that cites the task file is checked against it: if
the task file says it, it is supported. Only a claim you cannot verify from the
screen, the task file or the reference notes counts as unsupported.

Do not use any tools. Do not reward length, headings or a particular layout.
Return **only** a JSON object, with no prose before or after it, in exactly
this shape:

{"options": [{"option": "<short label>", "what_it_does": 0-3, "benefit": 0-3, "cost": 0-3}],
 "factual_correctness": 0-3, "decision_explained": 0-3, "recommendation_reasoning": 0-3,
 "unsupported_claims": 0-3, "readability": 0-3, "advisory_only": true|false, "could_choose": 0-3,
 "failure_flag": true|false, "rationale": "<= 80 words"}

List every realistic option the user faced (from the screen) in `options`,
including the ones the answer did not recommend.

=== RUBRIC ===
{rubric}

=== REFERENCE NOTES (scorer-only) ===
{reference}

=== THE SCREEN THE SHADOW SAW ===
{screen}

=== THE TASK FILE (AND PLAN) THE SHADOW COULD READ ===
{task}

=== THE ANSWER TO SCORE (id {blind_id}) ===
{answer}
