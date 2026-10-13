---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_fold, bash_scripts, gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-12 22:40
updated_at: 2026-10-13 11:37
completed_at: 2026-10-13 11:37
---

## Origin
Found downstream in the thinking_app repo (its t295, Step 8b review, 2026-10-12), which consumes this framework. The defect is in the framework, so it is tracked here.

## Upstream defect
- `.aitask-scripts/aitask_fold_content.sh:111` — folded bodies are emitted verbatim (`extract_body "$f"`), so a folded task's `## Gate Runs` and `## Inbox` blocks land in the primary's body, where another task's gate history can parse as the primary's ledger and its notes appear in a second inbox section.
- `.aitask-scripts/aitask_fold_content.sh:82` — `--primary-stdin` emits stdin verbatim (`primary_body=$(cat)`), without the frontmatter stripping the file path gets through `extract_body` (line 84). Piping the primary task file (the natural way to avoid reading and writing the same file) duplicates its frontmatter into the body.

## Diagnostic context
- A downstream fold of two tasks into one primary produced a merged body containing:
  - one folded task's `## Gate Runs` section, with a `plan_approved` pass and a `plan_approved` fail;
  - two extra `## Inbox` sections, with `✉ note` blocks addressed to the folded tasks.
- Applied unchanged via `aitask_update.sh --desc-file -`, the primary would have carried two ledgers. The gate parser is section-based (`gate_ledger.py`, `SECTION_HEADER = "## Gate Runs"`), so the folded task's history could be read as the primary's. The downstream session rewrote the folded copies as plain reference prose by hand.
- Separately, piping the whole primary task file to `--primary-stdin` produced a second frontmatter block inside the body, which was removed by hand.

## Suggested fix
- In `aitask_fold_content.sh`, demote each folded body's `## Gate Runs` and `## Inbox` sections, for example to `### t<N> gate history (reference only)` / `### Notes t<N> received`, with the `> **✅ gate:` / `> **✉ note:` markers rewritten so neither parser picks them up.
- Run stdin through `extract_body` when it starts with a frontmatter block.
- Add tests for both cases: a folded task with a ledger and an inbox, and `--primary-stdin` fed a whole task file.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-13T07:52:25Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-13T08:36:06Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-13T08:37:32Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f11e88a349281722

> **✅ gate:risk_evaluated** run=2026-10-13T08:37:32Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1962/risk_evaluated_2026-10-13T08:37:32Z-risk_evaluated-a1.log`
