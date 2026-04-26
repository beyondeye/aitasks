---
priority: medium
effort: medium
depends: [624]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [624]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 12:25
updated_at: 2026-04-26 10:22
completed_at: 2026-04-26 10:22
boardidx: 10
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t624

## Verification Checklist

- [x] Run `ait setup` in a fresh scratch project directory (no existing git repo) and confirm: — PASS 2026-04-26 10:22
- [x] Install prompts happen smoothly — PASS 2026-04-26 10:19
- [x] AGENTS.md created at project root with >>>aitasks/<<<aitasks markers and new Folded/Manual Verification sections. — PASS 2026-04-26 10:19
- [x] CLAUDE.md and GEMINI.md also contain the updated shared seed content. — PASS 2026-04-26 10:19
- [x] tmux session name prompt appears with default "aitasks" — PASS 2026-04-26 10:21
- [x] Overwriting session name with a custom value writes that value; idempotent re-run says "already configured". — PASS 2026-04-26 10:21
- [x] With lazygit installed: setup detects it and writes `git_tui: lazygit` to project_config.yaml — PASS 2026-04-26 10:19
- [x] Commit banner "READY TO COMMIT N FRAMEWORK FILES" appears; answering Y produces `ait: Add aitask framework` commit with CLAUDE.md, GEMINI.md, AGENTS.md, .gemini/, .opencode/, opencode.json tracked. — PASS 2026-04-26 10:21
- [x] Post-commit `git ls-files | grep -E '^(CLAUDE|GEMINI|AGENTS)\.md$'` lists all three. — PASS 2026-04-26 10:22
- [x] Answering N at the commit prompt shows the "UNTRACKED" list warning. — PASS 2026-04-26 10:22
- [x] Re-run `ait setup` on same project — PASS 2026-04-26 10:22
