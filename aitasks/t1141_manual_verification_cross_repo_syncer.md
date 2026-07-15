---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [tui, git-integration, project_groups, manual_verification]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1138
created_at: 2026-07-09 10:33
updated_at: 2026-07-15 18:56
---

## Origin

Risk-mitigation ("after") follow-up for t1138, created at Step 8d after implementation landed.

## Risk addressed

Code-health risk (single-repo regression, live multi-repo TUI behavior, refresh scheduling):
- Syncer row-key model rework (composite keys, per-repo snapshots) could regress single-repo behavior or `check_action` gating.
- Concurrent refresh sources (interval tick, manual `r`, post-action) could interleave: a superseded local-only snapshot overwriting a newer fetched one, or accumulated background git passes.

## Goal

Drive the live syncer TUI in a multi-repo environment and verify the cross-repo behavior end-to-end.

## Verification Checklist

- [ ] Launch `ait syncer` in a repo with ≥2 registered projects: table shows one row per repo × ref (`main`, `aitask-data`) with a Project column; the launch repo is listed first.
- [ ] Least-recently-fetched scheduling: over successive automatic ticks (default 60s), exactly one repo's Fetched age resets per tick — always the least-recently-fetched one; a repo whose fetch fails (e.g. no network/remote) does NOT get re-picked every tick (rotation advances; its Fetched age keeps growing).
- [ ] Fetched age column ticks up smoothly between refreshes (5s display updates); `—` shows for never-fetched repos.
- [ ] Manual `r` immediately refreshes the highlighted row's repo and defers it in the automatic rotation.
- [ ] Per-row action gating: `s` footer hint/action only on `aitask-data` rows, `u`/`p` only on `main` rows — following the highlighted row across repos.
- [ ] Run `s` (sync) and `u` (pull) against a NON-current repo: notifications are prefixed with that project's label, and (best-effort corroboration) that repo's `.git/FETCH_HEAD` mtime advances on `u` while the launch repo's does not. The primary targeting guarantee is the unit spy tests in `tests/test_sync_action_runner.py`.
- [ ] Trigger a failure on a non-current repo (e.g. push with no permission) and confirm the failure modal names the project and the "Launch agent to resolve" flow roots the agent in THAT repo.
- [ ] Single-repo regression: with only one discovered repo (e.g. temporary empty registry + outside tmux), the table shows the legacy two rows, no Project column, last column is a wall-clock "Last refresh".
- [ ] `ait stats` still renders correct project labels after the `compact_root` promotion.

## Related

Original task: t1138 (archived). Plan: `aiplans/archived/p1138_add_cross_repo_support_to_syncer_tui.md` after archival.
