---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [review, skill, task-workflow]
created_at: 2026-05-19 17:22
updated_at: 2026-05-19 17:22
boardcol: now
boardidx: 60
---

Address findings from a Skill Authoring Best Practices review of `.claude/skills/task-workflow/planning.md`.

**Important constraint (from user):** For any numbering or section-name change made below, search all other markdown files inside `.claude/skills/task-workflow/` (and other related skill dirs that consume this file: `.agents/skills/task-workflow/`, `.opencode/skills/task-workflow/`, `.gemini/skills/task-workflow/` if present) and update every cross-reference. Do **not** leave dangling `§6.1` / `1b.` / "Verify Decision sub-procedure" pointers behind.

---

## Findings to address

### #1 — DRY violation in plan_preference branches (HIGH)

**Location:** `.claude/skills/task-workflow/planning.md:29-120`

The "Profile-driven plan preference" + "Verify Decision sub-procedure" body is duplicated across both Jinja branches (`{% if profile.plan_preference is defined ... %}` lines 29–72 and `{% else %}` lines 73–120). About 45 lines of body content are repeated almost verbatim — only variable references differ (`{{ profile.name }}` vs `<name>`, `{{ profile.plan_verification_required | default(1) }}` vs `<required>`).

**Suggested fix:** Extract the shared decision-flow body into a single block outside the conditional, or move it to a dedicated reference file like `verify-decision.md`. Keep only the variable-binding preamble inside `{% if/else %}`.

### #2 — DRY violation in post_plan_action branches (MEDIUM)

**Location:** `.claude/skills/task-workflow/planning.md:337-362`

`post_plan_action` resolution is also duplicated across `{% if %}` / `{% else %}` branches with the same "Display" / "Remote Drift Check" instructions.

**Suggested fix:** Apply the same factoring pattern as #1.

### #3 — Numbering glitch `1.` → `1b.` → `2.` (MEDIUM)

**Location:** `.claude/skills/task-workflow/planning.md:137`

The numbered list reads `1.` `1b.` `2.`, suggesting `1b.` was patched in retroactively.

**Suggested fix:** Either renumber to `1.` `2.` `3.`, or fold `1b.` into `1.` as an addendum sentence.

### #4 — Verify-path append reminder duplicates content (MEDIUM)

**Location:** `.claude/skills/task-workflow/planning.md:294-296`

The "Verify-path append reminder" paragraph duplicates content already specified at lines 130–144. A future editor changing one will likely leave the other stale.

**Suggested fix:** Keep one canonical description and have the second site refer to it by anchor (e.g., "see §6.1.a verify-path append step").

### #5 — Inconsistent terminology "child subtasks" vs "child tasks" (MEDIUM)

**Locations:** `.claude/skills/task-workflow/planning.md:189` ("break it into child subtasks"), `:192` ("If creating child tasks"), `:254` ("Created <N> child tasks").

**Suggested fix:** Standardize on "child tasks" throughout. Check other task-workflow markdown files for matching language.

### #6 — Table of Contents incomplete (MEDIUM)

**Location:** `.claude/skills/task-workflow/planning.md:6-13`

Lists only 5 anchors but skips significant sub-sections readers may navigate to: Ad-Hoc Fold Procedure, Complexity Assessment / child-task creation flow, Manual verification sibling, Child task checkpoint, file-naming/metadata header subsection.

**Suggested fix:** Either add anchors for those sub-sections (preferred — Skill Authoring guide says >100-line reference files need usable ToCs), or annotate that 6.1 contains multiple sub-flows enumerated below.

### #7 — Historical/motivational tail on Approve-and-stop option (LOW)

**Location:** `.claude/skills/task-workflow/planning.md:395`

The sentence "...replaces the infeasible context-usage auto-detection by letting the user make the call based on their own HUD" is rationale, not execution guidance. Best-practices guide says token cost must be justified by execution value.

**Suggested fix:** Drop the sentence (or move it to a design doc / `aidocs/`).

### #8 — Broken cross-reference `§6.1` to a sub-paragraph (LOW)

**Location:** `.claude/skills/task-workflow/planning.md:294`

Cross-reference reads "described in §6.1 ('After `ExitPlanMode` on the verify path')" but `§6.1` resolves to the heading "## 6.1: Planning" while the target is a bolded paragraph inside it. The anchor will not link cleanly.

**Suggested fix:** Promote that paragraph to a real `###`-level subheading (e.g., `### 6.1.a: Verify-path append`), then link to its slug. After promotion, re-run the cross-reference search (per the user constraint) to catch any other dangling pointers.

---

## Verification

- After all edits, render the skill via `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile default --agent claude` (and any other consumers of planning.md) and ensure no Jinja errors.
- `grep -rn "§6.1\|Verify Decision sub-procedure\| 1b\." .claude/skills/task-workflow/ .agents/skills/task-workflow/ .opencode/skills/task-workflow/ .gemini/skills/task-workflow/ 2>/dev/null` should not surface stale references.
- Run `./.aitask-scripts/aitask_skill_verify.sh` per CLAUDE.md.
- Smoke-test by picking a task that triggers Step 6 (plan creation) under both `plan_preference: verify` and no-profile flows to confirm behavior is unchanged.
