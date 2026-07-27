---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: [ait_setup, installation, claudeskills]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-22 18:48
updated_at: 2026-07-27 19:12
completed_at: 2026-07-27 19:12
---

## Origin

Risk-mitigation ("after") follow-up for t635_36, created at Step 8d after
implementation landed.

## Risk addressed

Addresses three code-health risks from `aiplans/archived/p635/p635_36_*.md`:

- **Upgrade path leaves zombie wrappers** — "A missed install location (one of
  eight, across three agent roots plus two staging dirs) leaves a discoverable
  `/aitask-pickn` in upgraded projects · severity: medium".
- **The prune helper deletes a live skill** — "`aitask-pickn` / `task-workflown`
  sit one character from `aitask-pick` / `task-workflow`; a prefix glob in the
  retired-paths table or the rendered-dir expansion destroys a working
  installation on upgrade · severity: high".
- **The prune helper deletes the user's own work** — "An exact retired path is
  not proof of framework ownership ... Silent deletion on upgrade is
  unrecoverable for untracked files · severity: high".

In-task coverage is a temp-dir fixture (`tests/test_prune_retired_skills.sh`,
62 asserts, incl. both negative controls). What it cannot cover is the **real
upgrade path** — `ait upgrade` → `install.sh --force` → tarball extract →
`prune_retired_skills` → the framework commit — and the agents' **live skill
discovery**, which is what a user actually sees.

## Goal

Verify on a real, already-installed project (not this framework repo) that the
retirement landed cleanly and destroyed nothing.

## Verification Checklist

- [x] Take a project that was installed BEFORE this change and still carries the — PASS 2026-07-27 19:11 auto: copy of real aitasks_go (framework 0.27.0, 8 retired surfaces present); ait upgrade -> v0.29.0 exit 0
  retired surfaces; run `ait upgrade`.
- [x] `/aitask-pickn` no longer appears in the skill listing of any agent: Claude — PASS 2026-07-27 19:11 auto: Claude Code / completion shows no /aitask-pickn; OpenCode 'No matching items'; Codex has no aitask slash surface and .agents/skills/aitask-pickn is gone
  Code, Codex CLI, and OpenCode (check `/` completion in each, not just the
  filesystem).
- [x] `/aitask-pick` still resolves and renders normally in all three agents. — PASS 2026-07-27 19:11 auto: /aitask-pick listed in Claude Code + OpenCode completion, present in .agents/skills for Codex; skill_render exit 0 for all 3 agents; retired stem fails 'template not found' (negative control)
- [x] No `aitask-pickn` or `task-workflown` AUTHORING or wrapper directory remains — PASS 2026-07-27 19:11 auto: 0 authoring/wrapper dirs left across all 6 roots; 8 retired paths PRUNED
  under `.claude/skills/`, `.agents/skills/`, `.opencode/skills/`,
  `.opencode/commands/`, `aitasks/metadata/codex_skills/`, or
  `aitasks/metadata/opencode_skills/`.
- [x] Any rendered `aitask-pickn-<profile>-` / `task-workflown-<profile>-` closure — PASS 2026-07-27 19:11 auto: 3 rendered closures reported KEPT:rendered-closure-not-verifiable and all still present after upgrade
  directories are reported as `KEPT` and are still present — upgrades must never
  delete a closure.
- [x] The upgrade's git commit contains the deletions (`git show --stat` on the — PASS 2026-07-27 19:11 auto: main commit deletes 31-33 pickn/workflown paths, aitask-data commit deletes staging; 0 pickn paths tracked on either branch
  framework-update commit), so other checkouts see them.
- [x] `ait settings` → project tab shows no `pickn` row under `default_profiles`, — PASS 2026-07-27 19:11 auto: project tab renders 9 default_profiles rows, no pickn; real save_project_settings() left map unchanged, no pickn in saved YAML; pickn absent from VALID_PROFILE_SKILLS
  and saving the tab does not resurrect it.
- [x] **Preservation case (the important one):** on a second copy of the project, — PASS 2026-07-27 19:11 auto: hand-edited retired wrapper + rendered closure both survive byte-identical (diff), KEPT warning names both with rm -rf, upgrade exit 0 (7 pruned not 8)
  hand-edit BOTH a retired wrapper (e.g. add a line to
  `.claude/skills/aitask-pickn/SKILL.md`) AND a rendered closure's `SKILL.md`
  before upgrading. After `ait upgrade`: both files survive **byte-identical**
  (`diff` against a pre-upgrade copy), the `KEPT` warning names them with an
  `rm -rf` cleanup command, and the upgrade still exits 0.
- [x] **Live neighbour check:** `.claude/skills/aitask-pick/`, — PASS 2026-07-27 19:11 auto: aitask-pick/ and task-workflow/ intact, no neighbour in PRUNED list; generated render dirs byte-identical; task-workflow-remote- only gained shipped gate-cli.md
  `.claude/skills/task-workflow/`, and any `aitask-pick-<profile>-` /
  `task-workflow-<profile>-` render directories are untouched.
- [x] Finally, run `./.aitask-scripts/aitask_prune_retired_skills.sh --prune-rendered` — PASS 2026-07-27 19:11 auto: --prune-rendered removed exactly the 3 retired closures; all 7 aitask-pick-*- / task-workflow-*- neighbours survive
  explicitly: the retired closures are removed while the `aitask-pick-*-` /
  `task-workflow-*-` neighbours remain.
