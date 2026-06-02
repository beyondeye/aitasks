---
Task: t884_6_risk_evaluation_website_docs.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_6_risk_evaluation_website_docs
Branch: aitask/t884_6_risk_evaluation_website_docs
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-02 12:06
---

# Plan: t884_6 — Website docs for risk evaluation

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on t884_1/_9 (fields), t884_2 (profile key), t884_3 (planning step + `## Risk`),
> t884_4 (mitigation procedure), t884_5 (force-reverify). All archived/landed.

## Context

The risk-evaluation feature (parent t884) is fully implemented across siblings 1–5
and 9 but undocumented on the website. This task documents only the **user-visible
surfaces**. Follow `aidocs/documentation_conventions.md`: current-state only (no
version history), generic placeholder project names, "autonomous" not
"auto-execution".

## Verify-pass correction (2026-06-02)

The pre-existing plan assumed a **single** `risk` frontmatter field. Per the t884_9
redirect (archived: `aiplans/archived/p884/p884_9_two_field_risk_plumbing.md`) the
single field was **replaced by two** independent fields, with **no aggregate**:

- `risk_code_health` — `high|medium|low`; stability / quality / maintainability /
  blast-radius of the planned change.
- `risk_goal_achievement` — `high|medium|low`; whether the plan will actually deliver
  the user's requested goals.

Both are **display-only** (no sort score, no border color), **omitted by default**,
and a **planning output** (assigned by the risk-evaluation step via
`ait update`, never a creation-time input). Display labels confirmed against the live
code: `ait ls` renders `CH-risk:` / `GA-risk:`; `ait board` cycle fields are
"Code-health risk" / "Goal risk". `risk_mitigation_tasks` is a single shared YAML list,
dropped on fold. The docs below describe **two** fields throughout.

## Target pages (verified to exist; extend in place — no new pages)

1. **`website/content/docs/development/task-format.md`** — the canonical frontmatter
   reference. Add three rows to the **Frontmatter Fields** table (after the `verifies`
   row, grouping with other planning-output fields):
   - `risk_code_health` | `high`, `medium`, `low` | Code-health risk assigned by the
     risk-evaluation planning step (display-only; omitted unless evaluated)
   - `risk_goal_achievement` | `high`, `medium`, `low` | Goal-achievement risk assigned
     by the risk-evaluation planning step (display-only)
   - `risk_mitigation_tasks` | `[t884_4, t890]` | Task IDs created to mitigate risks
     identified during planning (dropped on fold)

2. **`website/content/docs/tuis/board/reference.md`** — add two rows to the **Task
   Metadata Fields** table (after `effort`): `risk_code_health` / `risk_goal_achievement`,
   `string`, Editable = **Yes (cycle)**, "`low`, `medium`, or `high` — shown only when set
   by the risk-evaluation planning step". One sentence noting they render as read-only for
   Done/Folded tasks (matching the implemented `ReadOnlyField`/`CycleField` split).

3. **`website/content/docs/skills/aitask-pick/execution-profiles.md`** — add a
   `risk_evaluation` row to the **Standard Profile Fields** table (after
   `manual_verification_mode`): `bool` | "`true` runs the risk-evaluation step at the end
   of planning and offers risk-mitigation follow-ups; omit or `false` = disabled
   (opt-in, off by default)". Mirrors the `profiles.md` schema row landed by t884_2.
   Optionally add `risk_evaluation` to the example key list in
   `website/content/docs/concepts/execution-profiles.md` §"What it is" (low-value;
   include only if it reads naturally).

4. **NEW dedicated page `website/content/docs/workflows/risk-evaluation.md`** (weight `79`
   — between upstream-defect-followup `78` and manual-verification `80`, clustering it with
   the other automatic follow-up / verification workflows). Models its shape/voice on
   `workflows/upstream-defect-followup.md` and `workflows/manual-verification.md`. Documents
   the whole opt-in feature as one coherent narrative:
   - **Gating:** the `risk_evaluation` profile key (opt-in, off by default) — cross-link to
     [execution-profiles].
   - **The risk-evaluation planning step:** at the end of planning the agent assesses the
     two dimensions *separately* (code-health, goal-achievement) and writes a `## Risk`
     section into the plan, one subsection per dimension headed by its level. The two levels
     are written to the task's `risk_code_health` / `risk_goal_achievement` fields after the
     plan is approved — cross-link to [task-format] and [board reference].
   - **Propose-and-confirm mitigation flow:** from the `## Risk` section the agent proposes
     before/after mitigation tasks, recorded under a `### Planned mitigations` block.
     **before** = an independent task the original *depends on* (blocking edge); creating one
     reverts the original to `Ready` (shows **Blocked** in `ait ls`) and ends the session —
     implement the mitigation first, then re-pick the original. **after** = a
     post-implementation follow-up that blocks nothing. Created tasks are tracked in
     `risk_mitigation_tasks`.
   - **Force re-verification:** when a "before" mitigation lands, the original's plan is
     force re-verified on the next pick (the codebase changed underneath it).

5. **`website/content/docs/workflows/follow-up-tasks.md`** — keep it as the hub of short
   summaries (mirroring the existing "Automatic Upstream-Defect Follow-up" section). Add
   **two** short summary sections, each cross-linking to its dedicated page:
   - **"Automatic Risk-Mitigation Follow-up"** — 2–3 sentences on the before/after mitigation
     follow-ups (before=blocking dep, after=post-implementation), cross-linking to the new
     `risk-evaluation.md`.
   - **"Automatic Manual-Verification Follow-up"** — fills a **current gap** (only
     upstream-defect has a summary here today): 2–3 sentences on the Step 8c standalone
     manual-verification follow-up, cross-linking to
     `manual-verification.md#post-implementation-follow-up-step-8c`. *(Per user request during
     planning — small, in-scope consistency fix.)*

6. **`_index.md`:** no change — Docsy auto-builds the workflows menu from the content tree +
   `weight`; the new `risk-evaluation.md` (weight 79) slots in automatically. No manual index
   edit required.

## Reference patterns

- `follow-up-tasks.md` → "Automatic Upstream-Defect Follow-up" — section shape/voice
  for an opt-in, agent-driven follow-up flow.
- `website/content/docs/workflows/manual-verification.md` — model for a
  planning-integrated procedure.
- Existing rows in the three tables above (formatting/voice).

## Verification

- `cd website && hugo build --gc --minify` — clean, no broken refs/links.
- `cd website && ./serve.sh` — visually confirm the new rows/section render and the
  internal cross-links resolve.

## Notes for sibling tasks

Surfaces documented here are also covered behaviorally by the t884_8 manual-verification
sibling. t884_7 tracks the Codex/OpenCode skill ports.

See Step 9 (Post-Implementation) in the shared workflow for cleanup/archival/merge
(profile 'fast' → current branch, no separate branch).
