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
- Confirmed **inline risk mitigations** appear as explicit
  `### Pre-phase (risk mitigations)` / `### Post-phase (risk mitigations)`
  step blocks — the pre-phase block immediately before the first numbered
  implementation step, the post-phase block immediately after the last.
  **Fallback for plans without numbered main steps** (heading- or
  file-oriented plans): the pre-phase block goes at the top of the plan body,
  immediately after the metadata header; the post-phase block goes
  immediately before the first of `## Verification` / `## Risk` (end of file
  if neither exists). Steps are name-labeled and cross-referenced from the
  `## Risk` bullets by mitigation name. These two headings are the canonical
  insertion anchors (see `risk-mitigation-followup.md` Part 1 step 3).
