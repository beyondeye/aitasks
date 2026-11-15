---
Task: t2299_4_sitrep_recovery_skill_and_docs.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_1_*.md, aitasks/t2299/t2299_2_*.md, aitasks/t2299/t2299_3_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
---

# Plan: sitrep skill and docs for recovery items (t2299_4)

## Context

The first three children added crash recovery to sitrep: the store support, the
detector, and the refresh, monitor and TUI wiring. This child teaches
`/aitask-sitrep` to triage recovery items and documents the feature, using
current-state wording.

The description must follow what actually shipped, so read the three archived
sibling plans first, especially their Final Implementation Notes.

## Steps

1. **Skill** (`.claude/skills/aitask-sitrep/SKILL.md.j2`). Make the edits the
   task file lists:
   - the list section: the `recover:` ref, the categories, and the survey passage;
   - the writing rules: recovery items are detector/refresh-owned;
   - `>w` with the theme `crashed-agents`;
   - `>p` with the rank order;
   - cleanup flags for stale locks and orphans;
   - the dismissal and episode rules;
   - the guardrail additions.

   Keep the Capabilities section the single source of the menu.
2. **Goldens.** Regenerate them per `aidocs/framework/skill_authoring_conventions.md`.
   Run `aitask_skill_verify.sh`, `tests/test_skill_render_aitask_sitrep.sh` and
   `tests/test_sitrep_skill_contract.sh`.
3. **`aidocs/framework/sitrep.md`.** Add:
   - the components row;
   - store: the ref, format 3, `recovery-apply` and its rules, the episode key and the dismissal exception;
   - the decision table, as a summary plus a pointer to `lib/sitrep_crash.py`;
   - the refresh `recovery` class;
   - the maintenance order;
   - the TUI `recover` key;
   - the tests table rows.
4. **Website.** Read `aitasks/metadata/doc_update_guide.md` first. Then:
   - `workflows/sitrep.md`: a new "Crashed agents" section, and amend step 6's dismissal sentence;
   - `tuis/sitrep/reference.md`: the What-to-do texts and the detector output lines;
   - `tuis/sitrep/how-to.md`: "How to resume crashed work";
   - `workflows/crash-recovery.md`: a cross-link.
5. **Hunk-scoped staging of `crash-recovery.md`.** The file carries t2284's
   uncommitted hunk. Commit only this task's hunk:
   1. Save the foreign hunk aside as a patch: `git diff -- <file> > /scratch/foreign.patch`, taken before editing.
   2. After editing, take `git diff -- <file>` again.
   3. Build the patch of only this task's hunk: either filter the combined diff with `filterdiff` or a small script, or create it from `git diff` of a temporary copy. Verify it with `git apply --cached --check`.
   4. `git apply --cached`, then `git diff --cached -- <file>` must show only this task's lines.

   Never restore or stash the file.
6. **Link checks.** Run `cd website && python3 check_links.py --build`, and
   offer `check_link_relevance.py`.
7. **Note to t2199.** `./ait note 2199 --from 2299_4 --file -` names the skill
   sections to port.
8. **Doc review.** Optionally run `/aitask-docs-review` on the changed website
   pages before committing.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/test_skill_render_aitask_sitrep.sh`
- `bash tests/test_sitrep_skill_contract.sh`
- `cd website && python3 check_links.py --build`
- `git diff --cached` shows only this task's hunks.

## Risk

### Code-health risk: low
- The hunk-scoped staging could commit the other task's hunk, or lose it. · severity: medium · → mitigation: dry-run with `git apply --cached --check`, inspect the staged diff, and never change the work tree's content
- Golden drift if the template edits are not regenerated. · severity: low · → mitigation: `aitask_skill_verify.sh`

### Goal-achievement risk: low
- The docs could describe the plan rather than what shipped. · severity: low · → mitigation: read the siblings' Final Implementation Notes first

## Step 9

Post-implementation: commit this task's paths only (`documentation: … (t2299_4)`, with the skill change possibly as `feature:`), then archive via Step 9.
