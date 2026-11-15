---
Task: t1363_fix_board_work_report_key_docs_and_ait_help_gate_pass.md
Base branch: main
Output branch: main
---

# t1363 — Fix the work-report key in docs (`W` → `w`); `ait --help` gate pass already done

## Context

t1361 found that the board docs give the work-report key as uppercase **W**.
The real default binding is lowercase `w`
(`.aitask-scripts/board/aitask_board.py:2319` — `Binding("w", "work_report", "Work Report")`;
there is no `Binding("W", …)` anywhere under `.aitask-scripts/board/`).
`reference.md:65` and `workflows/work-report.md:27` already say `w`.

The task's second item — adding `gate pass` to the `ait --help` "Gates:" block —
**is already done** on main: `ait:65` reads
`gate pass      Sign a human gate (writes the code-bound witness)` (t1270,
e818128b6, as the t1647_6 note says, now confirmed). No edit is needed; the plan
records it as resolved upstream.

## Changes

Doc convention (confirmed in the same file, e.g. `how-to.md:53` "Press **x**",
`:97` "Press **m**"): bold, lowercase key letter.

1. `website/content/docs/tuis/board/how-to.md`, § "How to Generate a Work Report"
   — replace the three `**W**` occurrences with `**w**`:
   - line 387: `2. Press **W**` → `2. Press **w**`
   - line 394: `The **W** key is column-scoped…` → `The **w** key is column-scoped…`
   - line 398: `To rebind **W** itself…` → `To rebind **w** itself…`
2. `website/content/docs/commands/codeagent.md:302` — same defect, outside the
   task's named section but found by the sweep:
   `Pressing **W** on the board` → `Pressing **w** on the board`.

Nothing else in `website/content/docs` names `**W**` or `` `W` `` (grep
checked). No test pins these strings.

## Verification

- `grep -rn '\*\*W\*\*' website/content/docs` → no hits for the work-report key.
- `cd website && python3 check_links.py --build` (required after editing pages
  under `website/content/`) → passes.

## Step 9

Post-implementation: commit the doc change (`documentation:`/`bug:` type per
task's issue_type → `bug: … (t1363)`), then archive per Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
