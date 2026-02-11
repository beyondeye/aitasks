---
Task: t77_in_the_aitask_statssh_shell_script_i_would_like_to_make_firs.md
Branch: main (working on current branch)
Base branch: main
---

# Plan: Add configurable first day of week to aitask_stats.sh

## Context

The `aitask_stats.sh` script currently hardcodes Monday as the first day of the week. The user wants a `-w` option that takes a day name prefix (e.g., `sun`, `mon`, `tu`) and configures which day is treated as the week start. If the match is ambiguous or not found, default to Monday with a warning.

## File to modify

- `aitask_stats.sh` (single file change)

## Implementation Steps

### 1. Add `-w` option to help text

Add `-w, --week-start DAY` option and example to help text.

### 2. Add default value and argument parsing

- Add `WEEK_START_DOW=1` default (1=Monday in `%u` format)
- Add `-w|--week-start` case in argument parser
- After parsing, resolve the string to a day number via a matching function

### 3. Add `resolve_week_start()` function

Prefix-match input against full day names, warn on ambiguous/no match, default to Monday.

### 4. Modify `get_week_start()` function

Generalize offset: `(dow - WEEK_START_DOW + 7) % 7`

### 5. Modify `print_dow_averages()`

Iterate starting from `WEEK_START_DOW` with wrap-around.

### 6. Modify `print_label_dow()`

Dynamic header and iteration starting from `WEEK_START_DOW`.

## Verification

1. `./aitask_stats.sh` — default Monday behavior preserved
2. `./aitask_stats.sh -w sun` — tables start with Sunday
3. `./aitask_stats.sh -w s` — ambiguous warning, proceeds with Monday
4. `./aitask_stats.sh -w xyz` — no-match warning, proceeds with Monday
5. `./aitask_stats.sh -w Mon` — case insensitive

## Final Implementation Notes
- **Actual work done:** All 6 steps implemented as planned. Added `-w`/`--week-start` option with prefix matching, ambiguity/no-match warnings, and updated all day-of-week display sections to respect the configured start day.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** The "This Week" column dash logic was updated to use modular offset comparison rather than simple `dow > current_dow`, ensuring correct behavior regardless of which day starts the week.

## Post-Implementation

Step 9 from aitask-pick: archive task and plan files.
