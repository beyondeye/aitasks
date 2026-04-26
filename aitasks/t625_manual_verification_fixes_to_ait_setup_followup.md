---
priority: medium
effort: medium
depends: [624]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [624]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 12:25
updated_at: 2026-04-26 10:14
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

- [ ] Run `ait setup` in a fresh scratch project directory (no existing git repo) and confirm:
- [ ] Install prompts happen smoothly — git init accepted, data branch accepted.
- [ ] AGENTS.md created at project root with >>>aitasks/<<<aitasks markers and new Folded/Manual Verification sections.
- [ ] CLAUDE.md and GEMINI.md also contain the updated shared seed content.
- [ ] tmux session name prompt appears with default "aitasks" — accepting default writes `default_session: aitasks` to aitasks/metadata/project_config.yaml.
- [ ] Overwriting session name with a custom value writes that value; idempotent re-run says "already configured".
- [ ] With lazygit installed: setup detects it and writes `git_tui: lazygit` to project_config.yaml — no "write failed" warning.
- [ ] Commit banner "READY TO COMMIT N FRAMEWORK FILES" appears; answering Y produces `ait: Add aitask framework` commit with CLAUDE.md, GEMINI.md, AGENTS.md, .gemini/, .opencode/, opencode.json tracked.
- [ ] Post-commit `git ls-files | grep -E '^(CLAUDE|GEMINI|AGENTS)\.md$'` lists all three.
- [ ] Answering N at the commit prompt shows the "UNTRACKED" list warning.
- [ ] Re-run `ait setup` on same project — all writes are idempotent, no duplicate tmux: blocks, no new commits beyond any re-check necessary.
