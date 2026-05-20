---
Task: t813_fix_aitask_update_multiline_yaml_list_parsing.md
Worktree: (current branch — no separate worktree)
Branch: (current branch)
Base branch: main
---

# Plan: Fix `aitask_update.sh` frontmatter parser truncating multi-line YAML flow lists (t813)

## Context

The line-by-line frontmatter parser in `.aitask-scripts/aitask_update.sh`
(`parse_yaml_frontmatter`, lines 338–383) matches each physical line against
`^([a-z_]+):(.*)$`. When a list-valued field (`children_to_implement`,
`depends`, `verifies`, `labels`, `folded_tasks`, `file_references`) is
serialized as a YAML **flow sequence wrapped across multiple lines**, the
continuation lines start with whitespace, fail the key regex, and are silently
dropped. A subsequent `--add-child`/`--remove-child` then rewrites the field
with only the truncated subset, **permanently losing the continuation entries**.

The only producer that wraps is the board: `task_yaml.py` calls
`yaml.dump(...)` with PyYAML's default `width=80`. Verified empirically — an
18-entry `children_to_implement` wraps onto 3 lines, the first ending exactly
`... t777_10,` (matching the real-world `t777` corruption described in the task).
Bash's `format_yaml_list` always emits a single line, so wrapping never comes
from the bash side.

The same first-line-only bug exists in two **reader** helpers that
`aitask_archive.sh` depends on, so a board-written wrapped list also does not
survive an archival read:
- `read_yaml_field()` in `lib/task_utils.sh` — used by archive for `folded_tasks`
  and `verifies`.
- `read_yaml_list()` in `lib/agentcrew_utils.sh` — used by archive at line 453
  to read the parent's `children_to_implement` ("are all children complete?").

This plan fixes the wrapped-list bug end-to-end so `aitask_update.sh`,
`aitask_archive.sh`, and the board agree on list serialization/parsing.

## Approach

Two-pronged: stop the board from ever wrapping (the only producer), and make
the bash readers tolerant of wrapped lists (for already-corrupted/historical
files and general robustness).

### 1. `.aitask-scripts/lib/task_utils.sh` — add shared join helper + fix `read_yaml_field`

Add a pure-bash stdin filter near the YAML helpers (after `format_yaml_list`,
~line 246):

```bash
# Join YAML flow-sequence values that wrap across multiple physical lines.
# Reads YAML text on stdin; emits it with any "key: [ ... ]" whose brackets
# span multiple lines collapsed onto a single physical line. Continuation
# lines are appended with a separating space (harmless — list parsers strip
# spaces). Bracket-depth tracked so multi-line wraps of any length collapse.
join_yaml_flow_lists() {
    local line buffer="" depth=0 opens closes
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ $depth -gt 0 ]]; then buffer+=" $line"; else buffer="$line"; fi
        opens="${buffer//[^\[]/}"
        closes="${buffer//[^\]]/}"
        depth=$(( ${#opens} - ${#closes} ))
        if [[ $depth -le 0 ]]; then
            printf '%s\n' "$buffer"
            buffer=""
            depth=0
        fi
    done
    [[ -n "$buffer" ]] && printf '%s\n' "$buffer"
    return 0   # explicit — last [[ ]] test would otherwise leak exit 1
}
```

Fix `read_yaml_field()` (line ~270): change `done < "$file_path"` to
`done < <(join_yaml_flow_lists < "$file_path")` so a wrapped flow-list value is
already collapsed before the field-match loop sees it. (Loop still breaks at
the closing `---`, so body markdown links are never reached.)

### 2. `.aitask-scripts/aitask_update.sh` — fix `parse_yaml_frontmatter`

Line 383: change `done <<< "$yaml_content"` to
`done < <(printf '%s\n' "$yaml_content" | join_yaml_flow_lists)`.

`join_yaml_flow_lists` is already available — `aitask_update.sh` sources
`task_utils.sh` at line 11. After the join, the existing `^([a-z_]+):(.*)$`
regex captures the full single-line `[...]` value, and `parse_yaml_list`
(which strips brackets/quotes/all spaces) handles it unchanged. No change
needed to the per-field `case` block — the fix covers **all** list-valued
fields at once because it operates before field dispatch.

### 3. `.aitask-scripts/lib/agentcrew_utils.sh` — fix `read_yaml_list`

`agentcrew_utils.sh` is sourced standalone by crew scripts that do **not**
source `task_utils.sh`, so the fix must be self-contained (no dependency on
`join_yaml_flow_lists`).

Replace the `grep ... | head -n 1` single-line grab (lines 102–107) with a
capture loop that appends continuation lines until brackets balance:

```bash
# Capture the field's value, joining a wrapped flow list onto one line.
local value="" capturing=false depth=0 fline opens closes
while IFS= read -r fline; do
    if [[ "$capturing" == false ]]; then
        [[ "$fline" == "${field}:"* ]] || continue
        capturing=true
        value="${fline#"${field}":}"
    else
        value="$value $fline"
    fi
    opens="${value//[^\[]/}"
    closes="${value//[^\]]/}"
    depth=$(( ${#opens} - ${#closes} ))
    [[ $depth -le 0 ]] && break
done < "$file"
[[ "$capturing" == false ]] && return 0
value="${value#"${value%%[![:space:]]*}"}"   # ltrim
```

The existing inline-format branch (`^\[.*\]$` → `tr`/`sed` split) and the
block-format branch are kept as-is. For a block-style list the field line has
an empty value → `depth` stays 0 → `break` immediately → `value` is empty →
falls through to the block-format loop (which re-reads the file independently),
so block parsing is unaffected.

### 4. `.aitask-scripts/board/task_yaml.py` — stop the board from wrapping

In `serialize_frontmatter()` (line 116), add `width=` to the `yaml.dump` call
so flow lists are never line-wrapped:

```python
frontmatter = yaml.dump(ordered, Dumper=_FlowListDumper,
                        default_flow_style=False, sort_keys=False,
                        width=4096)
```

Verified: `width=4096` keeps an 18-entry list on a single line. This is the
systemic fix — `task_yaml.py` is the sole wrapping producer and is shared by
both the board (`aitask_board.py`) and `aitask_merge.py`, so one change covers
every Python writer. Add a brief comment noting why `width` is set.

### 5. `tests/test_update_multiline_yaml.sh` — new self-contained test

Follows the `tests/test_format_yaml_list.sh` convention (`assert_eq` helper,
`PASS/FAIL/TOTAL` summary, `bash -n` syntax check, exit non-zero on failure).
Self-contained: builds a temp `aitasks/` dir, calls the real scripts by
absolute path (no `ait` dispatcher, no git — omit `--commit`). Cases:

1. **Round-trip (core acceptance):** write `t900_test.md` with a
   `children_to_implement` flow list wrapped across 3 physical lines (exact
   PyYAML shape from the empirical check). Run
   `aitask_update.sh --batch 900 --remove-child t900_1`; re-read the file and
   assert the field contains `t900_2..t900_18` (17 entries) and not `t900_1` —
   i.e. no continuation entries lost.
2. **`--add-child`** on the same wrapped list — assert the new child is added
   and all pre-existing entries survive.
3. **Wrapped `depends`** round-trip via an unrelated `--status` update — assert
   the wrapped `depends` list is preserved intact.
4. **`join_yaml_flow_lists` unit cases** — single line unchanged; 3-line wrap
   collapsed; `depends: []` and a scalar `issue:` URL untouched.
5. **`read_yaml_list`** (source `agentcrew_utils.sh`) on a wrapped inline list
   — returns all entries; also a non-wrapped inline list and a block list still
   work.
6. **`read_yaml_field`** (source `task_utils.sh`) on a wrapped `verifies` list
   — returns the full `[...]` value.
7. **Board agreement** — run an inline `python3` snippet importing
   `task_yaml.serialize_frontmatter` with a long `children_to_implement`;
   assert the serialized output keeps the field on one physical line.

## Files to modify

| File | Change |
|------|--------|
| `.aitask-scripts/lib/task_utils.sh` | Add `join_yaml_flow_lists()`; route `read_yaml_field()` input through it |
| `.aitask-scripts/aitask_update.sh` | `parse_yaml_frontmatter`: pipe `yaml_content` through `join_yaml_flow_lists` |
| `.aitask-scripts/lib/agentcrew_utils.sh` | `read_yaml_list()`: self-contained continuation-line join for wrapped inline lists |
| `.aitask-scripts/board/task_yaml.py` | `serialize_frontmatter()`: add `width=4096` to `yaml.dump` |
| `tests/test_update_multiline_yaml.sh` | New test (created) |

No new system lib is added to `./ait`'s source chain, so
`tests/lib/test_scaffold.sh` needs no change.

## Verification

```bash
# New test
bash tests/test_update_multiline_yaml.sh

# Regression — existing YAML/update/archive tests still pass
bash tests/test_format_yaml_list.sh
bash tests/test_update_check.sh
bash tests/test_update_landing.sh
bash tests/test_archive_utils.sh
bash tests/test_archive_scan.sh

# Lint
shellcheck .aitask-scripts/aitask_update.sh \
           .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/lib/agentcrew_utils.sh
bash -n .aitask-scripts/aitask_update.sh

# Board serializer sanity
python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/board'); \
import task_yaml; \
md={'children_to_implement':['t1_%d'%i for i in range(1,30)]}; \
out=task_yaml.serialize_frontmatter(md,'body',['children_to_implement']); \
print('WRAPPED' if any(l.startswith(' ') for l in out.splitlines()) else 'OK')"
```

Expected: new test passes; existing tests unchanged; shellcheck clean; board
sanity prints `OK`.

## Post-implementation note

`task_yaml.py` is shared with the board TUI and `aitask_merge.py`; the change
is confined to a pure serializer function (no TUI/keybinding surface), so the
TUI-conventions review does not apply. Step 9 will merge on the current branch
and archive via `aitask_archive.sh 813`.
