---
priority: medium
effort: medium
depends: [t826_8, t826_6, t826_7, t826_8]
issue_type: feature
status: Ready
labels: [cross_repo, aitask_projects]
created_at: 2026-05-26 12:03
updated_at: 2026-05-26 12:03
---

## Context

Spun off from t826_5 brainstorm (`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`).

Interactive scan-and-repair verb. Iterates STALE registry entries
and offers a per-entry choice: prune / update / clone / keep / skip-all.
The clone branch is opt-in via `--clone` flag (decision #3 of the
brainstorm).

## Key Files to Modify

- `.aitask-scripts/aitask_projects.sh` — add `cmd_doctor` function +
  dispatch case. Update `--help` text.

## Reference Files for Patterns

- `cmd_remove` (added in t826_7) — reused for prune branch.
- `cmd_update` (added in t826_7) — reused for update branch.
- `classify_registry_entry` (added in t826_6) — STALE detection.
- `cmd_list` (lines 220-249) — registry iteration pattern.

## Implementation Plan

1. **`cmd_doctor [--clone]`**:
   - Iterate registry; collect STALE entries with their metadata
     (name, path, git_remote, last_opened).
   - Print summary header `Found <N> stale entries.` Exit 0 if N=0.
   - For each STALE entry (with index `i/N`):
     ```
     [<i>/<N>] STALE: <name> → <path>
              last opened: <last_opened>
              git_remote: <remote>     (omit line if empty)

              Action? [p]rune / [u]pdate / <c>lone> / [k]eep / [s]kip-all
     ```
     The `c` option is **only listed AND parsed when `--clone` is
     set AND `git_remote` is non-empty**. Otherwise omitted.
   - Branch:
     - **`p`** — `cmd_remove "$name" --force`. Print `Pruned <name>.`
     - **`u`** — read new path from stdin (`New path: ` prompt);
       validate via `cmd_update <name> <new_path>` (which itself
       validates marker presence and errors out cleanly on
       mismatch — re-prompt or move on per error).
     - **`c`** — confirm `Clone <remote> into <path>? [y/N]:`. On
       `y`, `git clone "$remote" "$path"`. After clone, check if
       `<path>/aitasks/metadata/project_config.yaml` exists: if
       yes, print `Cloned and now OK.` (next `cmd_list` will
       reflect it). If no, print `Warning: cloned but no
       aitasks/metadata/project_config.yaml — entry remains STALE.`
       Leave registry untouched (the marker check next time will
       flip status automatically).
     - **`k`** — no-op for this entry.
     - **`s`** — break the loop.
2. Add `doctor` to the verb dispatcher and `--help` block.

## Verification Steps

- `tests/test_aitask_projects_doctor.sh`:
  - Setup: temp registry with one STALE entry (with git_remote)
    and one OK entry.
  - **prune branch**: stdin `p\n` → STALE removed; OK preserved.
  - **keep branch**: stdin `k\n` → registry unchanged.
  - **skip-all**: with 2 STALE entries, stdin `s\n` → both still
    present.
  - **`--clone` disabled**: prompt does NOT list `c` even when
    `git_remote` is set. Stdin containing `c` is rejected.
  - **`--clone` enabled but no git_remote**: still no `c` listed.
  - **`--clone` happy path**: mock `git clone` via PATH override
    or use a `file://` local-repo source as the remote. Verify
    target dir created and marker file present → `Cloned and now
    OK.`
  - **update branch**: stdin `u\n/new/path/with/marker\n` →
    registry repointed.
- `shellcheck .aitask-scripts/aitask_projects.sh` — clean.

## Out of Scope

- Top-level `ait projects clone <name>` — gated through doctor
  (brainstorm decision #3).
- Auto-prune by `last_opened` age — display only, no action.
- Race-condition handling in the TUI switcher — child E (t826_10).
