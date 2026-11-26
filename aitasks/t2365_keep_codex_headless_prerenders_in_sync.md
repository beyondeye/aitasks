---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [skills, codex, setup]
created_at: 2026-11-26 09:34
updated_at: 2026-11-26 09:34
---

## Problem

Framework upgrades can leave tracked Codex headless skill files modified in a consumer's otherwise clean checkout. During thinking_app t327, the merge broker returned `DIRTY_TREE:2` for `.agents/skills/aitask-pickrem-remote-codex-/SKILL.md` and `.agents/skills/aitask-pickweb-remote-codex-/SKILL.md`. Each file had gained the generated Codex tool-mapping instruction. The same checkout also had an untracked `materialize-active.md` and the rendered `.agents/skills/task-workflow-remote-codex-/` directory. The framework source repo already tracks those dependencies. Check how the release and installer deliver them to existing consumers.

## Scope

- Trace the headless Codex `remote` output from its templates through release packaging, install or upgrade, and `ait setup`. `install.sh` calls `refresh_codex_rendered_entries` after `commit_installed_files`, with a comment that rendered directories are ignored. The generated-directory ignore rules explicitly make exceptions for these remote paths. Check the analogous setup path.
- Deliver both remote entry points and their generated dependencies together. Keep the current headless startup contract so a clean consumer checkout can load both remote skills and their referenced files without a local renderer or a prior `ait setup`.
- Make install, upgrade, and setup converge on the same committed output for a stock project. Reuse the installer's pre-existing dirty-path protections so a consumer's edits are preserved. Keep on-demand variants ignored.

## Verification

- Reproduce with a clean consumer fixture from before the Codex tool-mapping refresh, including stale tracked entry points and missing generated dependencies. Upgrade it and run setup. Verify the full required remote Codex skill set is present and that the operations leave no generated-wrapper changes outside the framework update commit. Repeat them to check idempotence.
- Check both remote Codex entry points in a fresh checkout of the upgraded consumer without the renderer. Verify every generated dependency is present. Use the existing prerender freshness check on a clean release input to catch stale or missing output before publication.
- Exercise an upgrade with a pre-existing local edit and confirm the installer preserves it.

Related work includes t2297 (tool-mapping refresh), t1154 (a separate OpenCode prerender drift), and t1484 (test golden freshness).
