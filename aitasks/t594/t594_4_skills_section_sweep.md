---
priority: medium
effort: high
depends: [t594_2]
issue_type: documentation
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 17:11
updated_at: 2026-04-20 10:41
---

Child of t594. Sweep the 27 pages under `website/content/docs/skills/`. Depends on t594_2 so canonical wording for pick/pickrem/pickweb is already set.

## Context

Parent plan: `aiplans/p594_website_documentation_coherence.md`. Largest section (27 pages). Focus on factual drift vs each skill's `SKILL.md`, profile-field documentation gaps, and cross-linking related skills.

## Key Files to Modify

- All 27 pages under `website/content/docs/skills/` — cross-check against corresponding `SKILL.md` files.
- `website/content/docs/skills/aitask-pick/execution-profiles.md` — add missing profile fields.
- `website/content/docs/skills/aitask-explore.md` — add `--profile <name>` argument documentation.
- `website/content/docs/skills/_index.md` — category grouping polish (no weight changes).

## Reference Files for Patterns (Authoritative Sources)

- `.claude/skills/<name>/SKILL.md` — source of truth for each skill's step list.
- `.claude/skills/task-workflow/*.md` — shared procedures (planning.md, profiles.md, execution-profile-selection.md, etc.).
- `aitasks/metadata/profiles/*.yaml` — shipped profiles (default, fast, remote).
- `.claude/skills/task-workflow/profiles.md` — canonical profile field documentation (internal).
- `aitasks/metadata/codeagent_config.json`, `.aitask-scripts/aitask_codeagent.sh:27` — default-model truth.

## Implementation Plan

1. **Profile-field additions to `execution-profiles.md`:**
   - Add `plan_verification_required` (int, default 1) — documented in `profiles.md:31`.
   - Add `plan_verification_stale_after_hours` (int, default 24) — documented in `profiles.md:32`.
   - Add a "Remote-mode fields" section pointing at `/aitask-pickrem` for details (or inline the fields: `force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `complexity_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status`).
2. **Document `--profile` on `aitask-explore.md`:** add a "Usage" section mentioning `--profile <name>` per `.claude/skills/aitask-explore/SKILL.md:6-12`.
3. **Per-skill SKILL.md diff pass:** for each of the 27 skill pages, diff the documented step list against `.claude/skills/<name>/SKILL.md`. Priority order: aitask-pick, aitask-pickrem, aitask-pickweb, aitask-explore, aitask-qa, aitask-review, aitask-fold, aitask-wrap, aitask-revert. Fix invented or missing major steps.
4. **Default-model alignment:** verify any page mentioning a default model against `codeagent_config.json` and `DEFAULT_AGENT_STRING`.
5. **Related-skills cross-links:** add "Related skills" sections where skills chain naturally (explore → create → pick; pick → qa; review → pick; wrap → pick; etc.).
6. **Category polish in `skills/_index.md`:** tighten category descriptions; do not reorder.

## Verification Steps

- For each verified skill, the website's step list matches the SKILL.md structure (no invented or dropped major steps).
- `grep -r "plan_verification_required\|plan_verification_stale_after_hours" website/content/docs/` — at least one match in execution-profiles.md.
- `grep "\-\-profile" website/content/docs/skills/aitask-explore.md` — documented.
- `cd website && hugo build --gc --minify` succeeds.
