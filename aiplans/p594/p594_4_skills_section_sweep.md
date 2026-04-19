---
Task: t594_4_skills_section_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,3,5,6}_*.md
Depends on: t594_2 (canonical wording for pick/pickrem/pickweb)
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# t594_4 — Skills section coherence sweep

## Context

Largest section (27 pages). Depends on t594_2 which first unifies canonical wording for pick/pickrem/pickweb step names. This child then applies broader factual drift fixes, profile-field additions, and cross-linking.

## Scope

**In-bounds:**
- Diff each skill page's step list vs `.claude/skills/<name>/SKILL.md`; fix invented/missing steps.
- Add missing profile fields to `execution-profiles.md`.
- Document `--profile <name>` argument on `aitask-explore.md`.
- Add "Related skills" cross-links where skills chain naturally.
- Polish `skills/_index.md` category descriptions without reordering.

**Out-of-bounds:**
- Re-fixing wording already canonicalized by t594_2.
- Reorganizing `skills/_index.md` category structure or weight.
- Creating new skill documentation pages.

## Concrete drift items to fix

### A. Profile field additions to `skills/aitask-pick/execution-profiles.md`

The field table currently ends at `qa_tier`. Add:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `plan_verification_required` | int | `1` | Minimum fresh plan_verified entries required to skip verification in Step 6.0. |
| `plan_verification_stale_after_hours` | int | `24` | Age threshold for treating a plan_verified entry as stale. |

Source of truth: `.claude/skills/task-workflow/profiles.md:31-32`. Both fields are already in the shipped `fast.yaml:8-9`.

### B. Remote-only profile fields

Add a dedicated "Remote mode fields" subsection (or inline rows) covering:

- `force_unlock_stale` — bool, default `false`. Auto force-unlock stale task locks.
- `done_task_action` — string, default `archive`. What to do with Done tasks.
- `orphan_parent_action` — string, default `archive`. What to do with completed parent tasks.
- `complexity_action` — string, default `single_task`. Always single task.
- `review_action` — string, default `commit`. Auto-commit behavior.
- `issue_action` — string, default `close_with_notes`. Issue handling.
- `abort_plan_action` — string, default `keep`. Plan file on abort.
- `abort_revert_status` — string, default `Ready`. Task status on abort.

Already documented on `website/content/docs/skills/aitask-pickrem.md:79-104`. Either mirror the table here or add a "For remote mode fields, see /aitask-pickrem" pointer.

### C. `aitask-explore.md`: document `--profile <name>` argument

Source: `.claude/skills/aitask-explore/SKILL.md:6-12` declares the argument. Add a "Usage" note on the website page: `/aitask-explore --profile <name>` overrides the default profile selection for this invocation.

### D. Per-skill SKILL.md diff pass

Priority order (most-used / highest-drift-risk first):
1. `skills/aitask-pick/_index.md` vs `.claude/skills/aitask-pick/SKILL.md` — hub skill.
2. `skills/aitask-pickrem.md`, `skills/aitask-pickweb.md`.
3. `skills/aitask-explore.md`.
4. `skills/aitask-qa.md` (recently updated — higher drift risk).
5. `skills/aitask-review.md`, `aitask-fold.md`, `aitask-wrap.md`, `aitask-revert.md`.
6. The remaining 18 pages — spot-check.

For each, confirm the documented step list matches the SKILL.md step structure at the level of major steps (no invented or missing major steps).

### E. Default-model alignment

Any page mentioning a default model (most likely `aitask-pick/_index.md` or variants) must match `aitasks/metadata/codeagent_config.json` and `.aitask-scripts/aitask_codeagent.sh:27` (`DEFAULT_AGENT_STRING="claudecode/opus4_7_1m"`).

### F. "Related skills" cross-links

Add a small "Related" section at the bottom of key skill pages:
- `/aitask-explore` → `/aitask-fold`, `/aitask-pick`.
- `/aitask-pick` → `/aitask-qa`, `/aitask-review`, `/aitask-revert`.
- `/aitask-review` → `/aitask-pick`.
- `/aitask-wrap` → `/aitask-pick`.
- `/aitask-contribute` → `/aitask-contribution-review`.

## Authoritative sources

| Topic | Source |
|---|---|
| Each skill's step flow | `.claude/skills/<name>/SKILL.md` |
| Shared workflow steps | `.claude/skills/task-workflow/*.md` (SKILL.md, planning.md, profiles.md, execution-profile-selection.md) |
| Shipped profiles | `aitasks/metadata/profiles/*.yaml` |
| Canonical profile field list | `.claude/skills/task-workflow/profiles.md` |
| Default models | `aitasks/metadata/codeagent_config.json`, `.aitask-scripts/aitask_codeagent.sh:27` |

## Implementation plan

1. **Profile field additions** to `execution-profiles.md` (items A and B above).
2. **Document `--profile` on `aitask-explore.md`** (item C).
3. **Per-skill SKILL.md diff pass** in priority order (item D). For each skill:
   - Read `.claude/skills/<name>/SKILL.md`.
   - Read `website/content/docs/skills/<name>.md` (or `<name>/_index.md` for aitask-pick).
   - Diff step-by-step.
   - Fix invented/missing major steps. Keep the user-facing page's style (narrative, not step-dump), but ensure the story matches the actual flow.
4. **Default-model alignment** (item E).
5. **Related-skills cross-links** (item F).
6. **Polish `skills/_index.md` categories** — tighten descriptions, do not reorder.
7. **Hugo build check.**

## Verification

- For each diffed skill, the website step list matches the SKILL.md step structure (no invented/missing major steps).
- `grep -l "plan_verification_required" website/content/docs/skills/` includes `aitask-pick/execution-profiles.md`.
- `grep -l "\-\-profile" website/content/docs/skills/aitask-explore.md` returns the file.
- `grep -r "opus4_7_1m" website/content/docs/` — all mentions match the current default in `codeagent_config.json`.
- `cd website && hugo build --gc --minify` succeeds.

## Step 9 reference

Archive via `./.aitask-scripts/aitask_archive.sh 594_4`.
