---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1468_5]
issue_type: chore
status: Implementing
labels: [task_metadata, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1468
implemented_with: claudecode/opus5
created_at: 2026-08-10 16:31
updated_at: 2026-08-13 22:37
---

## Context

Parent: t1468 — mark auto-spawned follow-up tasks with a machine-readable kind.
Depends on **t1468_1** (the field and the `--followup-kind` flag); best run last,
after t1468_3/_4 make the result visible for review.

Forward-only marking leaves the existing backlog unchanged — and the backlog is
where the pain actually is. This child retro-classifies the follow-ups already on
disk.

Read the parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md`.

## Pre-phase (risk mitigation — do this FIRST)

**`backfill_single_revertible_commit`.** Require a **clean working tree** before
`--apply`, then land **two separate commits** — the framework forbids mixing code
with task/plan files, and task data lives on the `aitask-data` branch:

1. the backfill script itself, via plain `git`;
2. the field writes **plus** the reviewed classification table, via one
   `./ait git` commit over task data only.

The table is not a loose artifact: write it into this task's plan file
(`aiplans/p1468/p1468_6_*.md`, "Final Implementation Notes"), which is already on
the data branch and is the framework's durable record. A mis-classification is
then a revert of commit 2 alone.

## The corpus is live — do not hard-code a total

The parent task file quotes "168 of 382". Re-measured during planning: **385**
active tasks, **171** follow-ups. It will have moved again by the time this runs.

**The script must derive its counts at run time.** The acceptance check is
"every follow-up is either classified or listed as reviewed residue" — never a
hard-coded total.

## Classification rules — apply IN THIS ORDER

| kind | detection | count at planning |
|---|---|---|
| `carry_over` | body has `Carry-over of deferred manual-verification items` | 7 |
| `manual_verification` | `issue_type: manual_verification` | 62 |
| `risk_mitigation` | body matches `Risk-mitigation \("(before\|after)"\)` | 54 |
| `upstream_defect` | body has `^## Upstream defect` **or** `Spawned from t<id> during Step 8b review` | 43 |
| `verification_failure` | body has `^## Failed verification item from t` | 4 |
| `review_finding` | frontmatter `labels` contains `review` | 1 |
| `qa_test_gap` | `labels` contains `qa` | 0 |
| `docs_gap` | filename matches `docs_gaps_since_` | 0 |

**Order is load-bearing:** `carry_over` is a *subset* of manual-verification and
must win. The rest are disjoint in the current corpus — assert that rather than
assuming it.

**The last three rules are the ones that make the parent's acceptance criterion
reachable.** The parent task file's own table sums to 167, not 168, and silently
drops the single review finding —
`aitasks/t804_planning_md_skill_authoring_review.md`
(`labels: [review, skill, task-workflow]`), which matches no body rule.
`.claude/skills/aitask-review/SKILL.md.j2:187` hard-codes `labels: "review"` on
every task it creates, so the label *is* the reliable marker.
`qa_test_gap` and `docs_gap` have zero active instances today — include the rules
anyway so the script needs no editing the first time one appears, and assert the
zero explicitly rather than leaving it unexamined.

## Requirements

- One reviewable script (`.aitask-scripts/aitask_followup_backfill.sh` or a
  Python helper), **dry-run by default**, printing a per-task classification
  table: id · matched rule · assigned kind.
- `--apply` performs the writes, through
  `aitask_update.sh --batch --followup-kind` — the sanctioned path, so nothing
  else in the frontmatter is lost. **Never hand-edit the files.**
- **Report violations of the MV cross-field invariant** (`followup_kind:
  manual_verification` on a task whose `issue_type` is something else) as residue
  rather than writing them — t1468_1 makes that pair unwritable through the CLI,
  so a pre-existing violation must surface, not fail mid-run.
- **Document the scope decision:** active corpus only, or archived tasks too.
- **Residue is a first-class output.** Precision is not 100%: 41 of 42
  upstream-defect hits carry the exact Step 8b sentence; the outlier
  `t1246_fix_codeagent_tests_v5_model_drift.md` is a genuine upstream defect
  written in freeform prose and will not match. An unmatched task is an explicit
  reviewed outcome, not a silent zero.

## Verification steps

1. Dry run on the real corpus; **review the classification table with the user
   before any write**.
2. Counts derived at run time; the script prints them and does not compare
   against a baked-in number.
3. Rule precedence proven: a task matching both `carry_over` and
   `manual_verification` is classified `carry_over` (add a fixture if none
   exists naturally).
4. `t804_planning_md_skill_authoring_review.md` is classified `review_finding`.
5. `qa_test_gap` and `docs_gap` counts are asserted (zero today) rather than
   silently absent.
6. Residue list is non-empty-and-explained rather than assumed empty; confirm
   `t1246` appears in it.
7. Clean tree before `--apply`; two commits as described; spot-check ~5 tasks per
   category on disk afterwards.
8. Round-trip safety: pick a backfilled task, run an unrelated
   `ait update --status`, confirm `followup_kind` survives (t1468_1's guarantee,
   verified on real data).
9. `shellcheck` the new script; `bash tests/run_all_python_tests.sh` (read the
   LAST line for the verdict).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T19:37:52Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-13T20:23:46Z status=pass attempt=1 type=human
