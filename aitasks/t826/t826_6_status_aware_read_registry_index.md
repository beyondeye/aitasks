---
priority: medium
effort: low
depends: [t826_5]
issue_type: refactor
status: Implementing
labels: [cross_repo, aitask_projects, registry]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 12:02
updated_at: 2026-05-26 12:09
---

## Context

Spun off from t826_5 brainstorm (`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`).

Today `_read_registry_index` in `.aitask-scripts/lib/agent_launch_utils.py`
silently skips STALE registry entries (path missing the
`aitasks/metadata/project_config.yaml` marker). This prevents downstream
callers (`discover_aitasks_sessions` → TUI switcher) from surfacing
STALE entries to the user.

This task changes the helper's return shape and surfaces STALE entries
downstream. No new user-facing verbs land here — this is the
plumbing that unblocks child tasks B (remove/update), C (prune),
D (doctor), and E (switcher rendering).

## Key Files to Modify

- `.aitask-scripts/lib/agent_launch_utils.py` — `_read_registry_index`
  return-type change (~lines 262-330); `AitasksSession` dataclass
  (~lines 84-95) — add `is_stale: bool = False`;
  `discover_aitasks_sessions` (~lines 380-450) — synthesize STALE rows
  with `is_live=False, is_stale=True`.
- `.aitask-scripts/aitask_projects.sh` — extract
  `classify_registry_entry(name, path)` helper from `cmd_list` inline
  logic (lines 232-238). Returns `LIVE` / `OK` / `STALE`.

## Reference Files for Patterns

- `aitask_projects.sh::list_registry_entries` (lines ~124-174) —
  YAML line-parser pattern.
- `aitask_projects.sh::cmd_list` (lines 220-249) — current inline
  classification logic.
- `tests/test_discover_include_registered.py` — the t826_2 test
  pattern for fake registries via `AITASKS_PROJECTS_INDEX`.

## Implementation Plan

1. Add `is_stale: bool = False` to `AitasksSession`. Default preserves
   every existing constructor.
2. Change `_read_registry_index()` return type from
   `list[tuple[str, Path]]` to `list[tuple[str, Path, str]]` where
   the third element is `"OK"` or `"STALE"`. Stop skipping STALE
   entries — emit them with `status="STALE"`.
3. Update `discover_aitasks_sessions` consumer of
   `_read_registry_index`: when `status=="STALE"`, synthesize an
   `AitasksSession(is_live=False, is_stale=True)`; when
   `status=="OK"`, synthesize as today (`is_live=False, is_stale=False`).
4. Extract `classify_registry_entry` function in `aitask_projects.sh`
   that takes `(name, path)` and prints one of `LIVE` / `OK` / `STALE`.
   Replace inline logic in `cmd_list` to call the helper. (Children
   B–D will reuse this same helper for their own classification.)
5. The `live_names` set still uses tmux discovery; STALE entries
   never match (no live session), so the live-vs-registry dedup
   continues working.

## Verification Steps

- `bash tests/test_discover_include_registered.py` — extend with
  cases: tuple shape is 3-element, STALE entry reaches consumer,
  `is_stale=True` on synthesized entry. All existing assertions
  still pass.
- `bash tests/test_discover_default_unchanged.py` — must still pass
  (the no-flag path is untouched).
- `shellcheck .aitask-scripts/aitask_projects.sh` — clean.
- `ait projects list` output unchanged (`classify_registry_entry`
  is a pure refactor of the inline code).

## Out of Scope

- User-facing surfacing of STALE entries — that's child E (switcher).
- New `ait projects` verbs — children B/C/D.
- Caching the marker-file probe — decided against in the brainstorm.
