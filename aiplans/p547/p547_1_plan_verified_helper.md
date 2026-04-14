---
Task: t547_1_plan_verified_helper.md
Parent Task: aitasks/t547_plan_verify_on_off_in_task_workflow.md
Sibling Tasks: aitasks/t547/t547_*_*.md
Archived Sibling Plans: aiplans/archived/p547/p547_*_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified: []
---

# Context

This is the foundational child of t547. It builds the bash helper `aitask_plan_verified.sh` that the workflow (Child 3) will consume. The parent plan `aiplans/p547_plan_verify_on_off_in_task_workflow.md` describes the full architecture — read it first for the big picture.

The helper owns all the counting/staleness/decision logic so that the skill markdown stays trivial. Output is structured `KEY:value` lines on stdout, following the pattern set by `aitask_query_files.sh` and `aitask_scan_profiles.sh`.

No cross-project dependencies — this child is fully standalone and parallel-safe with Child 2.

# Files to create / modify

| File | Change |
|---|---|
| `.aitask-scripts/aitask_plan_verified.sh` | NEW |
| `.aitask-scripts/aitask_plan_externalize.sh` (`build_header()` ~line 248) | Add `plan_verified: []` emit line |
| `tests/test_plan_verified.sh` | NEW |

# Helper script design

## Boilerplate

```bash
#!/usr/bin/env bash
set -euo pipefail

# Double-sourcing guard
if [[ -n "${_AIT_PLAN_VERIFIED_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
_AIT_PLAN_VERIFIED_LOADED=1

# Resolve script dir and source terminal_compat
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
```

Dispatcher:

```bash
cmd="${1:-}"
shift || true
case "$cmd" in
    read)       cmd_read "$@" ;;
    append)     cmd_append "$@" ;;
    decide)     cmd_decide "$@" ;;
    ""|help|-h|--help) usage ;;
    *) die "Unknown subcommand: $cmd" ;;
esac
```

## `read <plan_file>`

Extract the header block (first `---` through second `---`), find the `plan_verified:` line, parse the immediate following list items, emit `<agent>|<timestamp>` per entry.

Algorithm (macOS-portable):

```bash
cmd_read() {
    local plan_file="${1:-}"
    [[ -z "$plan_file" ]] && die "read requires a plan file"
    [[ -f "$plan_file" ]] || die "plan file not found: $plan_file"

    # Extract header (between first two ^---$ lines)
    local header
    header=$(awk '/^---$/{c++; if(c==2) exit; next} c==1' "$plan_file")

    # Check if plan_verified exists at all and is not inline-empty
    local pv_start
    pv_start=$(printf '%s\n' "$header" | grep -n '^plan_verified:' | head -n1 | cut -d: -f1 || true)
    [[ -z "$pv_start" ]] && return 0  # no field → no entries

    local pv_line
    pv_line=$(printf '%s\n' "$header" | sed -n "${pv_start}p")
    [[ "$pv_line" == "plan_verified: []" ]] && return 0  # inline empty

    # Iterate lines after the plan_verified: line, collect list items
    local total_lines
    total_lines=$(printf '%s\n' "$header" | wc -l | tr -d ' ')
    local i=$((pv_start + 1))
    while [[ $i -le $total_lines ]]; do
        local line
        line=$(printf '%s\n' "$header" | sed -n "${i}p")
        # List item format: "  - <agent> @ <timestamp>"
        if [[ "$line" =~ ^[[:space:]]+-[[:space:]]+(.+)[[:space:]]@[[:space:]]+([0-9]{4}-[0-9]{2}-[0-9]{2}[[:space:]][0-9]{2}:[0-9]{2})[[:space:]]*$ ]]; then
            printf '%s|%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
        elif [[ "$line" =~ ^[[:space:]]*$ ]] || [[ ! "$line" =~ ^[[:space:]] ]]; then
            # Empty line OR non-indented line → end of list
            break
        fi
        # else: malformed indented line → skip silently
        i=$((i + 1))
    done
}
```

## `append <plan_file> <agent>`

```bash
cmd_append() {
    local plan_file="${1:-}"
    local agent="${2:-}"
    [[ -z "$plan_file" ]] && die "append requires a plan file"
    [[ -z "$agent" ]] && die "append requires an agent string"
    [[ -f "$plan_file" ]] || die "plan file not found: $plan_file"

    local ts
    ts=$(date '+%Y-%m-%d %H:%M')
    local new_entry="  - $agent @ $ts"

    # Find where the header ends (second ---)
    local header_end
    header_end=$(grep -n '^---$' "$plan_file" | sed -n '2p' | cut -d: -f1)
    [[ -z "$header_end" ]] && die "malformed plan header in: $plan_file"

    # Check if plan_verified already exists in the header region
    local pv_line_num
    pv_line_num=$(sed -n "1,${header_end}p" "$plan_file" | grep -n '^plan_verified:' | head -n1 | cut -d: -f1 || true)

    if [[ -z "$pv_line_num" ]]; then
        # No field → insert as new key + list item immediately before closing ---
        sed_inplace "${header_end}i\\
plan_verified:\\
${new_entry}
" "$plan_file"
    else
        local pv_content
        pv_content=$(sed -n "${pv_line_num}p" "$plan_file")
        if [[ "$pv_content" == "plan_verified: []" ]]; then
            # Inline empty → replace with key-only, then insert entry
            sed_inplace "${pv_line_num}c\\
plan_verified:\\
${new_entry}
" "$plan_file"
        else
            # Existing non-empty list → find the last list item and insert after it
            local i=$((pv_line_num + 1))
            local last_item=$pv_line_num
            while [[ $i -le $header_end ]]; do
                local line
                line=$(sed -n "${i}p" "$plan_file")
                if [[ "$line" =~ ^[[:space:]]+- ]]; then
                    last_item=$i
                elif [[ "$line" =~ ^[[:space:]]*$ ]] || [[ ! "$line" =~ ^[[:space:]] ]]; then
                    break
                fi
                i=$((i + 1))
            done
            sed_inplace "${last_item}a\\
${new_entry}
" "$plan_file"
        fi
    fi
}
```

**macOS note:** `sed_inplace` is defined in `lib/terminal_compat.sh` and handles BSD vs GNU sed differences. Multi-line insertion via `i\`, `a\`, `c\` is portable when each continuation uses `\\` at end of line. Test on both.

## `decide <plan_file> <required> <stale_after_hours>`

```bash
cmd_decide() {
    local plan_file="${1:-}"
    local required="${2:-}"
    local stale_hours="${3:-}"
    [[ -z "$plan_file" ]] && die "decide requires a plan file"
    [[ -z "$required" ]] && die "decide requires a required count"
    [[ -z "$stale_hours" ]] && die "decide requires stale_after_hours"
    [[ "$required" =~ ^[0-9]+$ ]] || die "required must be a positive integer: $required"
    [[ "$stale_hours" =~ ^[0-9]+$ ]] || die "stale_after_hours must be a positive integer: $stale_hours"

    if [[ ! -f "$plan_file" ]]; then
        printf 'TOTAL:0\nFRESH:0\nSTALE:0\nLAST:NONE\nREQUIRED:%s\nSTALE_AFTER_HOURS:%s\nDISPLAY:No plan file found.\nDECISION:VERIFY\n' "$required" "$stale_hours"
        return 0
    fi

    # Compute cutoff unix timestamp
    local cutoff_ts
    cutoff_ts=$(compute_cutoff "$stale_hours")

    local fresh=0
    local stale=0
    local total=0
    local last_entry="NONE"
    local last_ts=0

    while IFS='|' read -r agent timestamp; do
        [[ -z "$agent" ]] && continue
        total=$((total + 1))
        local entry_ts
        entry_ts=$(parse_ts "$timestamp") || continue
        if [[ $entry_ts -ge $cutoff_ts ]]; then
            fresh=$((fresh + 1))
        else
            stale=$((stale + 1))
        fi
        if [[ $entry_ts -gt $last_ts ]]; then
            last_ts=$entry_ts
            last_entry="$agent @ $timestamp"
        fi
    done < <(cmd_read "$plan_file")

    local display
    local decision
    if [[ $total -eq 0 ]]; then
        decision="VERIFY"
        display="No prior verifications found — entering verify mode."
    elif [[ $fresh -ge $required ]]; then
        decision="SKIP"
        display="Plan has $fresh fresh verification(s) (most recent: $last_entry). Skipping verification."
    else
        decision="ASK_STALE"
        display="Plan has $total verification(s) ($fresh fresh, $stale stale). Required: $required."
    fi

    printf 'TOTAL:%d\nFRESH:%d\nSTALE:%d\nLAST:%s\nREQUIRED:%s\nSTALE_AFTER_HOURS:%s\nDISPLAY:%s\nDECISION:%s\n' \
        "$total" "$fresh" "$stale" "$last_entry" "$required" "$stale_hours" "$display" "$decision"
}
```

### Helper: `compute_cutoff` and `parse_ts` (BSD/GNU date portability)

```bash
compute_cutoff() {
    local hours="$1"
    # GNU date (linux)
    if date -d "1 hour ago" +%s >/dev/null 2>&1; then
        date -d "${hours} hours ago" +%s
    else
        # BSD date (macOS)
        date -v-"${hours}"H +%s
    fi
}

parse_ts() {
    local ts="$1"   # Format: "YYYY-MM-DD HH:MM"
    if date -d "1 hour ago" +%s >/dev/null 2>&1; then
        date -d "$ts" +%s 2>/dev/null
    else
        date -jf '%Y-%m-%d %H:%M' "$ts" +%s 2>/dev/null
    fi
}
```

Return non-zero on parse failure so the caller can `|| continue`.

# `build_header()` update in `aitask_plan_externalize.sh`

Locate the function around line 248. At the end of the parent-task header construction (after `Base branch: ...`), append:

```bash
        printf '%s\n' "plan_verified: []"
```

Do the same at the end of the child-task branch. Place it as the last field before the closing `---` is emitted elsewhere in the calling code.

Verify by running externalize on a fresh test task — the header must contain `plan_verified: []` between `Base branch:` and `---`.

# Tests (`tests/test_plan_verified.sh`)

Follow the pattern in `tests/test_plan_externalize.sh`. Use `mktemp -d` for a sandbox. Source `assert_eq`/`assert_contains` from the standard test helper (inline them if the suite has no shared file — look at how existing tests bootstrap).

## Test fixtures

Create helper functions:
- `make_plan_basic` — writes a minimal header with no `plan_verified` field
- `make_plan_empty_list` — writes a header with `plan_verified: []`
- `make_plan_with_entries <n>` — writes a header with `n` entries using fresh timestamps
- `make_plan_with_stale <n>` — writes entries dated 48h ago

## Test cases

| Case | Setup | Call | Expected |
|---|---|---|---|
| read_no_field | basic | `read` | empty output |
| read_empty_list | empty_list | `read` | empty output |
| read_two_entries | with 2 fresh entries | `read` | 2 lines, `agent\|timestamp` format |
| read_malformed | header with 1 valid + 1 malformed line | `read` | 1 valid line only (malformed skipped) |
| append_no_field | basic | `append file agent` | header now has `plan_verified:` with 1 entry; `read` returns 1 line |
| append_empty_list | empty_list | `append file agent` | same as above |
| append_existing | with 1 entry | `append file agent` | header now has 2 entries; both readable |
| decide_no_file | (no file) | `decide missing.md 1 24` | output contains `DECISION:VERIFY` and `TOTAL:0` |
| decide_zero | basic | `decide file 1 24` | `DECISION:VERIFY`, `TOTAL:0` |
| decide_one_fresh_req1 | 1 fresh entry | `decide file 1 24` | `DECISION:SKIP`, `FRESH:1`, `STALE:0` |
| decide_one_fresh_req2 | 1 fresh entry | `decide file 2 24` | `DECISION:ASK_STALE`, `FRESH:1` |
| decide_one_stale | 1 stale entry (48h old) | `decide file 1 24` | `DECISION:ASK_STALE`, `FRESH:0`, `STALE:1` |
| decide_mix_fresh_stale_req1 | 1 fresh + 1 stale | `decide file 1 24` | `DECISION:SKIP`, `FRESH:1`, `STALE:1` |
| decide_mix_fresh_stale_req2 | 1 fresh + 1 stale | `decide file 2 24` | `DECISION:ASK_STALE` |
| decide_two_fresh_req1 | 2 fresh entries | `decide file 1 24` | `DECISION:SKIP`, `FRESH:2` |
| decide_display_line | basic | `decide file 1 24` | output contains `DISPLAY:No prior verifications` |
| decide_bad_required | basic | `decide file abc 24` | exit code non-zero, error mentions "positive integer" |

Wire these into a `main()` that prints PASS/FAIL counts and exits non-zero on any failure.

# Verification

1. `shellcheck .aitask-scripts/aitask_plan_verified.sh` — no errors
2. `bash tests/test_plan_verified.sh` — all cases pass
3. Create a dummy plan file with `plan_verified: []`, then run `./.aitask-scripts/aitask_plan_verified.sh append /tmp/dummy.md "claudecode/opus4_6"` and inspect — entry present and readable
4. Run `./.aitask-scripts/aitask_plan_verified.sh decide /tmp/dummy.md 1 24` — verify output is 8 lines in the documented order
5. Test `build_header()` update: run `aitask_plan_externalize.sh` on a Ready test task and grep the emitted header for `plan_verified: []`
6. macOS compatibility: if a mac is available, repeat tests on macOS. Otherwise verify manually that `date -v`, `sed -i ''`, and `mktemp` usage are correct per `aidocs/sed_macos_issues.md`

# Notes for sibling tasks

Child 3 consumes this helper. The interface contract — command names, argument order, output format, decision values — is stable. Any changes to these require updating the parent plan and Child 3's task description.

Malformed entry tolerance: the `read` subcommand MUST silently skip malformed list items without crashing, so that a manually-edited plan file with a typo doesn't brick `aitask-pick`.

BSD/GNU date portability is the main portability risk. Both branches are exercised in the tests — run them on Linux first, then on macOS if available.
