---
priority: medium
effort: medium
depends: [866]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [866]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 11:32
updated_at: 2026-06-03 10:12
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t866

## Verification Checklist

- [defer] Launch `ait codeagent invoke qa <archived-task-id>` with a `codex/*` agent string — DEFER 2026-06-03 10:12 auto: default-mode half confirmed (dry-run launches 'codex -m gpt-5.4 $aitask-qa 866' directly, no /plan helper). Live 'request_user_input surfaces' needs interactive Codex session
- [defer] Launch `ait codeagent invoke explain <source-file>` with a `codex/*` agent string — DEFER 2026-06-03 10:12 auto: default-mode half confirmed (dry-run launches 'codex -m gpt-5.4 $aitask-explain <file>' directly, no /plan helper). Live request_user_input surfacing needs interactive Codex session
- [x] Launch `ait codeagent invoke pick <task-id>` with a `codex/*` agent string — PASS 2026-06-03 10:12 auto: dry-run shows codeagent invoke pick routes through aitask_codex_plan_invoke.py (/plan typed -> composer shows /plan)
- [x] Launch `ait codeagent invoke explore` with a `codex/*` agent string — PASS 2026-06-03 10:12 auto: dry-run shows codeagent invoke explore routes through aitask_codex_plan_invoke.py (/plan typed -> composer shows /plan)
- [x] Run `ait skillrun qa <id> --agent-string codex/<model>` then `ait skillrun pick <id> --agent-string codex/<model>` — PASS 2026-06-03 10:12 auto: skillrun qa -> direct codex launch (no aitask_codex_plan_invoke); skillrun pick -> aitask_codex_plan_invoke helper. Parity with codeagent confirmed via --dry-run
