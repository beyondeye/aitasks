---
Task: t1468_6_backfill_existing_followup_kinds.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_5_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
---

# p1468_6 — Backfill `followup_kind` on existing follow-ups

Context, the rule table and the residue discipline are in
`aitasks/t1468/t1468_6_backfill_existing_followup_kinds.md`.

**Precondition:** t1468_1 has landed. Best run after t1468_3/_4, so the result is
visually reviewable on the board and in `ait ls`.

## Pre-phase (risk mitigation — before `--apply`)

**`backfill_single_revertible_commit`.**

1. Require a **clean working tree**; abort otherwise.
2. Land **two separate commits** — the framework forbids mixing code with
   task/plan files, and task data lives on the `aitask-data` branch:
   - the backfill script, via plain `git`;
   - the field writes **plus** the reviewed classification table, via one
     `./ait git` commit over task data only.
3. The table is not a loose artifact: the script writes it into **this plan
   file**, under "Final Implementation Notes". That is already on the data branch
   and is the framework's durable record, so both requirements are satisfiable at
   once.

A mis-classification is then a revert of commit 2 alone.

## Implementation steps

### 1. The script

`.aitask-scripts/aitask_followup_backfill.sh` (or a Python helper under `lib/`
with a thin `.sh` wrapper, matching the family style).

- **Dry-run by default.** `--apply` performs writes.
- Prints a per-task classification table: `task id · matched rule · assigned
  kind`, plus a summary count per kind and a residue section.
- Writes go through `aitask_update.sh --batch <id> --followup-kind <kind>` — the
  sanctioned path, so nothing else in the frontmatter is lost. **Never hand-edit
  the task files.**
- `--scope active|all` for the documented scope decision (default `active`;
  record the choice and its rationale in the notes).

### 2. Rules — order is load-bearing

Apply in this order; first match wins:

| order | kind | detection |
|---|---|---|
| 1 | `carry_over` | body has `Carry-over of deferred manual-verification items` |
| 2 | `manual_verification` | `issue_type: manual_verification` |
| 3 | `risk_mitigation` | body matches `Risk-mitigation \("(before\|after)"\)` |
| 4 | `upstream_defect` | body has `^## Upstream defect` **or** `Spawned from t<id> during Step 8b review` |
| 5 | `verification_failure` | body has `^## Failed verification item from t` |
| 6 | `review_finding` | frontmatter `labels` contains `review` |
| 7 | `qa_test_gap` | `labels` contains `qa` |
| 8 | `docs_gap` | filename matches `docs_gaps_since_` |

`carry_over` is a strict **subset** of `manual_verification` and must be tested
first. Rules 3–8 are disjoint in the current corpus — **assert that** rather than
assuming it: a task matching two of them is a rule bug and should surface as a
conflict, not be silently resolved by ordering.

Rules 6–8 are the ones the parent task file omits; without rule 6 the single
review finding (`aitasks/t804_planning_md_skill_authoring_review.md`) is
unclassifiable and the parent's acceptance criterion cannot be met.
`.claude/skills/aitask-review/SKILL.md.j2:187` hard-codes `labels: "review"` on
every task it creates, so the label is the reliable marker.

### 3. Counts are derived, never asserted against a constant

The parent task file quotes "168 of 382"; planning re-measured **385 / 171**; it
will have moved again. The script derives every count at run time and prints it.
The acceptance check is *"every follow-up is classified or listed as reviewed
residue"* — never a hard-coded total.

### 4. Residue is a first-class output

- Tasks matching no rule that nonetheless look like follow-ups. Known example:
  `t1246_fix_codeagent_tests_v5_model_drift.md` — a genuine upstream defect
  written in freeform prose (41 of 42 upstream hits carry the exact Step 8b
  sentence; this is the outlier).
- **MV cross-field violations:** any task that would receive
  `followup_kind: manual_verification` while its `issue_type` is something else.
  t1468_1 makes that pair unwritable through the CLI, so a pre-existing violation
  must be *reported*, not attempted mid-run.

Report both; do not write either.

### 5. Run it

1. Dry run on the real corpus.
2. **Present the classification table to the user and get review before any
   write.** This is the acceptance criterion, not a courtesy.
3. `--apply` on a clean tree; two commits as above.

## Verification

1. Dry-run table reviewed with the user before any write.
2. Counts derived at run time; no baked-in total anywhere in the script or tests.
3. Precedence proven: a task matching both `carry_over` and
   `manual_verification` classifies as `carry_over` (add a fixture if the corpus
   does not supply a clean case).
4. Disjointness assertion fires as a conflict, not a silent first-match, when two
   of rules 3–8 hit the same task.
5. `t804_planning_md_skill_authoring_review.md` classifies as `review_finding`.
6. `qa_test_gap` and `docs_gap` counts are asserted (zero at planning time)
   rather than silently absent — an unexamined zero is not evidence.
7. Residue list is non-empty-and-explained rather than assumed empty; `t1246`
   appears in it.
8. Clean tree before `--apply`; the two commits land as described; spot-check ~5
   tasks per category on disk afterwards.
9. **Round-trip safety on real data:** pick a backfilled task, run an unrelated
   `ait update --status`, confirm `followup_kind` survives. This exercises
   t1468_1's guarantee against the actual corpus rather than a fixture.
10. `ait ls --followup-kind risk_mitigation` returns a plausible count and the
    board shows the glyphs (leans on t1468_3/_4).
11. `shellcheck` the new script; `bash tests/run_all_python_tests.sh` — read the
    **last** line.

## Notes for sibling tasks

This is the last child. When it lands, re-run the parent's end-to-end
verification list in
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md`
before archiving the parent.
