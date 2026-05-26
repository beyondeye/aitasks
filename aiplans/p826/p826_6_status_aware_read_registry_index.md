---
Task: t826_6_status_aware_read_registry_index.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_10_switcher_stale_inline_render_and_race.md, aitasks/t826/t826_3_website_docs_multi_project_workflow.md, aitasks/t826/t826_4_manual_verification_brainstorm_cross_repo_project_references.md, aitasks/t826/t826_7_ait_projects_remove_update_verbs.md, aitasks/t826/t826_8_ait_projects_prune_verb.md, aitasks/t826/t826_9_ait_projects_doctor_verb.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md, aiplans/archived/p826/p826_2_tui_switcher_show_inactive_projects.md, aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md
Base branch: main
plan_verified: []
---

# t826_6 — Status-aware `_read_registry_index`

## Context

The brainstorm in `aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`
decided that STALE registry entries (rows whose path no longer holds
`aitasks/metadata/project_config.yaml`) must be surfaced to the user
through the TUI switcher and new `ait projects` verbs (remove/update/
prune/doctor). This task lays the plumbing: it stops silently dropping
STALE rows in `_read_registry_index()` and adds a status tag so
downstream consumers can decide what to do. The bash inline classifier
in `cmd_list` is also extracted into a reusable helper that the
follow-up verb children (B/C/D under t826) will reuse.

No user-facing surfacing or new verbs land here.

## Files to Modify

- `.aitask-scripts/lib/agent_launch_utils.py`
  - `AitasksSession` dataclass — add `is_stale: bool = False`.
  - `_read_registry_index()` — change return type from
    `list[tuple[str, Path]]` to `list[tuple[str, Path, str]]`, stop
    skipping STALE entries, emit each with `"OK"` or `"STALE"`.
  - `discover_aitasks_sessions()` — unpack the new 3-tuple; build
    `AitasksSession(is_live=False, is_stale=(status=="STALE"))`.
- `.aitask-scripts/aitask_projects.sh`
  - Add `classify_registry_entry <name> <path> [<live_names>]`
    function. Returns `LIVE` / `OK` / `STALE`.
  - Refactor `cmd_list` inline classification (lines 232-238) to call
    the helper.
- `tests/test_discover_include_registered.py` — extend with three new
  assertions:
  1. `_read_registry_index` returns 3-tuples (direct unit test).
  2. STALE registry rows reach `discover_aitasks_sessions(include_registered=True)`
     consumers as `is_stale=True`, `is_live=False` entries.
  3. `is_stale` defaults to `False` for OK (non-stale) registry-only entries.

## Implementation Details

### 1. `AitasksSession` dataclass

Add a new field after `is_live`:

```python
is_stale: bool = False  # True when synthesized from a STALE registry row
```

Keep the dataclass `frozen=True`. Default `False` preserves every
existing constructor call (no callers pass `is_stale` today).

Update the docstring's "When ``include_registered=True``..." paragraph
to mention that STALE entries now produce `is_stale=True` rows
alongside the existing `is_live=False` rows.

### 2. `_read_registry_index()` return shape

Change signature:

```python
def _read_registry_index() -> list[tuple[str, Path, str]]:
```

Inside `_flush()`, do not gate the append on the marker-file check.
Instead, compute the status and append unconditionally when both
`cur_name` and `cur_path` are present:

```python
def _flush() -> None:
    nonlocal cur_name, cur_path
    if cur_name and cur_path:
        p = Path(cur_path)
        if (p / "aitasks" / "metadata" / "project_config.yaml").is_file():
            entries.append((cur_name, p, "OK"))
        else:
            entries.append((cur_name, p, "STALE"))
    cur_name = ""
    cur_path = ""
```

Rewrite the docstring's "Skips entries whose path…" sentence to
"Annotates each entry with `"OK"` or `"STALE"` so downstream callers
can decide whether to render or skip."

### 3. `discover_aitasks_sessions()` registry loop

Update the loop body so STALE entries also propagate, with the new
`is_stale` flag set on STALE rows:

```python
for name, root, status in _read_registry_index():
    if name in live_names:
        continue
    found.append(AitasksSession(
        session=_read_default_session(root),
        project_root=root,
        project_name=name,
        is_live=False,
        is_stale=(status == "STALE"),
    ))
```

Note: `_read_default_session(root)` for a STALE entry will find the
config file missing and fall back to the literal `"aitasks"` — that
behavior is acceptable per the brainstorm and is independent of this
task. The synthesized session name for STALE rows is informational
only; selection of a STALE row will be handled by child E (t826_10).

### 4. `aitask_projects.sh` helper extraction

Insert `classify_registry_entry` in the **Helpers** section (after
`build_registry_yaml`, before the `# --- Verb: list -----` banner):

```bash
# Classify a registry entry by (name, path).
# Optional 3rd arg: newline-separated list of currently-live project_names
# (from live_tmux_project_names). When provided and the name matches, the
# entry is classified LIVE; otherwise OK/STALE based on the marker file.
# Echoes exactly one of: LIVE / OK / STALE.
classify_registry_entry() {
    local name="$1"
    local path="$2"
    local live="${3:-}"

    if [[ -n "$live" ]] && grep -Fxq "$name" <<< "$live" 2>/dev/null; then
        printf 'LIVE\n'
        return 0
    fi
    if [[ -d "$path" && -f "$path/aitasks/metadata/project_config.yaml" ]]; then
        printf 'OK\n'
    else
        printf 'STALE\n'
    fi
}
```

Refactor `cmd_list`'s inner classification (replaces the current
`if grep -Fxq ... elif [[ ... ]] ... else ... fi` block):

```bash
status=$(classify_registry_entry "$name" "$path" "$live")
```

The surrounding loop, padding, and `git_remote` print branches stay
identical — output remains byte-identical when no STALE entries are
present (current test coverage). The reuse contract for children B-D
is the same function call.

## Verification

1. `python3 tests/test_discover_include_registered.py` — extended
   with three new tests (3-tuple shape, STALE reaches consumer with
   `is_stale=True`, OK entry has `is_stale=False`). All existing
   tests still pass.
2. `python3 tests/test_discover_default_unchanged.py` — must still
   pass unchanged (the no-flag path is byte-identical to today).
3. `shellcheck .aitask-scripts/aitask_projects.sh` — clean.
4. Smoke-test `ait projects list` against the real registry to
   confirm `LIVE` / `OK` / `STALE` output is unchanged (pure refactor).

## Out of Scope

- New `ait projects` verbs (`remove`, `update`, `prune`, `doctor`) —
  children B/C/D (t826_7 / t826_8 / t826_9).
- Switcher rendering and selection of STALE entries — child E (t826_10).
- Caching the marker-file probe — decided against in the brainstorm.
- Updating `aidocs/cross_repo_references.md` — it does not currently
  document the Python helper's return shape; no edit required.

## Step 9 reference

Follow shared workflow Step 9 after Step 8 approval. Profile `fast`
works on the current branch; no worktree to clean up. Archival closes
t826_6 and leaves the next children (t826_7 / t826_8 / t826_9 /
t826_10 / t826_3 / t826_4) pickable.
