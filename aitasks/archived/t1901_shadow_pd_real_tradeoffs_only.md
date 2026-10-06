---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [shadow, skills, website, documentation]
implemented_with: claudecode/opus5_5
created_at: 2026-10-06 09:49
updated_at: 2026-10-06 09:49
completed_at: 2026-10-06 09:49
---

## Goal

Rework the shadow `>pd` (plan decisions) sub-procedure, added in t1894, so it
reports only the plan's **real design trade-offs** instead of a padded,
complete tour of the plan.

## Why

A live `>pd` run on t1894's own plan buried the genuine trade-offs under
routine choices (a docs table, on-request-only behaviour). Every item carried
"Probable benefit / Probable cost" labels, and one item spent its space
explaining the output's own labelling scheme. The user's original one-line
prompt ("explain the task in simple words and the design decisions
incorporated in the plan and the probable pros and cons") produced better
output.

Root cause: `plan-decisions.md` turned that prompt into a form to fill in:
- a "three to six decisions" quota;
- a fixed per-decision template;
- pros and cons hedged as "probable", with a cost required for every item;
- anti-invention guardrails rendered as visible output labels;
- a strict no-jargon audience rule.

The model followed it literally and padded the answer.

## Change

- Add a "Signal, not coverage" rule.
- Replace the quota with a three-part selection test: a reasonable alternative
  existed, each way gives something up, and it matters to the outcome. There
  is no target count; zero to two decisions is normal.
- Each decision gets a short paragraph and plain `Pros:` / `Cons:`. A choice
  with no real con is dropped.
- Allow at most one line on what was deliberately left out.
- Keep the anti-invention rule as an instruction, not as labels.
- Loosen the audience rule so concrete names are allowed.
- Align the routing bullet, goldens, website docs, aidocs and the test's
  content assertions.
