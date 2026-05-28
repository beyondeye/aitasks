---
Task: t835_6_audit_and_reorganize_adding_a_new_codeagent_doc.md
Parent Task: aitasks/t835_add_agy_antigravity_cli_support.md
Sibling Tasks: aitasks/t835/t835_1_*.md, aitasks/t835/t835_2_*.md, aitasks/t835/t835_3_*.md, aitasks/t835/t835_4_*.md, aitasks/t835/t835_5_*.md
Archived Sibling Plans: aiplans/archived/p835/p835_1_*..p835_5_*.md (primary evidence)
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Overview

Use the t835 agy implementation as empirical ground truth to audit,
reorganize, and surface `aidocs/adding_a_new_codeagent.md` so the
next code-agent addition has an accurate, well-ordered reference.

Runs LAST of all t835 children (after t835_1-5 archive) so the
audit can compare the doc against what was actually done.

Full plan in the task description; this plan file summarizes the
order of operations and verification criteria.

## Order of operations

1. **Audit pass.** For each of the doc's 23 sections, walk the
   corresponding t835 child plan(s) and diffs:
   ```bash
   git log --oneline main..HEAD -- .aitask-scripts/ seed/ install.sh .github/workflows/release.yml website/ .claude/
   ```
   For each section mark: accurate / stale / missing / dead.
   Capture findings inline so the reorganize pass has a checklist.

2. **Reorganize into logical implementation order** matching the
   t835 child split:
   - Phase A: Agent identity (current §§ 2-2c, 3-8, 10)
   - Phase B: Skill rendering (current §§ 1-1g, 9, 12-16)
   - Phase C: Setup, install, release (current §§ 17-22)
   - Phase D: User-facing documentation (current § 23)
   - Phase E: Cleanup & verification (NEW — distill t835_5)
   - Phase F: Tests checklist (current § 11)

   Add an "Implementation order" diagram / mapping table at the top
   so archived-plan references to old section numbers still resolve.

3. **Deduplicate content.** Consolidate known duplications:
   - Helper-doc copy-loop tuple (§§ 17e, 18d, 19b, 21) → canonical
     in §21, cross-ref elsewhere.
   - `SUPPORTED_AGENTS` lockstep (§ 2b) → verify no other section
     re-enumerates them.
   - `× N agents` message string (§ 8b) → check §§ 17/18 for
     repeats.
   - Apply DRY rule from `aidocs/planning_conventions.md` to any
     pattern appearing 3+ times.

4. **Surface in website docs.** New page at
   `website/content/docs/development/adding-a-new-code-agent.md` —
   thin Hugo wrapper with frontmatter, short purpose blurb,
   audience note, link to the aidocs file. Do NOT duplicate aidocs
   content. Add sidebar/index link from
   `website/content/docs/development/_index.md` (or equivalent).

5. **Verify CLAUDE.md pointer** — confirm
   `**Read `aidocs/adding_a_new_codeagent.md`**` is still correctly
   placed and references valid (renumbered) sections.

6. **Verify agent_runtime_guards_audit.md** — if t835_2 added new
   `{% if agent == "agy" %}` gates, ensure they are recorded.

## Verification

- Top-to-bottom walk of the reorganized doc, executing each section
  mentally against `git log --oneline main..HEAD -- .aitask-scripts/ seed/ install.sh .github/workflows/release.yml website/`. Every change in those paths maps to exactly one section.
- `cd website && ./serve.sh` — the new
  `development/adding-a-new-code-agent` page renders and the
  outbound link to aidocs resolves.
- Fresh-context read-through: open the reorganized aidocs as if
  planning a hypothetical new agent. Note remaining clarity gaps;
  fix or log as follow-up task.
- `grep -c "^## " aidocs/adding_a_new_codeagent.md` shows a
  reasonable section count (reorganization didn't lose content).

## Step 9 reference

Standard task-workflow Step 9 archive after Step 8 approval. When
this child archives, the **parent t835** archives automatically
(it has no other pending children).
