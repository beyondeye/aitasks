---
Task: t815_dedup_read_yaml_field_definition.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t815 — Deduplicate `read_yaml_field` into a shared YAML lib

## Context

`read_yaml_field` is defined **twice**, independently:

- `.aitask-scripts/lib/task_utils.sh:282` — frontmatter-restricted (`---`…`---`),
  routes through `join_yaml_flow_lists`. Used by ~30 scripts that read
  markdown task/plan files.
- `.aitask-scripts/lib/agentcrew_utils.sh:92` — whole-file scan, inline
  bracket-depth flow-list join. Used by crew scripts that read plain
  `*_status.yaml` files (no `---` frontmatter).

`aitask_archive.sh` sources both libs (`task_utils.sh` then
`agentcrew_utils.sh`), so the **agentcrew copy silently shadows** the
task_utils copy at archive time. t813 had to fix *both* copies to land its
multi-line-flow-list bug fix — proving the duplication is a live footgun:
any future edit to one copy silently diverges depending on source order.

A function-name audit of the two libs confirms `read_yaml_field` is the
**only** collision (`comm -12` of their function lists). `read_yaml_list`
lives only in `agentcrew_utils.sh` today but is the same class of helper and
belongs with it.

**Goal:** one canonical `read_yaml_field`, in one place, behaviour-preserving
for every current caller, guarded against re-introduction.

## Approach

Per the task's own suggested fix: `agentcrew_utils.sh` is sourced standalone
by crew scripts (cannot depend on `task_utils.sh`), so extract the shared
YAML readers into a **new dedicated leaf lib** that both libs source.

### The behaviour problem

The two copies are *not* interchangeable:
- task_utils copy requires `---` frontmatter delimiters → returns nothing on a
  plain YAML file.
- agentcrew copy scans the whole file → can match a stray body line in a
  markdown file.

Crew `*_status.yaml` files are plain YAML (no `---`); markdown task/plan files
always open with `---`. The canonical function detects which by the **first
line** and behaves accordingly — a strict superset of both, behaviour-
preserving for every current caller and strictly safer for `aitask_archive.sh`
(its `.md` reads become frontmatter-restricted instead of whole-file).

## Files to change

### 1. NEW — `.aitask-scripts/lib/yaml_utils.sh`

Pure leaf lib: bash + `sed`/`grep`/`tr` only, **no** `terminal_compat.sh`
dependency, **no** `SCRIPT_DIR` manipulation (must not clobber a caller's).

```bash
#!/usr/bin/env bash
# yaml_utils.sh - Canonical YAML readers shared by task_utils.sh and
# agentcrew_utils.sh. Pure bash; no dependencies. Source this; do not execute.
#
# read_yaml_field lived independently in both task_utils.sh and
# agentcrew_utils.sh; whichever lib was sourced last silently won (t815).
# Keeping it here, behind a double-source guard, makes one definition canonical.

[[ -n "${_AIT_YAML_UTILS_LOADED:-}" ]] && return 0
_AIT_YAML_UTILS_LOADED=1
```

Then move, **verbatim except where noted**:

- `join_yaml_flow_lists()` — moved verbatim from `task_utils.sh` (its only
  caller is `read_yaml_field`).
- `read_yaml_list()` — moved verbatim from `agentcrew_utils.sh` (whole-file
  scan; unchanged).
- `read_yaml_field()` — **canonical**, based on the task_utils copy (regex +
  `join_yaml_flow_lists`), with the frontmatter restriction relaxed to a
  whole-file fallback when the file has no frontmatter:

```bash
# read_yaml_field <file> <field>
# Extracts a scalar YAML field as a single line.
#   - Markdown task/plan files open with a `---` frontmatter delimiter; only
#     the frontmatter block is searched.
#   - Plain YAML files (crew *_status.yaml) have no frontmatter; the whole
#     file is searched.
# Flow lists wrapped across physical lines (PyYAML wraps past ~80 cols) are
# rejoined via join_yaml_flow_lists. Prints "" and returns 0 if not found.
read_yaml_field() {
    local file_path="$1"
    local field_name="$2"
    local in_yaml=false has_frontmatter=false line first_line=""

    IFS= read -r first_line < "$file_path" 2>/dev/null || true
    [[ "$first_line" == "---" ]] && has_frontmatter=true

    while IFS= read -r line; do
        if [[ "$has_frontmatter" == true && "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ ( "$has_frontmatter" == false || "$in_yaml" == true ) \
              && "$line" =~ ^${field_name}:[[:space:]]*(.*) ]]; then
            local value="${BASH_REMATCH[1]}"
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$value"
            return
        fi
    done < <(join_yaml_flow_lists < "$file_path")

    echo ""
}
```

### 2. `.aitask-scripts/lib/task_utils.sh`

- After the existing `source` lines (~line 14, after `archive_utils.sh`), add:
  ```bash
  # shellcheck source=yaml_utils.sh
  source "${SCRIPT_DIR}/lib/yaml_utils.sh"
  ```
  (`SCRIPT_DIR` here = `.aitask-scripts/`.)
- Delete the `join_yaml_flow_lists()` definition (~lines 248–279) and the
  `read_yaml_field()` definition (~lines 281–308). Keep `parse_yaml_list()`
  and `read_task_status()` (the latter still calls `read_yaml_field`, now
  resolved via the sourced `yaml_utils.sh`).

### 3. `.aitask-scripts/lib/agentcrew_utils.sh`

- After `source "$SCRIPT_DIR/terminal_compat.sh"` (~line 11), add:
  ```bash
  # shellcheck source=yaml_utils.sh
  source "$SCRIPT_DIR/yaml_utils.sh"
  ```
  (`SCRIPT_DIR` here = the `lib/` dir.)
- Delete the `read_yaml_field()` definition (~lines 86–114) and the
  `read_yaml_list()` definition (~lines 116–167).

### 4. `.aitask-scripts/aitask_archive.sh`

`aitask_archive.sh` uses **only** `read_yaml_field` / `read_yaml_list` from
`agentcrew_utils.sh` (verified — no `crew_*` / `AGENT*_STATUS` / `detect_*`
symbols). Both are now provided transitively by `task_utils.sh` →
`yaml_utils.sh`, so the dedicated `agentcrew_utils.sh` source and its
`SCRIPT_DIR`-preservation dance (~lines 29–33) are removed entirely. This
also eliminates the collision site itself.

### 5. NEW — `tests/test_yaml_utils.sh`

Self-contained bash test (`assert_eq`/`assert_contains` pattern, matching
`tests/test_update_multiline_yaml.sh`). Sources **both** `task_utils.sh` and
`agentcrew_utils.sh`, then asserts:

- `read_yaml_field` on a markdown frontmatter file: scalar field, wrapped
  multi-line flow list (`verifies`), missing field → `""`.
- `read_yaml_field` **frontmatter restriction**: a `status:`-prefixed line in
  the markdown *body* is NOT matched (the frontmatter value wins).
- `read_yaml_field` on a **plain YAML file with no frontmatter** (crew
  `*_status.yaml` shape) — the previously-divergent agentcrew behaviour;
  scalar fields resolve correctly.
- `read_yaml_list` still works: inline, wrapped, and block-style lists.
- **Collision regression guard:** `grep` asserts `task_utils.sh` and
  `agentcrew_utils.sh` no longer contain a `read_yaml_field()` definition and
  `yaml_utils.sh` does — fails loudly if a copy is re-introduced.
- Double-source guard: sourcing `yaml_utils.sh` twice is a no-op.
- `bash -n` syntax check on all three libs + `aitask_archive.sh`.

## Out of scope / verified non-issues

- **No seed/installer change:** `seed/` ships no `.aitask-scripts/lib/`
  manifest; the framework dir is copied wholesale, so a new lib is picked up
  automatically.
- **No test-scaffold change:** `yaml_utils.sh` is *not* in `./ait`'s
  source-on-startup chain (only `aitask_path.sh` is) — it is sourced
  transitively by `task_utils.sh`/`agentcrew_utils.sh`. The CLAUDE.md rule to
  also register libs in `tests/lib/test_scaffold.sh` applies only to the
  startup chain, so no change there.

## Verification

```bash
# New + existing regression suites
bash tests/test_yaml_utils.sh
bash tests/test_update_multiline_yaml.sh        # t813 suite must still pass

# Broader archive regressions (exercise read_yaml_field/list via archive)
for t in test_archive_utils test_archive_scan test_archive_folded; do
  bash tests/$t.sh
done

# Crew scripts still resolve read_yaml_field (no task_utils dependency)
bash -n .aitask-scripts/aitask_crew_command.sh \
        .aitask-scripts/aitask_crew_cleanup.sh \
        .aitask-scripts/aitask_crew_setmode.sh

# Lint
shellcheck .aitask-scripts/lib/yaml_utils.sh \
           .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/lib/agentcrew_utils.sh \
           .aitask-scripts/aitask_archive.sh
```

Expected: all suites pass; `shellcheck` shows only the pre-existing baseline
findings recorded in the t813 plan (SC1091 source-not-followed, etc.) and
nothing pointing at the new code.

Also confirm no caller references `join_yaml_flow_lists` from a context that
no longer reaches it (grep `.aitask-scripts/` + `tests/` — expected: only
`yaml_utils.sh`, the libs that source it, and `test_update_multiline_yaml.sh`).

## Step 9 — Post-Implementation

Profile 'fast', current branch — no worktree to clean up. Commit code +
`tests/`, then archive via `./.aitask-scripts/aitask_archive.sh 815` and
`./ait git push`.
