---
Task: t911_extract_priority_risk_enum_single_source.md
Base branch: main
plan_verified: []
---

# Plan: t911 — Extract the high|medium|low level enum to a single source

## Context

The `high | medium | low` enum is shared by four task frontmatter fields —
`priority`, `effort`, `risk_code_health`, `risk_goal_achievement` — and is
currently hardcoded at many sites across bash and Python. The parent feature
(t884, task risk evaluation) deliberately mirrored `priority`'s existing
duplication rather than introduce a shared constant inside the feature, and
filed this as a named follow-up (per `aidocs/planning_conventions.md` —
"name the refactor, don't bury it"). t911 removes the duplication by giving
the enum **one canonical definition per language**.

### Triage (the real scope, narrower than the task's "~15 files" estimate)

A direct scan of every `high`/`medium`/`low` occurrence found:

- **Genuine enum-membership duplication (migrate):**
  - Bash validation `case` blocks: `aitask_create.sh` (priority, effort) and
    `aitask_update.sh` (priority, `risk_code_health`, `risk_goal_achievement`,
    effort) — **6 blocks**.
  - Bash interactive fzf selection lists: `aitask_create.sh` (2),
    `aitask_update.sh` (4) — **6 sites**.
  - Python: **only** `board/aitask_board.py` (the two `CycleField` option
    lists). `settings/`, `brainstorm/`, `monitor/`, `agentcrew/` contain **no**
    level-enum literals (only unrelated color names) — the task's file list
    over-counted.
- **Out of scope (field-specific data / prose, NOT enum membership — left as-is):**
  - Per-value **sort weights** in `aitask_ls.sh` (priority high=1…, effort
    low=1…) — order is opposite per field; these are sort logic, not membership.
  - Per-value **border colors** in `board/aitask_board.py` (`_priority_border_color`).
  - **Display capitalization** ("High"/"Medium"/"Low"), **default values**
    (`"medium"` in archive/verification_followup/create_manual_verification),
    and **help-text prose**.
  - `aitask_issue_import.sh` / `aitask_pr_import.sh` fzf lists: deliberately
    ordered **default-first** (`medium\nhigh\nlow`); retained as a distinct UX
    (no validation occurs there). Documented, not migrated.
  - The separate **`status`** enum (`Ready|Editing|…`) — analogous duplication,
    different enum, explicitly a non-goal.

## Approach

**Per-language canonical constant + helpers** (chosen over a shared data file:
the three values are immutable framework vocabulary; a runtime data file would
add I/O on the hot `aitask_ls.sh`/board path plus a "what if someone edits it"
breakage surface that sort-weights structurally depend on — rejected for
over-engineering).

### 1. Bash source of truth — `.aitask-scripts/lib/task_utils.sh`

Already sourced by all five affected scripts and guarded by
`_AIT_TASK_UTILS_LOADED`, so adding functions is safe and needs no
test-scaffold change (it is not a `./ait` startup lib, and no *new* lib file is
introduced on the bash side).

Add near the other small helpers:

```bash
# Canonical task level enum (high/medium/low), shared by priority, effort,
# and the two risk fields. Single bash source of truth (Python mirror:
# .aitask-scripts/lib/task_levels.py).
TASK_LEVELS="high medium low"   # canonical, severity-descending

is_valid_task_level() {
    local val="$1" level
    for level in $TASK_LEVELS; do
        [[ "$val" == "$level" ]] && return 0
    done
    return 1
}

task_levels_lines()     { printf '%s\n' high medium low; }   # canonical (desc)
task_levels_lines_asc() { printf '%s\n' low medium high; }   # ascending
```

### 2. Replace the 6 bash validation blocks

In `aitask_create.sh` (priority ~1766, effort ~1771) and `aitask_update.sh`
(priority ~1562, risk_code_health ~1570, risk_goal_achievement ~1576, effort
~1584), replace each `case … high|medium|low … esac` with:

```bash
is_valid_task_level "$BATCH_PRIORITY" \
  || die "Invalid priority: $BATCH_PRIORITY (must be high, medium, or low)"
```

Keep each existing `die` message verbatim (field-appropriate prose — left
byte-stable to avoid churn and test breakage). `is_valid_task_level` returns
non-zero for the empty string, preserving current semantics (update.sh already
wraps these in `-n` guards; create.sh defaults to `medium`).

### 3. Migrate the 6 bash fzf selection lists

Replace the inline `echo -e "high\nmedium\nlow"` / `"low\nmedium\nhigh"` with
the emitters, piping into the existing `fzf` calls unchanged:

- `aitask_create.sh` `select_priority` → `task_levels_lines`
- `aitask_create.sh` `select_effort` → `task_levels_lines_asc`
- `aitask_update.sh` `interactive_update_priority` → `task_levels_lines`
- `aitask_update.sh` `interactive_update_risk_code_health` → `task_levels_lines`
- `aitask_update.sh` `interactive_update_risk_goal_achievement` → `task_levels_lines`
- `aitask_update.sh` `interactive_update_effort` → `task_levels_lines_asc`

(Orders preserved exactly — no UX change.)

### 4. Python source of truth — new `.aitask-scripts/lib/task_levels.py`

```python
"""Canonical task level enum (high/medium/low), shared by priority, effort,
and the two risk fields. Single Python source of truth — mirror of TASK_LEVELS
in .aitask-scripts/lib/task_utils.sh."""

LEVELS = ("high", "medium", "low")            # canonical, severity-descending
LEVELS_ASCENDING = ("low", "medium", "high")  # ascending, for UI pickers


def is_valid_level(value: str) -> bool:
    return value in LEVELS
```

In `board/aitask_board.py`: add `from task_levels import LEVELS_ASCENDING` to
the existing `lib`-import block (board already does
`sys.path.insert(0, …/lib)`), and change the two `CycleField` option lists
(~2562–2567) from `["low", "medium", "high"]` to `list(LEVELS_ASCENDING)`.
Order preserved → no cycle-behavior change. Colors and defaults stay untouched.

## Critical files

- `.aitask-scripts/lib/task_utils.sh` — add constant + 3 helpers
- `.aitask-scripts/lib/task_levels.py` — **new** Python constant module
- `.aitask-scripts/aitask_create.sh` — 2 validations + 2 fzf lists
- `.aitask-scripts/aitask_update.sh` — 4 validations + 4 fzf lists
- `.aitask-scripts/board/aitask_board.py` — import + 2 CycleField lists
- `tests/test_task_levels.sh` — **new** unit test (see Verification)

## Verification

- **New unit test** `tests/test_task_levels.sh` (self-contained, sources
  `task_utils.sh`): `is_valid_task_level` accepts `high`/`medium`/`low`,
  rejects `med`/`urgent`/`High`/`""`; `task_levels_lines`/`_asc` emit the exact
  3-line orders.
- **Existing** `bash tests/test_update_risk.sh` must still pass (exercises the
  migrated risk validation) — run before/after.
- **Bash invalid-input** smoke: `aitask_create.sh --batch … --priority bogus`
  and `aitask_update.sh --batch <id> --priority bogus` still `die` with the
  same message.
- **shellcheck** `.aitask-scripts/aitask_create.sh aitask_update.sh
  lib/task_utils.sh`.
- **Python import** check:
  `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import task_levels; assert task_levels.LEVELS==('high','medium','low')"`
  and `py_compile` `board/aitask_board.py`.
- **Manual (low-risk):** `ait board` → open a task's edit fields → confirm
  Priority/Effort cycle `low → medium → high` as before.

Post-implementation: standard Step 9 (review → commit → archive/merge per
profile).

## Risk

### Code-health risk: low
- Touches validation in the load-bearing `aitask_create.sh`/`aitask_update.sh`
  batch paths, but the change is a pure membership-check substitution with
  identical semantics, covered by `test_update_risk.sh` + a new unit test +
  shellcheck · severity: low · → mitigation: none needed.

### Goal-achievement risk: low
- None identified. The goal (one canonical definition per language) is
  unambiguous and the approach plainly delivers it; orders are preserved so
  there is no behavior change to misjudge.
