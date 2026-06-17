---
Task: t1025_1_project_group_data_model_and_cli.md
Parent Task: aitasks/t1025_design_project_group_grouping_and_tui_navigation.md
Sibling Tasks: aitasks/t1025/t1025_2_*.md, aitasks/t1025/t1025_3_*.md, aitasks/t1025/t1025_4_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: project-group data model, bootstrap, read/write API + `ait projects group` CLI (t1025_1)

See parent plan `aiplans/p1025_design_project_group_grouping_and_tui_navigation.md`
for full context, decisions, and the resolved review concerns. This child is the
data layer only — no TUI changes.

## Steps

1. **Shared slug validator** — `^[a-z0-9][a-z0-9_-]*$`. Used by every write path
   (CLI `group set`, settings editor in t1025_3, bootstrap reader). Reject with a
   clear message, or normalize (lowercase, spaces→`-`, strip illegal) and confirm.
   Rejecting `|` makes the `IFS='|'` writer record structurally safe; rejecting
   `:`/`#`/quotes/leading-space keeps the custom line parser correct.
2. **Registry reader 4→5 field** — `_parse_registry_records()`
   (`agent_launch_utils.py:294-367`) returns `(name, path, git_remote,
   last_opened, project_group)`. Update `_read_registry_index()`,
   `build_registry_yaml` (`aitask_projects.sh:179-194`, add a 5th `|`-field and
   emit `project_group:`), the `--list-registry` output, and the bash awk reader
   `index_lookup_path` (`aitask_project_resolve.sh:150-195`). Update the parity
   golden in `tests/test_registry_reader_parity.sh`. **Land parity in this child.**
3. **`AitasksSession.project_group`** — add `project_group: str | None` to the
   dataclass (`agent_launch_utils.py:96-119`).
4. **Discovery-time group resolution** — in `discover_aitasks_sessions()`
   (`:435-509`) populate `project_group` for EVERY session (live + registered):
   (1) registry value for the `project_name`, else (2) read the repo's own
   `aitasks/metadata/project_config.yaml` `project.project_group`, else (3) None.
   Add a cached config reader beside `_read_default_session()` (`:392-432`).
5. **Bootstrap (init-if-missing)** — `cmd_add` (`aitask_projects.sh:267-306`)
   reads `project.project_group` from the repo config when registering; add a
   `group sync` verb to backfill already-registered entries. Registry value wins
   once written.
6. **`ait projects group` CLI** — dispatch (`:641-685`): `group list` (groups →
   members, including stale rows so they can be reassigned), `group set <name>
   <group>`, `group unset <name>`, `group sync`. Mutations go through the existing
   Python-authority writer.
7. **Pure `group_sessions(sessions, selected_group)`** — ring = `[members of
   selected_group] + [out-of-group where is_live]`. Stale in-group kept (flagged);
   stale out-of-group dropped from ring but still listed by `group list`.
   Ungrouped repos under a synthetic cyclable "(ungrouped)" group. Also returns
   the ordered group list for `[`/`]`. Lives in the model layer for t1025_2/3.

## Notes for sibling tasks

- t1025_2 imports `group_sessions` + the resolved `AitasksSession.project_group`;
  do not re-derive grouping in the TUI.
- t1025_3 reuses the slug validator + registry writer; no direct YAML writes.

## Verification

- `bash tests/test_registry_reader_parity.sh` — parity holds with the new field.
- `bash tests/test_projects_cmd.sh` — `group list/set/unset/sync`.
- Slug validator: accepts `a-z0-9_-`; rejects/normalizes `:`, `#`, `|`, space,
  quote, uppercase, leading space.
- Discovery group resolution: live-registered repo, live-UNregistered repo (group
  from its own config), ungrouped repo.
- `group_sessions` ring: live-but-out-of-group included; stale-in-group kept;
  stale-out-of-group dropped; no-groups flat fallback.
- Bootstrap-from-config when registry field absent; registry-wins when present.
- `shellcheck .aitask-scripts/aitask_projects.sh .aitask-scripts/aitask_project_resolve.sh`.

## Step 9
Standard child archival (see parent plan / task-workflow Step 9).
