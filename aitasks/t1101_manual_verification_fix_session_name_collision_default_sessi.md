---
priority: medium
effort: medium
depends: [1099]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1099]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-01 11:51
updated_at: 2026-07-01 12:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1099

## Verification Checklist

- [ ] [stats] Register 2+ repos with NO tmux.default_session (both -> "aitasks"); open `ait stats` — confirm two distinct project-named rows, each with its own totals (no cache bleed).
- [ ] [stats] Labels are project-oriented — a normal unique repo shows just its project name (NOT "aitasks (repo)").
- [ ] [stats] ←/→ and `[`/`]` reach each colliding repo and the "All projects (aggregate)" entry unambiguously.
- [ ] [switcher] With two colliding "aitasks" repos, the Session: row renders them as `aitasks (repoA)` / `aitasks (repoB)`; a uniquely-named session still shows its bare name.
- [ ] [switcher] Selecting/acting on each colliding row (launch, git, desync) targets that row's OWN project_root.
- [ ] [switcher] Opening the switcher from inside repoB selects repoB (cwd context), not the first colliding entry.
