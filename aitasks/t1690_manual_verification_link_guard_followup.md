---
priority: medium
effort: medium
depends: [1682]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1682]
anchor: 1595
followup_kind: manual_verification
created_at: 2026-09-02 16:16
updated_at: 2026-09-02 16:16
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1682

## Verification Checklist

- [ ] On the next release, confirm the `Check internal links` step appears in the Actions log for the "Deploy Hugo site to Pages" run, executes after `Build with Hugo` and before `Upload artifact`, and passes. `act` is not installed on the dev box, so t1682 verified only the step's exact command (run locally under two base URLs) and its YAML structure (PyYAML parse of name / working-directory / run / position) — the workflow itself has never been executed.
- [ ] Confirm the base URL GitHub Pages actually supplies via `steps.pages.outputs.base_url` resolves to the CNAME custom domain, so the checker derives `base_path: /` in CI and reports `base-agnostic: 0` there. If it instead resolves to a project path (`https://beyondeye.github.io/aitasks/`), expect `base-agnostic: 8` — still a pass, but confirm those 8 are the known site-root links in `content/_index.md` and `docs/workflows/releases.md` and nothing new.
- [ ] Confirm the deploy still completes end-to-end with the new step in the job — it did not introduce a failure, and its runtime is negligible next to the Hugo build (~1s locally over 216 pages).
- [ ] On the published site, click through two repaired links: `/docs/tuis/settings/how-to/` -> the Board TUI link (must land on `/docs/tuis/board/`), and `/docs/installation/windows-wsl/` -> the "Authentication with Your Git Remote" link (must land on `/docs/installation/git-remotes/` and scroll to that heading).
