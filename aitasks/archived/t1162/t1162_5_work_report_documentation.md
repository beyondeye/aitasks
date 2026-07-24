---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: [t1162_4]
issue_type: documentation
status: Done
labels: [documentation, reporting]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1162
implemented_with: claudecode/opus4_8
created_at: 2026-07-22 10:46
updated_at: 2026-07-24 11:50
completed_at: 2026-07-24 11:50
---

## Context

Fifth child of t1162. Documents the work-report feature across the website: skill reference, workflow page, board shortcut, and operation registration. Parent plan: `aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md` (t1162_5 section). Write per `aidocs/framework/documentation_conventions.md`: current-state-only (no version history), genericize supported-agent references, describe the projection as data-derived and clearly labeled.

## Key Files to Create/Modify

- `website/content/docs/skills/aitask-work-report.md` (new) + a row in the categorized table in `website/content/docs/skills/_index.md`.
- `website/content/docs/workflows/work-report.md` (new) + a bullet in the hand-curated `website/content/docs/workflows/_index.md` (manual page list — new workflow pages need an explicit bullet).
- `website/content/docs/tuis/board/reference.md` — add `w` / Work Report / context to the Keyboard Shortcuts table.
- `website/content/docs/tuis/board/how-to.md` — narrative: focus a column, press `w`, adjust column/task selections, launch the agent.
- `website/content/docs/commands/codeagent.md` — add `work-report` to the supported-operations list.

## Content requirements

- Cover: column/task selection (board `w` and interactive skill paths), horizon labeling (Today / This week / custom), report structure (focus summary, column-grouped priorities with task IDs, completion projection, blockers/manager-asks), the fail-closed stale-selection behavior, the completion projection (historical throughput, 7/30-day windows, projection-not-commitment framing, insufficient-history fallback), and that no report file is written.
- Do NOT document `diffviewer` interactions; keep the board TUI list unchanged.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- All new internal links resolve (relref/link check during build).
- Skill/workflow index entries render (grep the built site or verify page front matter).

## AC amendments (agreed during implementation)

Three scope decisions confirmed with the user at planning time; the original
acceptance criteria above are superseded on these points:

1. **Corrected feature description.** The "Content requirements" above describe
   the completion projection as using "historical throughput, 7/30-day
   windows". That is drifted — it describes a design replaced during t1162_1.
   The landed behavior is a selectable estimator (`dow` per-weekday averages by
   default, `flat` as the alternative) over a 90-day default window, and the
   projection is **opt-in**, not a default section. The docs document the
   landed behavior.
2. **Backfill the whole operations table.** `website/content/docs/commands/codeagent.md`
   was missing `explore-relay`, `shadow`, and `learn` in addition to
   `work-report`. All four rows are added, so the table matches
   `SUPPORTED_OPERATIONS` in `.aitask-scripts/aitask_codeagent.sh`.
3. **Ship a doc-list drift guard.** `tests/test_website_doc_lists.sh` asserts
   that every supported code-agent operation has a row in `codeagent.md`, and
   that every `aitask-*` skill page is linked from `skills/_index.md`. This
   also closes a pre-existing gap (`/aitask-add-model` had no index row).

A fourth item was folded in from t1162_4's notes-for-siblings: document how to
customize the work-report code-agent default and how to rebind the board `w`
key.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-24T08:15:09Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-24T08:42:38Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-24T08:50:39Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3f34adbbe95bc8a4

> **✅ gate:risk_evaluated** run=2026-07-24T08:50:39Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1162_5/risk_evaluated_2026-07-24T08:50:39Z-risk_evaluated-a1.log`
