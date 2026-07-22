---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [ait_setup, installation, claudeskills]
anchor: 635
created_at: 2026-07-22 18:48
updated_at: 2026-07-22 18:48
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

## Verification Steps

- Take a project that was installed BEFORE this change and still carries the
  retired surfaces; run `ait upgrade`.
- `/aitask-pickn` no longer appears in the skill listing of any agent: Claude
  Code, Codex CLI, and OpenCode (check `/` completion in each, not just the
  filesystem).
- `/aitask-pick` still resolves and renders normally in all three agents.
- No `aitask-pickn` or `task-workflown` AUTHORING or wrapper directory remains
  under `.claude/skills/`, `.agents/skills/`, `.opencode/skills/`,
  `.opencode/commands/`, `aitasks/metadata/codex_skills/`, or
  `aitasks/metadata/opencode_skills/`.
- Any rendered `aitask-pickn-<profile>-` / `task-workflown-<profile>-` closure
  directories are reported as `KEPT` and are still present — upgrades must never
  delete a closure.
- The upgrade's git commit contains the deletions (`git show --stat` on the
  framework-update commit), so other checkouts see them.
- `ait settings` → project tab shows no `pickn` row under `default_profiles`,
  and saving the tab does not resurrect it.
- **Preservation case (the important one):** on a second copy of the project,
  hand-edit BOTH a retired wrapper (e.g. add a line to
  `.claude/skills/aitask-pickn/SKILL.md`) AND a rendered closure's `SKILL.md`
  before upgrading. After `ait upgrade`: both files survive **byte-identical**
  (`diff` against a pre-upgrade copy), the `KEPT` warning names them with an
  `rm -rf` cleanup command, and the upgrade still exits 0.
- **Live neighbour check:** `.claude/skills/aitask-pick/`,
  `.claude/skills/task-workflow/`, and any `aitask-pick-<profile>-` /
  `task-workflow-<profile>-` render directories are untouched.
- Finally, run `./.aitask-scripts/aitask_prune_retired_skills.sh --prune-rendered`
  explicitly: the retired closures are removed while the `aitask-pick-*-` /
  `task-workflow-*-` neighbours remain.
