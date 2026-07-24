---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task_attachments, ait_settings]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-24 14:42
updated_at: 2026-07-24 14:42
---

## Context

The `ait artifact` substrate (t1076_1–3) is fully functional. Its `local` backend already stores blobs git-tracked: they land in the data worktree (`attachments/blobs/<2>/<62>` inside `.aitask-data`) and are committed via `task_git` — i.e., on the **aitask-data branch** in branch mode (or the current branch in legacy mode). The branch target is implicit and not configurable.

The `aitask-trail` feature (t1210) stores implementation trails via `ait artifact`, making a well-defined default git backend more important.

## Goal

Make the git-branch storage target for the artifact/attachment blob store an explicit, configurable option:

1. **Configurable branch target** — either the aitask-data branch (current behavior, remains the default) or a **dedicated branch** with a configurable name (e.g. `aitask-artifacts`), keeping artifact blobs from bloating the task-data branch.
2. **Settings integration** — expose the configuration in a **new tab** in the settings TUI (`.aitask-scripts/settings/settings_app.py`; extend `TAB_SWITCH_ACTIONS` — currently 8 tabs — so shortcuts/footer hints follow automatically per existing pattern). Persist config in `aitasks/metadata/project_config.yaml` under the existing `artifacts.backends.*` scheme used by the `dir` backend (`lib/artifact_registry.sh`).
3. **Branch initialization decision** — decide (in planning, with trade-offs) whether a newly configured dedicated branch is:
   - **eagerly initialized** when the configuration is confirmed in settings (fail-fast, immediate feedback, but settings TUI performs a git mutation), or
   - **lazily initialized** on first artifact write (no side effects at config time, but first-use failure surface).
4. **Website docs** — the artifact feature currently has **no website documentation at all** (no page under `website/content/docs/commands/` or `docs/concepts/` mentions `ait artifact` or `ait attach`; only blog posts do). As part of this task:
   - add baseline user-facing docs for the artifact feature (concept + `ait artifact` command verbs),
   - document the backend options including the new configurable git-branch backend and its settings tab.

## Key touchpoints (from exploration)

- `.aitask-scripts/lib/artifact_backends/local.sh` — current data-worktree-backed backend (blob root via `_ait_detect_data_worktree`).
- `.aitask-scripts/lib/artifact_backends/dir.sh` — reference for a config-registered backend (fail-closed root checks).
- `.aitask-scripts/lib/artifact_registry.sh` — backend selection/activation from `project_config.yaml`; `# BACKEND-EXTENSION-POINT` dispatcher arm.
- `.aitask-scripts/aitask_artifact.sh` — path-scoped `task_git add/commit` transaction under the attach lock; a dedicated branch needs its own worktree + commit path analog.
- `.aitask-scripts/lib/task_utils.sh` — `_ait_detect_data_worktree` / `task_git` semantics to generalize or parallel.
- `.aitask-scripts/settings/settings_app.py` — tab registry (`TAB_SWITCH_ACTIONS`), per-tab pane pattern.

## Design considerations

- A dedicated branch likely needs an orphan-branch bootstrap and a hidden worktree (analogous to `.aitask-data`), plus sync/push semantics — coordinate with the syncer and the `ait git` flow; beware the known divergence pitfalls of the data branch.
- Switching branch config when blobs already exist on the old target: decide between migration (reuse `ait artifact move` machinery) and fail-closed rejection.
- Keep the hash-first invariant: backend/branch swap must never rewrite task files.
- Legacy mode (no data branch) behavior must stay defined for both options.

## Verification

- Round-trip put/get/versions on a dedicated-branch config; blobs and manifests commit to the configured branch only.
- Default config unchanged → byte-identical behavior to today (blobs on aitask-data branch).
- Settings tab edit persists to `project_config.yaml` and survives reload; eager-init path (if chosen) creates the branch exactly once and is idempotent.
