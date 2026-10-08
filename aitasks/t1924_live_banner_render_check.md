---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [task_workflow, skills]
anchor: 1913
followup_kind: risk_mitigation
created_at: 2026-10-08 23:18
updated_at: 2026-10-08 23:18
---

## Origin
Risk-mitigation ("after") follow-up for t1913, created at Step 8d after implementation landed.

## Risk addressed
banner paraphrased or reflowed in a live pane — "Agents may paraphrase or reflow the banner · severity: low"

## Goal
In a real session, confirm that the workflow-end banners added by t1913
(`.claude/skills/task-workflow/workflow-end.md`) render as intended.

## Verification Steps
- Run a fast-profile `/aitask-pick` to completion in Claude Code. Confirm that
  the `✔ aitask workflow complete — t<id> <name>` banner renders verbatim, as a
  fenced block, and is the last output of the run.
- End a run at an early exit, for example "Approve and stop here" at the plan
  checkpoint. Confirm that the `■ aitask workflow stopped — …` banner appears
  after the closing message, with `outcome: ready`.
- If Codex CLI or OpenCode is available, repeat the first check there and
  confirm the banner's first line is not paraphrased or reflowed.
