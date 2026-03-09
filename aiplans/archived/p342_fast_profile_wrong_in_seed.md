---
Task: t342_fast_profile_wrong_in_seed.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Sync Seeded Execution Profiles with Metadata (t342)

## Context

The task requested bringing the seeded execution profiles in `seed/profiles/`
back in line with the canonical profiles in `aitasks/metadata/profiles/`.
During inspection, `seed/profiles/fast.yaml` had drifted from the current
metadata copy, and `seed/profiles/remote.yaml` was missing entirely.

## Implementation Plan

1. Compare the current seeded profile files against the metadata profiles to
   determine the intended canonical contents.
2. Update `seed/profiles/fast.yaml` to match
   `aitasks/metadata/profiles/fast.yaml`.
3. Add `seed/profiles/remote.yaml` from
   `aitasks/metadata/profiles/remote.yaml`.
4. Verify the seeded files match the metadata profiles exactly using `diff`.

## Final Implementation Notes

- **Actual work done:** Synced `seed/profiles/fast.yaml` with the canonical
  `aitasks/metadata/profiles/fast.yaml` and added
  `seed/profiles/remote.yaml` to match
  `aitasks/metadata/profiles/remote.yaml`.
- **Deviations from plan:** No workflow code or documentation changes were made
  for this task. The implementation stayed limited to seed profile parity.
- **Issues encountered:** The previous seeded `fast.yaml` still contained the
  legacy `run_location` field and was missing
  `post_plan_action_for_child` and `explore_auto_continue`. Investigation also
  showed follow-up ambiguity around whether some `remote.yaml` keys are
  compatibility-only or meant to be actively consumed.
- **Key decisions:** Treated `aitasks/metadata/profiles/` as the source of
  truth for this task. Preserved the follow-up design question separately
  instead of expanding scope.
- **Follow-up created:** `t346_investigate_remote_profile_unused_keys` to
  investigate stale or compatibility-only references around
  `skip_task_confirmation` and `complexity_action` in the remote profile flow.
