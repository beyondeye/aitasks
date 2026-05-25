{# _planning_plan_contract.md — implementation-plan content contract for
   task-workflow planning.md (single-level plans). Consumed only by
   .claude/skills/task-workflow/planning.md via minijinja {% include %}.
   Brainstorm's detailer.md has its OWN two-level (proposal + plan)
   contract inlined in detailer.md — do NOT unify the two.
   Jinja comment (not HTML) so it does NOT appear in rendered output. #}
- Create a detailed, step-by-step implementation plan. "Detailed" means:
  specific file paths, detailed implementation steps with exact changes
  needed in each file, code snippets for non-trivial modifications, and
  verification steps. Do not produce a high-level overview.
