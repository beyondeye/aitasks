---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [documentation, reporting]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1544
followup_kind: upstream_defect
created_at: 2026-08-24 16:17
updated_at: 2026-11-15 18:15
completed_at: 2026-11-15 18:15
---

## Origin

Spawned from t1544_4 during Step 8b review.

## Upstream defect

- `.claude/skills/aitask-stats/SKILL.md:56 — CSV Export documents 7 columns (date, day_of_week, week_offset, task_id, labels, issue_type, task_type) against the 10 the script already emitted before this task; it is now 12.`
- `.claude/skills/aitask-stats/SKILL.md:16-19 — the Options list omits -w/--week-start, which the CLI has supported for a long time.`
- `.claude/skills/aitask-stats/SKILL.md:44-50 — the report-sections list stops at 7 and predates Pipeline Timing, By Code Agent, By LLM Model and Verified Model Rankings.`
- `.opencode/skills/aitask-stats/SKILL.md:1 — this and the .agents/ copy have diverged from the .claude/ source of truth (differing md5s), so any fix must sweep all three trees.`

## Diagnostic context

Found while extending `write_csv` from 10 to 12 columns in t1544_4. The doc was
already wrong before that change — it describes a 7-column export, so the drift
predates both t1544 and the column additions.

All four are pre-existing documentation drift in files t1544_4 does not touch.
t1544_4 is gated on `risk_evaluated` only and
`aitask_gate.sh procedure-gates 1544_4` reported no `docs_updated` gate, so
nothing in that task's flow would have caught or fixed them.

Per CLAUDE.md the source of truth is the Claude Code implementation in
`.claude/skills/`; the Codex CLI (`.agents/skills/`) and OpenCode
(`.opencode/skills/`) copies are adapted from it and must be updated in the
same sweep.

## Suggested fix

Re-derive all three lists from the current `aitask_stats.py`: the `write_csv`
header (12 columns), `parse_args` (which by then also carries `--backlog-weeks`
and `--csv-backlog`), and the `render_text_report` section order. Then port to
`.agents/` and `.opencode/` and run
`./.aitask-scripts/aitask_skill_verify.sh`.

Note t1544_6 owns this feature's documentation and will cover the two new
report sections; this task is about the pre-existing drift, so coordinate to
avoid double-editing the same lists.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **⏭ gate:risk_evaluated** run=2026-11-15T16:15:45Z status=skip attempt=1 type=machine
>
> Note: no code change; defects already fixed by t1544_6
