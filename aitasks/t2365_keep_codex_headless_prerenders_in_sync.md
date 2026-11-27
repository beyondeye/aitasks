---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [skills, codex, setup]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2382]
folded_tasks: [1154]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-11-26 09:34
updated_at: 2026-11-27 10:54
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

## Merged from t1154: rerender stale opencode remote prerenders


## Origin

Spawned from t1150 during Step 8b review.

## Upstream defect

- `.opencode/skills/task-workflow-remote-/cross-repo-child-assignment.md` — committed prerender is stale relative to its `.claude/skills/task-workflow/` source (t1117 edited `cross-repo-child-assignment.md` without rerendering); `aitask_skill_verify.sh` fails with 2 PRERENDER_FAIL (aitask-pickrem / aitask-pickweb, agent=opencode, profile=remote).

## Diagnostic context

While verifying t1150's aitask-explore `.md.j2` edit, `./.aitask-scripts/aitask_skill_verify.sh` reported:

```
PRERENDER_FAIL: aitask-pickrem agent=opencode profile=remote committed prerender stale or unrenderable (run aitask_skill_rerender.sh remote and commit):
committed prerender drift:
  .opencode/skills/task-workflow-remote-/cross-repo-child-assignment.md (stale)
PRERENDER_FAIL: aitask-pickweb agent=opencode profile=remote ... (same file)
```

Confirmed pre-existing: with t1150's edits stashed, the same 2 failures occur. `git log` shows the source was last touched by commit 49ee5e30f "bug: Support cross-repo child creation (t1117)", which did not regenerate the committed OpenCode remote prerender.

## Suggested fix

Run `./.aitask-scripts/aitask_skill_rerender.sh remote`, review the drift diff, and commit the regenerated `.opencode/skills/task-workflow-remote-/cross-repo-child-assignment.md`. Re-run `aitask_skill_verify.sh` to confirm green.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1154** (`t1154_rerender_stale_opencode_remote_prerenders.md`)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-27T06:24:57Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-27T08:49:49Z status=pass attempt=1 type=human
