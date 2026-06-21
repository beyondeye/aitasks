---
Task: t1029_registry_record_namedtuple.md
Worktree: (none - profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Registry Record NamedTuple (t1029)

## Summary

Convert `_parse_registry_records()` in `.aitask-scripts/lib/agent_launch_utils.py`
from returning raw 5-tuples to returning a named record type, then update every
direct Python consumer to use field names. Keep the serialized registry format
and public CLI output byte-for-byte unchanged.

## Key Changes

- Add a small `RegistryRecord` `NamedTuple` with fields `name`, `path`,
  `git_remote`, `last_opened`, and `project_group`.
- Change `_parse_registry_records()` to return `list[RegistryRecord]` and append
  `RegistryRecord(...)` objects in `_flush()`.
- Update `_read_registry_index()`, `_cli_list_registry()`, and
  `_cli_resolve_index()` to access parser results by attribute instead of
  positional unpacking.
- Preserve `_read_registry_index()`'s existing public return shape:
  `(name, Path, status, project_group)`.
- Add a focused regression test proving `_parse_registry_records()` exposes all
  five fields by name.

## Risk

- **Code-health risk:** low. The change narrows a fragile internal contract while
  preserving existing serialized output and downstream `_read_registry_index()`
  tuple shape.
- **Goal-achievement risk:** low. The affected parser consumers are concentrated
  in one module and covered by registry parity plus discovery tests.

### Planned mitigations

None.

## Verification

- `python3 -m py_compile .aitask-scripts/lib/agent_launch_utils.py`
- `python3 -m unittest tests.test_project_groups tests.test_discover_include_registered`
- `bash tests/test_registry_reader_parity.sh`
- `bash tests/test_projects_cmd.sh`

## Final Implementation Notes

- **Actual work done:** Added `RegistryRecord`, changed `_parse_registry_records()`
  to return named records, migrated direct parser consumers to attribute access,
  and added a regression test for named-field access.
- **Deviations from plan:** None.
- **Issues encountered:** No implementation issues. The task had no pre-existing
  external plan file because the initial plan was produced in chat; this plan was
  written during workflow continuation before committing.
- **Key decisions:** Kept `_read_registry_index()` returning its existing
  4-tuple interface to avoid broadening the refactor beyond the parser boundary.
- **Upstream defects identified:** None.
