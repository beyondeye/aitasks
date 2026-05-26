---
priority: medium
effort: low
depends: [t826_7, t826_6, t826_7]
issue_type: feature
status: Implementing
labels: [cross_repo, aitask_projects]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 12:02
updated_at: 2026-05-26 13:38
---

## Context

Spun off from t826_5 brainstorm (`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`).

Bulk cleanup verb for STALE registry entries. Composes the
`classify_registry_entry` helper from t826_6 and the `cmd_remove`
verb from t826_7.

## Key Files to Modify

- `.aitask-scripts/aitask_projects.sh` — add `cmd_prune` function +
  dispatch case. Update `--help` text.

## Reference Files for Patterns

- `cmd_list` (lines 220-249) — iteration pattern over
  `list_registry_entries`.
- `cmd_remove` (added in t826_7) — reused per matched STALE entry.
- `classify_registry_entry` (added in t826_6) — STALE detection.

## Implementation Plan

1. **`cmd_prune [--dry-run] [--yes]`**:
   - Iterate `list_registry_entries`; for each row,
     `classify_registry_entry "$name" "$path"`. Skip non-STALE.
   - Collect STALE entries into a tally. Print a summary header:
     `Found <N> stale entries.` Exit 0 if N=0.
   - **`--dry-run`**: print each STALE entry (`<name> → <path>`),
     no writes. Exit 0.
   - **default behavior**: per-entry prompt
     `Prune '<name>' (path: <path>)? [y/N]:` — on `y`, call
     `cmd_remove "$name" --force`; on anything else, skip.
   - **`--yes`**: skip prompts; call `cmd_remove --force` for every
     STALE entry.
   - Final summary: `Pruned <K> of <N> stale entries.`
2. Add `prune` to the verb dispatcher and `--help` block.

## Verification Steps

- `tests/test_aitask_projects_prune.sh`:
  - Setup: temp registry with 3 entries — 1 OK (real dir w/ marker),
    2 STALE (paths that don't exist).
  - **no stale**: registry without STALE rows → `Found 0 stale
    entries.`, exit 0, registry unchanged.
  - **`--dry-run`**: prints stale list, registry unchanged.
  - **`--yes`**: both STALE removed, OK preserved.
  - **default (interactive)**: pipe `y\nn\n` on stdin → 1 of 2
    stale removed.
- `shellcheck .aitask-scripts/aitask_projects.sh` — clean.

## Out of Scope

- Interactive `doctor` (per-entry prune/update/clone choice) —
  child D (t826_9). Prune is the simpler "bulk delete only" form.
