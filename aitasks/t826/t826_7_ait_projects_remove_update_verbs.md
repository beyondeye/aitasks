---
priority: medium
effort: low
depends: [t826_6, t826_6]
issue_type: feature
status: Implementing
labels: [cross_repo, aitask_projects]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 12:02
updated_at: 2026-05-26 12:30
---

## Context

Spun off from t826_5 brainstorm (`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`).

Two atomic verbs for the `ait projects` registry: drop a single
entry, and repoint a single entry whose path moved. These are the
building blocks reused by child C (`prune`) and child D (`doctor`).

## Key Files to Modify

- `.aitask-scripts/aitask_projects.sh` — add `cmd_remove` and
  `cmd_update` functions plus their dispatch cases in the `case`
  statement (~lines 350-400).

## Reference Files for Patterns

- `aitask_projects.sh::cmd_add` (lines 253-291) — the canonical
  rebuild-via-awk pattern for registry mutation.
- `aitask_projects.sh::atomic_write` — used by every mutator.
- `aitask_projects.sh::list_registry_entries` — TSV-producing read
  helper.

## Implementation Plan

1. **`cmd_remove <name> [--force]`**:
   - Read registry via `list_registry_entries`.
   - Confirm-or-`--force`: if not `--force`, prompt
     `Remove '<name>' from registry? [y/N]:`. Abort on anything
     other than `y`/`Y`.
   - Rebuild registry with `awk -F'|' -v skip="$name" '$1 != skip'`,
     emit via `build_registry_yaml` + `atomic_write`.
   - Error if `<name>` was not in the registry (exit 1 with message).
   - Print `Removed <name>` on success.

2. **`cmd_update <name> <new_path>`**:
   - Validate `<new_path>` exists and holds
     `aitasks/metadata/project_config.yaml`. Die with clear message
     otherwise.
   - Resolve `<new_path>` to absolute via `cd "$new_path" && pwd`.
   - Read registry, find entry by name. Die if not found.
   - Rebuild: replace the matched row's path field; refresh
     `last_opened` to today's date (`date -u +"%Y-%m-%d"`); keep
     `git_remote` field unchanged.
   - Use `awk -F'|' -v name="$name" -v new_path="$new_path"
     -v today="$today" '$1 == name { print $1 "|" new_path "|" $3
     "|" today; next } { print }'`.
   - Print `Updated <name> → <new_path>` on success.

3. Add `remove|rm` and `update` cases to the verb dispatcher; update
   the `--help` text block at the top of the file.

## Verification Steps

- New `tests/test_aitask_projects_remove.sh`:
  - Setup: temp `AITASKS_PROJECTS_INDEX` with 2 entries.
  - `remove existing --force` → entry gone, other entry intact.
  - `remove missing` → exit 1 with message.
  - Interactive `n` answer → registry unchanged.
- New `tests/test_aitask_projects_update.sh`:
  - Setup: temp registry + a moved project root with marker.
  - Happy path: `update <name> <new_path>` → row repointed,
    `last_opened` refreshed.
  - Missing-marker path → exit 1, registry unchanged.
  - Missing entry → exit 1.
- `shellcheck .aitask-scripts/aitask_projects.sh` — clean.

## Out of Scope

- Bulk `prune` — child C (t826_8).
- Interactive `doctor` flow — child D (t826_9).
- STALE-vs-OK awareness — `remove` works on any entry; `update`
  validates the new path holds the marker.
