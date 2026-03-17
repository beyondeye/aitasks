---
Task: t405_consolidate_lock_precheck_into_pick_own.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

Task-workflow SKILL.md Step 4 currently makes two sequential bash calls to handle task locking:
1. `aitask_lock.sh --check` — read-only pre-check (lines 118-141)
2. `aitask_pick_own.sh` — actual lock acquisition + status update (lines 143-187)

The pre-check is redundant because `aitask_pick_own.sh` already returns `LOCK_FAILED:<owner>` when lock acquisition fails, and the SKILL already handles that case. The only gap: `LOCK_FAILED` currently doesn't include lock details (`locked_at`, `hostname`), so the SKILL calls `--check` again after a failure to get them.

## Plan

### Step 1: Add `LOCK_HOLDER:` structured output to `aitask_lock.sh`

**File:** `.aitask-scripts/aitask_lock.sh` (lines 121-133)

In `lock_task()`, when a lock conflict is detected (locked by different user), output a structured `LOCK_HOLDER:` line to stdout before calling `die`. This lets `aitask_pick_own.sh` parse lock details without a separate `--check` call.

Changes:
- Extract `hostname` from lock content (add 2 lines after line 126)
- Add `echo "LOCK_HOLDER:${locked_by}|${locked_at}|${locked_hostname}"` before the `die` on line 132

```bash
# After line 126, add hostname extraction:
local locked_hostname
locked_hostname=$(echo "$lock_content" | grep '^hostname:' | sed 's/hostname: *//')
[[ -z "$locked_hostname" ]] && locked_hostname="unknown"

# Before die on line 132, add structured output:
echo "LOCK_HOLDER:${locked_by}|${locked_at}|${locked_hostname}"
die "Task t$task_id is already locked by $locked_by (since $locked_at, hostname: $locked_hostname)"
```

### Step 2: Enrich `LOCK_FAILED` output in `aitask_pick_own.sh`

**File:** `.aitask-scripts/aitask_pick_own.sh` (lines 162-178, `acquire_lock()` function)

Parse the `LOCK_HOLDER:` line from lock output and include details in `LOCK_FAILED`:

```bash
1)  # Already locked by another user
    local holder_line owner locked_at locked_hostname
    holder_line=$(echo "$lock_output" | grep '^LOCK_HOLDER:' || true)
    if [[ -n "$holder_line" ]]; then
        local details="${holder_line#LOCK_HOLDER:}"
        owner=$(echo "$details" | cut -d'|' -f1)
        locked_at=$(echo "$details" | cut -d'|' -f2)
        locked_hostname=$(echo "$details" | cut -d'|' -f3)
    else
        owner=$(echo "$lock_output" | grep -o 'already locked by [^ ]*' | sed 's/already locked by //')
        locked_at="unknown"
        locked_hostname="unknown"
    fi
    [[ -z "$owner" ]] && owner="unknown"
    echo "LOCK_FAILED:${owner}|${locked_at}|${locked_hostname}"
    return 1 ;;
```

Also update the script header comment (line 18) to document the new format:
```
#   LOCK_FAILED:<owner>|<locked_at>|<hostname>   Lock held by another user (exit 1)
```

### Step 3: Simplify SKILL.md Step 4 — remove lock pre-check

**File:** `.claude/skills/task-workflow/SKILL.md` (lines 118-187)

**Remove** the entire "Lock pre-check (read-only)" subsection (lines 118-141). This eliminates the `aitask_lock.sh --check` call.

**Update** the `LOCK_FAILED` handler (lines 162-173) to parse the enriched format instead of calling `--check`:

Before:
```
- `LOCK_FAILED:<owner>` — Task is locked by another user/PC. Run `aitask_lock.sh --check <task_num>` to get lock details...
```

After:
```
- `LOCK_FAILED:<owner>|<locked_at>|<hostname>` — Task is locked by another user/PC. Use AskUserQuestion:
    - Question: "Task t<N> is locked by <owner> (since <locked_at>, hostname: <hostname>). Force unlock?"
    - Header: "Lock"
    - Options:
      - "Force unlock and claim" (description: "Override the stale lock and claim this task")
      - "Pick a different task" (description: "Leave the lock intact and select another task")
    - If "Force unlock and claim": Re-run ownership with `--force`
    - If "Pick a different task": Return to calling skill's task selection
```

The "same user already has lock" case is handled automatically by `lock_task()` (idempotent refresh → success → `OWNED`).

### Step 4: Update SKILL.md Step 7 LOCK_FAILED reference

**File:** `.claude/skills/task-workflow/SKILL.md` (line 264)

Update from `LOCK_FAILED:<owner>` to `LOCK_FAILED:<owner>|<locked_at>|<hostname>` in the pre-implementation guard section.

### Step 5: Update aitask-pickrem SKILL.md

**File:** `.claude/skills/aitask-pickrem/SKILL.md` (line 145)

Update `LOCK_FAILED:<owner>` reference to `LOCK_FAILED:<owner>|<locked_at>|<hostname>`. The parsing logic only uses `<owner>` for display, so just update the format documentation — no behavioral change needed since the `<owner>` is still the first field before `|`.

### Step 6: Update aitask_pick_own.sh help text

**File:** `.aitask-scripts/aitask_pick_own.sh` (lines 68-69)

Update the help text output format documentation from `LOCK_FAILED:<owner>` to `LOCK_FAILED:<owner>|<locked_at>|<hostname>`.

## Files Modified

| File | Change |
|------|--------|
| `.aitask-scripts/aitask_lock.sh` | Add hostname extraction + `LOCK_HOLDER:` output in `lock_task()` |
| `.aitask-scripts/aitask_pick_own.sh` | Parse `LOCK_HOLDER:` in `acquire_lock()`, enrich `LOCK_FAILED` output, update help text |
| `.claude/skills/task-workflow/SKILL.md` | Remove lock pre-check subsection, update `LOCK_FAILED` handler |
| `.claude/skills/aitask-pickrem/SKILL.md` | Update `LOCK_FAILED` format reference |

## Not Modified

| File | Reason |
|------|--------|
| `.claude/skills/aitask-pickweb/SKILL.md` | Uses `aitask_lock.sh --check` as standalone informational check (no `aitask_pick_own.sh`), unaffected |
| `tests/test_lock_force.sh` | Uses `assert_contains` (substring match), `LOCK_FAILED:alice@test.com` still matches enriched format |
| `aitask_lock.sh --check` command | Unchanged — still useful as standalone CLI tool |

## Verification

1. Run existing tests: `bash tests/test_lock_force.sh` — all should pass (substring matching)
2. Run shellcheck: `shellcheck .aitask-scripts/aitask_lock.sh .aitask-scripts/aitask_pick_own.sh`
3. Syntax check: `bash -n .aitask-scripts/aitask_lock.sh && bash -n .aitask-scripts/aitask_pick_own.sh`

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned — all 6 steps completed
- **Deviations from plan:** None
- **Issues encountered:** None — existing tests passed without modification due to substring matching in `assert_contains`
- **Key decisions:** Used `|` as field separator in `LOCK_FAILED` output to avoid conflicts with `:` in timestamps (HH:MM format). Added `LOCK_HOLDER:` structured line to stdout in `aitask_lock.sh` before the `die` call to stderr, allowing `aitask_pick_own.sh` to parse lock details from a single `lock_task()` invocation without a separate `--check` call.

## Step 9: Post-Implementation

Archive task, release lock, commit plan file, push.
