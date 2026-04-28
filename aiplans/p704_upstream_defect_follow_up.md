---
Task: t704_upstream_defect_follow_up.md
Base branch: main
plan_verified: []
---

# Plan: Document upstream-defect follow-up workflow (t704)

## Context

The task-workflow skill recently added **Step 8b** in `.claude/skills/task-workflow/SKILL.md` and the procedure file `.claude/skills/task-workflow/upstream-followup.md`. This feature offers — after the "Commit changes" branch of `/aitask-pick`'s review step — to spawn a standalone bug aitask for an *upstream defect* surfaced during diagnosis (a separate, pre-existing bug in a different script/helper/module, whether or not it caused the current symptom).

It is also enforced upstream of itself: SKILL.md Step 8 plan consolidation requires every plan's `## Final Implementation Notes` section to include a `**Upstream defects identified:**` bullet (with `None` written verbatim if nothing applies).

None of this is documented on the website. The task asks for two deliverables:
1. Update existing docs to reflect the feature.
2. Add a dedicated workflow page for the "fixing a bug → automatic upstream-defect follow-up" flow.

## Scope

Three files touched. No code changes. User-facing-docs-only — current state, no version history.

### 1. New workflow page: `website/content/docs/workflows/upstream-defect-followup.md`

Create a new Hugo/Docsy page modelled after `website/content/docs/workflows/manual-verification.md` (similar Step 8 sub-step pattern).

Frontmatter:
```yaml
---
title: "Upstream Defect Follow-up"
linkTitle: "Upstream Defect Follow-up"
weight: 78
description: "Automatic prompt to spawn a follow-up bug task when diagnosis surfaces a separate, pre-existing defect"
depth: [intermediate]
---
```

Weight `78` slots between `qa-testing.md` (75) and `manual-verification.md` (80) inside the **Review & Quality** group — the natural neighborhood for this flow.

Content sections:
- **Lead paragraph** — Why this exists: bugfix work routinely surfaces *other* defects in different code; without a structured nudge those slip through. The automatic prompt fires from `/aitask-pick` Step 8b.
- **The plan-file contract** — Step 8 plan consolidation requires a `**Upstream defects identified:**` bullet inside `## Final Implementation Notes`. Format: `path/to/file.ext:LINE — short summary` (one bullet per defect). Write `None` (verbatim) when nothing was identified. Show a small example. Note what *doesn't* belong here (style/lint cleanups, refactor opportunities, test gaps — those route to `/aitask-qa` — and unrelated TODOs).
- **When the prompt fires** — After "Commit changes" in Step 8, before Step 8c (manual-verification follow-up). Skipped silently if no plan file exists for the task.
- **Fast path vs sanity-check path** — The procedure parses the canonical bullet first. If it sees `None`, an empty bullet, or a missing bullet, it re-reads the entire plan body — including "Out of scope", "Issues encountered", side bullets, and free prose — to catch defects that were filed in the wrong place. Reference the t687 illustration (canonical bullet `None`, real defect under `**Trailing-slash follow-up:**` side bullet — surfaced by the sanity-check path).
- **The user prompt** — The exact `AskUserQuestion` text and the two options ("Yes, create follow-up task" / "No, skip"). When there are multiple defects, the question shows the first verbatim and a `(+N-1 more — all will be folded into the new task body)` suffix.
- **The seeded follow-up task** — When the user accepts, a new task is created with `mode: parent`, `issue_type: bug`, `priority: medium`, `effort: low`, labels copied from the origin task. Body sections (`## Origin`, `## Upstream defect`, `## Diagnostic context`, optional `## Suggested fix`). Show a brief structural example.
- **End-to-end example** — Walk the t660 brainstorm-TUI illustration from `upstream-followup.md`: a worktree-prune ordering bug in `aitask_brainstorm_delete.sh:109-111` left a stale `crew-brainstorm-<N>` branch; the symptom task only added a recovery modal; Step 8b surfaced the upstream `delete` bug for its own task.
- **Tips** — Short list:
  - Document the defect in the canonical bullet, not in side bullets — the sanity-check path catches misfiled entries but the canonical bullet is the contract.
  - Use the `path/to/file.ext:LINE — short summary` form so the seeded task body has actionable navigation.
  - Don't conflate this with `/aitask-qa` — that handles automated test gaps; this is for *related* defects in code.

### 2. Index registration: `website/content/docs/workflows/_index.md`

Add one bullet to the **Review & Quality** group (between qa-testing and manual-verification):

```markdown
- [Upstream Defect Follow-up](upstream-defect-followup/) — Automatic prompt to spawn a follow-up bug task when diagnosis surfaces a separate, pre-existing defect.
```

Place it directly after the `[QA and Testing]` line and before the `[Manual Verification]` line so the natural reading order — automated tests → manual verification → upstream bug spawn — is preserved (or just slot it where the weight orders it; weight 78 is between 75 and 80).

### 3. Cross-link in `website/content/docs/workflows/follow-up-tasks.md`

That page already covers *user-driven* follow-up creation during implementation. Add a short final section (or paragraph after "Advantages Over Standalone Task Creation") titled e.g. "Automatic Upstream-Defect Follow-up" that references the new page and frames it as a complementary automatic flow. Two-three sentences max — the new workflow page is the canonical home; this is just a discoverability hook.

## Out of scope (deliberately)

- No changes to `aitask-pick/_index.md` — the existing skill page describes Steps 1–10 at a coarse grain and does not call out Step 8b/8c either; matching the manual-verification precedent (which also lives only in workflows, not in the pick page).
- No profile-key documentation — there is currently no profile key that gates Step 8b on/off (unlike `manual_verification_followup_mode`). If a future task adds one, that doc lives in the profile reference page.
- No code or procedure-file changes. The procedure already exists and works.

## Critical files (read references)

- `.claude/skills/task-workflow/SKILL.md` — Step 8 plan-consolidation contract (line ~334), Step 8b dispatcher (line ~392).
- `.claude/skills/task-workflow/upstream-followup.md` — Procedure source of truth, including the canonical/sanity-check paths and the t660 + t687 illustrations.
- `website/content/docs/workflows/manual-verification.md` — Style template for the new page (similar Step 8 sub-step workflow).
- `website/content/docs/workflows/qa-testing.md` — Adjacent doc; sets the weight-75 / 80 boundary.

## Verification

- Run `cd website && ./serve.sh` (or `hugo server`) and confirm the new page renders at `/docs/workflows/upstream-defect-followup/`.
- Confirm the new bullet appears in the Workflows index page under **Review & Quality** in the expected weight order.
- Confirm internal cross-links resolve: from the new page back to `/aitask-pick` skill, `/aitask-qa` skill, and the `follow-up-tasks` page; and from `follow-up-tasks` to the new page.
- Spot-check rendered markdown: code blocks for YAML/markdown samples, em-dash characters, and the "depth" frontmatter render correctly.
- No code or test changes — `tests/` and `shellcheck` runs are unnecessary for this task.
