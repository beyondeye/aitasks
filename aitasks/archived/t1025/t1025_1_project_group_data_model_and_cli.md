---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: []
issue_type: feature
status: Done
labels: [tui_switcher, tmux]
risk_mitigation_tasks: [1029]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-18 00:01
updated_at: 2026-06-18 15:16
completed_at: 2026-06-18 15:16
---

## Context

First child of t1025. Introduces the `project-group` concept at the data layer
only (no TUI changes). Establishes the slug naming contract, the registry
per-entry field, discovery-time group resolution, the bootstrap-from-config
rule, the `ait projects group` CLI, and the pure `group_sessions` derivation
function that child 2 (TUI) and child 3 (settings editor) consume.

`project-group` = the agreed umbrella term grouping connected repos. The
per-user registry `~/.config/aitasks/projects.yaml` is the operational source of
truth; each repo's `project_config.yaml` `project.project_group` is the bootstrap
seed. See the parent plan `aiplans/p1025_*.md` for full rationale and decisions.

## Key Files to Modify

- `seed/project_config.yaml` — add optional commented `project.project_group`.
- `.aitask-scripts/lib/agent_launch_utils.py`:
  - `_parse_registry_records()` (~:294-367): 4-field → 5-field tuple
    `(name, path, git_remote, last_opened, project_group)`.
  - `AitasksSession` dataclass (~:96-119): add resolved `project_group: str|None`.
  - `discover_aitasks_sessions()` (~:435-509): resolve each session's group
    (registry → repo `project_config.yaml` → None) for BOTH live and registered
    sessions. Add a cached config reader near `_read_default_session()` (~:392).
  - Add pure `group_sessions(sessions, selected_group) -> ordered_ring` + group
    list. Add shared slug validator `^[a-z0-9][a-z0-9_-]*$`.
- `.aitask-scripts/aitask_projects.sh`:
  - `build_registry_yaml` (~:179-194): add 5th `|`-field; emit `project_group:`.
  - `cmd_add` (~:267-306): bootstrap group from repo config.
  - dispatch table (~:641-685): add `group` verb → `group list|set|unset|sync`.
- `.aitask-scripts/aitask_project_resolve.sh` `index_lookup_path` (~:150-195):
  mirror the new field byte-for-byte (parity).
- `tests/test_registry_reader_parity.sh`, `tests/test_projects_cmd.sh`: extend.

## Reference Files for Patterns

- Registry reader authority + parity contract: `_parse_registry_records`
  docstring (agent_launch_utils.py:294-311) and `list_registry_entries`
  (aitask_projects.sh:166-172).
- Existing `project.name` read on `add` for the bootstrap pattern.

## Implementation Plan

1. **Slug validator** (shared, used by every write path): accept `a-z0-9_-`
   (must start alnum); reject or normalize `: # | space quote uppercase leading
   space` with a clear message. Pipe-rejection makes the `IFS='|'` writer safe.
2. **Reader 4→5 field** across Python + bash awk + `--list-registry` output +
   `build_registry_yaml` pipe record; update parity golden. Land parity in THIS
   child (testability-first).
3. **Discovery-time group resolution** on every `AitasksSession` (priority:
   registry value → repo `project_config.yaml` `project.project_group` → None).
4. **Bootstrap** on `ait projects add` + a `group sync` backfill verb; registry
   value wins once written.
5. **`ait projects group` CLI** (`list/set/unset/sync`) via the Python writer.
6. **Pure `group_sessions`**: ring = `[group members] + [out-of-group where
   is_live]`; stale in-group kept (flagged), stale out-of-group dropped from ring
   but listed for `group list`; ungrouped repos under synthetic "(ungrouped)".

## Verification

- `bash tests/test_registry_reader_parity.sh` (parity holds with new field).
- `bash tests/test_projects_cmd.sh` (group set/unset/list/sync).
- New unit tests: slug validator (accept/reject/normalize cases); discovery group
  resolution for live-registered, live-unregistered (group from own config),
  ungrouped; `group_sessions` ring incl. live-out-of-group, stale-in-group kept,
  stale-out-of-group dropped, no-groups flat fallback; bootstrap-from-config vs
  registry-wins.
- `shellcheck .aitask-scripts/aitask_projects.sh .aitask-scripts/aitask_project_resolve.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-18T09:50:35Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-18T09:50:37Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-18T12:14:00Z status=pass attempt=1 type=human
