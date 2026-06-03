# pickn/workflown experimental staging

`aitask-pickn` and `task-workflown` are experimental staging definitions for
workflow-hardening changes. They intentionally duplicate the current
`aitask-pick` and `task-workflow` flow so stricter gates can be tested without
changing production behavior in place.

The current experiment adds fail-closed checks around:

- required `## Risk` plan sections with both Code-health and Goal-achievement
  risk headings;
- post-approval task frontmatter writes for `risk_code_health` and
  `risk_goal_achievement`;
- archive-time verification that the plan and task frontmatter still carry risk
  data;
- Step 9b satisfaction feedback completion or an explicitly recorded skip
  reason before the final response.

Do not merge wording from `task-workflown` back into `task-workflow` as part of
this experiment. A follow-up task should review the staged behavior, decide any
wording changes, and then perform a separate production merge.
