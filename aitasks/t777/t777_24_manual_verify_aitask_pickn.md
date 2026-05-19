---
priority: medium
effort: medium
depends: [t777_26]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t777_6]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-18 15:52
updated_at: 2026-05-19 10:14
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] Fast profile, parent-task path: in a fresh Claude session, type `/aitask-pickn 16` (or any open parent task ID). Expected: auto-confirm fires inline (no AskUserQuestion); flow lands in `.claude/skills/task-workflown-fast-/SKILL.md` at Step 3; userconfig email resolves silently. Abort before any state-changing tool call. — PASS 2026-05-19 09:56
- [x] Default profile, interactive path: in a fresh Claude session, type `/aitask-pickn --profile default 16`. Expected: the stub strips `--profile default`, dispatches to `aitask-pickn-default-/SKILL.md`, interactive AskUserQuestion for parent confirmation appears. Cancel via "No, abort". — PASS 2026-05-19 10:02
- [x] Child task, fast profile: in a fresh Claude session, type `/aitask-pickn 777_6` (this task — PASS 2026-05-19 10:12
- [x] Remote profile (dry-run only): run `./ait skillrun pick --profile remote --dry-run 16`. Expected: synthesized Claude argv with `/aitask-pick --profile remote 16` (note: this exercises live aitask-pick, not aitask-pickn, since skillrun uses the public skill name). For aitask-pickn equivalent, manually invoke `./ait skill render aitask-pickn --profile remote --agent claude` and inspect `.claude/skills/aitask-pickn-remote-/SKILL.md`. — PASS 2026-05-19 10:13
- [x] Stub-marker spot-check (all 4 agents): visually read `.claude/skills/aitask-pickn/SKILL.md`, `.agents/skills/aitask-pickn/SKILL.md`, `.gemini/commands/aitask-pickn.toml`, `.opencode/commands/aitask-pickn.md`. Each must contain `aitask_skill_resolve_profile.sh aitask-pickn`, `ait skill render aitask-pickn`, and the `Dispatch via Read-and-follow` marker. — PASS 2026-05-19 10:14
- [x] Rendered closure inspection (claude/fast): open `.claude/skills/aitask-pickn-fast-/SKILL.md`. Confirm: (a) frontmatter `name: aitask-pickn-fast` (matches dir minus trailing dash); (b) no `{% if`, `{% else`, `{% endif`, `{{ profile.` markers leak; (c) auto-confirm text appears inline at both `skip_task_confirmation` sites; (d) task-workflown references rewritten to `.claude/skills/task-workflown-fast-/...`. — PASS 2026-05-19 10:14
- [x] Original `/aitask-pick` regression check: in a fresh Claude session, run `/aitask-pick 16` and confirm it still works exactly as before (live skill untouched by this rollout). Abort before destructive ops. — PASS 2026-05-19 10:14
