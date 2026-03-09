---
priority: high
effort: medium
depends: [t341_1]
issue_type: feature
status: Done
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-09 13:06
updated_at: 2026-03-09 17:03
completed_at: 2026-03-09 17:03
---

Add --target flag to aitask_contribute.sh for framework vs project dual-mode. Add --parent flag for hierarchical drill-down. Extend list_changed_files and generate_diff for project mode. Auto-detect project repo from git remote.

## Context

This is the second child of t341 (generalize aitask-contribute). Task t341_1 created `code_areas.yaml` format, the `parse_code_areas()` parser, and `aitask_codemap.sh`. This task adds the `--target` flag to `aitask_contribute.sh` so it can operate in two modes: framework (existing behavior, unchanged) and project (reads `code_areas.yaml`, diffs against local branches, creates issues on the project's own repo).

## Key Files to Modify

- **Modify** `.aitask-scripts/aitask_contribute.sh` — Add `ARG_TARGET`, `ARG_PARENT` variables; extend `parse_args()`; add `list_project_areas()` function; modify `list_areas()`, `list_changed_files()`, `generate_diff()`, `build_issue_body()`, `detect_contribute_mode()`, and `main()` for project mode
- **Extend** `tests/test_contribute.sh` — Tests for all new project-mode functionality

## Reference Files for Patterns

- `.aitask-scripts/aitask_contribute.sh:22-36` — Existing ARG_* batch variables
- `.aitask-scripts/aitask_contribute.sh:196-204` — `detect_contribute_mode()` to extend
- `.aitask-scripts/aitask_contribute.sh:229-248` — `list_areas()` to branch for project mode
- `.aitask-scripts/aitask_contribute.sh:269-299` — `list_changed_files()` to extend
- `.aitask-scripts/aitask_contribute.sh:301-335` — `generate_diff()` to extend
- `.aitask-scripts/aitask_contribute.sh:580-668` — `main()` flow
- Archived sibling plan `aiplans/archived/p341/p341_1_*.md` — for patterns established in t341_1

## Implementation Plan

### Step 1: Add new ARG variables and parse_args updates

Add to batch variables section (~line 22):
```bash
ARG_TARGET=""        # framework (default) or project
ARG_PARENT=""        # parent area name for hierarchical drill-down
```

Add to parse_args case statement (~line 548):
```bash
--target) ARG_TARGET="$2"; shift 2 ;;
--parent) ARG_PARENT="$2"; shift 2 ;;
```

Add validation after source platform check:
```bash
if [[ -n "$ARG_TARGET" ]]; then
    case "$ARG_TARGET" in
        framework|project) ;;
        *) die "Unknown target: $ARG_TARGET (supported: framework, project)" ;;
    esac
fi
```

### Step 2: Add list_project_areas() function

After `list_areas()` (~line 248), add:
```bash
list_project_areas() {
    local parent_filter="${ARG_PARENT:-}"
    echo "MODE:project"
    echo "TARGET:project"
    # parse_code_areas() was added by t341_1
    if [[ -n "$parent_filter" ]]; then
        parse_code_areas --parent "$parent_filter"
    else
        parse_code_areas
    fi
}
```

### Step 3: Modify list_areas() for dual-mode

Branch in `list_areas()`:
```bash
list_areas() {
    if [[ "$ARG_TARGET" == "project" ]]; then
        list_project_areas
        return
    fi
    # ... existing framework area listing code unchanged ...
}
```

### Step 4: Extend list_changed_files() for project mode

When `ARG_TARGET == "project"`, use `git diff main -- <dirs>` (same as clone mode). No upstream fetching needed:
```bash
list_changed_files() {
    local area_dirs="$1"
    local mode
    mode=$(detect_contribute_mode)
    IFS=',' read -ra dirs <<< "$area_dirs"

    if [[ "$mode" == "clone" || "$ARG_TARGET" == "project" ]]; then
        git diff --name-only main -- "${dirs[@]}" 2>/dev/null || true
    else
        # ... existing downstream mode unchanged ...
    fi
}
```

### Step 5: Extend generate_diff() for project mode

Similar — project mode uses `git diff main`:
```bash
generate_diff() {
    # ...
    if [[ "$mode" == "clone" || "$ARG_TARGET" == "project" ]]; then
        git diff main -- "${files[@]}"
    else
        # ... existing downstream mode unchanged ...
    fi
}
```

### Step 6: Extend resolve_area_dirs() for project mode

When `ARG_TARGET == "project"`, look up area in `code_areas.yaml` instead of AREAS array:
```bash
resolve_area_dirs() {
    local area_name="$1"
    if [[ "$ARG_TARGET" == "project" ]]; then
        # parse_code_areas outputs AREA|name|path|desc|parent
        local path
        path=$(parse_code_areas | awk -F'|' -v name="$area_name" '$2 == name {print $3; exit}')
        if [[ -z "$path" ]]; then
            die "Unknown project area: $area_name (check code_areas.yaml)"
        fi
        echo "$path"
        return 0
    fi
    # ... existing framework area resolution unchanged ...
}
```

### Step 7: Extend detect_contribute_mode() and main()

- `detect_contribute_mode()`: When `ARG_TARGET == "project"`, return `"project"`
- `main()`: When `ARG_TARGET == "project"` and `ARG_REPO` is empty, auto-detect from `git remote get-url origin`
- `build_issue_body()`: Minor header change for project contributions

### Step 8: Add tests

- Test `--list-areas` (no target) → unchanged output, backward compatible
- Test `--list-areas --target framework` → same as above
- Test `--list-areas --target project` → reads code_areas.yaml, outputs project areas
- Test `--list-areas --target project --parent <area>` → returns children only
- Test `--list-changes --target project --area <area>` → finds changed files
- Test dry-run with `--target project`

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_contribute.sh` passes
2. `bash tests/test_contribute.sh` — all tests pass (existing + new)
3. Existing `--list-areas` behavior is IDENTICAL (no regressions)
4. `--list-areas --target project` with a test `code_areas.yaml` returns correct areas
