---
priority: medium
effort: medium
depends: [1099]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [1099]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-01 11:51
updated_at: 2026-07-01 12:22
completed_at: 2026-07-01 12:22
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1099

## Verification Checklist

- [x] [stats] Register 2+ repos with NO tmux.default_session (both -> "aitasks"); open `ait stats` — PASS 2026-07-01 12:21 isolated registry: repoA and repoB both defaulted to session aitasks; stats labels repoA/repoB had distinct totals 1 vs 2 and cache keys were separate project_root keys
- [x] [stats] Labels are project-oriented — PASS 2026-07-01 12:21 stats TUI capture showed project-oriented labels repoB and repoA plus All projects aggregate; no label rendered as aitasks (repo)
- [x] [stats] ←/→ and `[`/`]` reach each colliding repo and the "All projects (aggregate)" entry unambiguously. — PASS 2026-07-01 12:21 stats TUI Right navigation reached repoA then All projects aggregate with totals 1 and 3; grouped helper check repointed bracket navigation between colliding repo keys
- [x] [switcher] With two colliding "aitasks" repos, the Session: row renders them as `aitasks (repoA)` / `aitasks (repoB)`; a uniquely-named session still shows its bare name. — PASS 2026-07-01 12:21 switcher capture showed Session row with distinct colliding labels aitasks (repoB) and aitasks (repoA); regression also covers unique sessions rendering bare
- [x] [switcher] Selecting/acting on each colliding row (launch, git, desync) targets that row's OWN project_root. — PASS 2026-07-01 12:21 switcher routing harness cycled both rows and resolved selected_project_root to repoB then repoA; git/desync/launch code paths derive targets from that selected root
- [x] [switcher] Opening the switcher from inside repoB selects repoB (cwd context), not the first colliding entry. — PASS 2026-07-01 12:21 launched from repoB cwd; resolve_selected_key and TuiSwitcherOverlay initial selection both selected repoB project_root, not the first colliding entry
