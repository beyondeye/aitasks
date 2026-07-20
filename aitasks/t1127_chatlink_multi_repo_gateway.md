---
priority: low
effort: high
depends: []
issue_type: feature
status: Folded
labels: [chat_surface, python]
gates: [risk_evaluated]
folded_into: 1157
anchor: 1120
created_at: 2026-07-05 12:01
updated_at: 2026-07-17 11:50
boardidx: 180
---

## Context

Follow-up of t1120 (Discord bug-report channel integration). t1120 delivers a
**per-workspace** chatlink gateway (applink model: one daemon per ait
workspace) by explicit design decision; this follow-up extends it to the
Hermes model — a **single gateway daemon serving multiple repos/Discord
servers**. Deferred from t1120 to keep the first iteration simple and pattern-
consistent with applink.

## Goal

One chatlink daemon can watch bug-intake channels across multiple linked
repos/Discord servers and route each session to the right workspace:

- **Repo-routing config**: per-repo channel map (channel ref → workspace),
  resolved via the `ait projects` registry (`~/.config/aitasks/projects.yaml`)
  — reference sibling projects by logical name, never by sibling-directory
  path.
- **Cross-workspace process management**: sandbox spawns and task commits
  execute in the routed workspace; `reap_orphans(workspace_id)` (already
  workspace-keyed in `lib/sandbox_launch.py` by design) scoped per workspace.
- **Config layering**: decide where multi-repo config lives (per-user vs
  per-workspace) without breaking t1120's per-workspace
  `aitasks/metadata/chatlink_config.yaml`.
- Multiple bot tokens / one bot across guilds — decide and document.

## Preconditions

- All t1120 children landed (relay, config/policy, daemon, explore skill,
  docker backend, e2e glue). Read `aiplans/archived/p1120*` first.
- The launcher seam and session store are already keyed by
  workspace/session_id (t1120 contracts 1, 8) — this task builds on those
  keys rather than refactoring them.

## Acceptance criteria

- Two configured repos, two channels, one daemon: a bug report in each
  channel produces a task committed in the correct repo, with no cross-talk
  (session routing verified by tests against MockChatAdapter).
- Single-repo setups keep working unchanged (t1120 config remains valid).
