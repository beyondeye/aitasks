---
Task: t238_aitask_own_lock.md
Branch: main
Base branch: main
---

## Context

Task t238 addresses a documentation gap: the `/aitask-pickweb` website page recommends `ait own` for pre-locking tasks, but `ait own` is not a public command. The board TUI can lock tasks, but there's no CLI equivalent. The task asks whether to expose `ait lock` or `ait own` (or both).

**Decision:** Expose only `ait lock` (not `ait own`). Rationale:
- The board TUI only locks (no status change, no `assigned_to` update) — the CLI should match
- Pre-locking should be lightweight — the "Implementing" status change happens later when `/aitask-pick` runs
- `aitask_own.sh` stays internal, called only by skills

## Plan

### Step 1: Modify `aiscripts/aitask_lock.sh` — Add email auto-detection and user-friendly mode

Currently `--lock` requires explicit `--email`. Changes:

1. **Source `task_utils.sh`** (line ~23) — needed for `get_user_email()`. The double-source guard in `terminal_compat.sh` prevents issues since both files source it.

2. **Add `get_user_email_with_fallback()` helper** — mirrors the board TUI's `_get_user_email()` Python logic: tries `get_user_email()` from task_utils.sh (userconfig.yaml), then falls back to first line of `emails.txt`.

3. **Modify `--lock` handler** (lines 381-388) — make `--email` optional; auto-detect when omitted. Die with helpful message if no email source found.

4. **Add bare task-ID shortcut** in the `*` case (line 412) — treat `ait lock 42` as `ait lock --lock 42`. Parse `^t?[0-9]+(_[0-9]+)?$` pattern, then same email resolution logic.

5. **Update header comment** (lines 1-18) — remove "Internal" language, show public usage patterns.

6. **Update `show_help()`** (lines 351-368) — document public usage with `ait lock` prefix, note `--email` is optional.

### Step 2: Modify `ait` dispatcher — Add `lock` command

- Add `lock` command to case statement
- Add `lock` to help text
- Add `lock` to update-check skip list

### Step 3: Update website — `aitask-pickweb.md`

Replace 3 occurrences of `ait own` with `ait lock`.

### Step 4: Create website page — `website/content/docs/commands/lock.md`

New page documenting all `ait lock` subcommands, email auto-detection, and pre-locking workflow.

### Step 5: Update website — `commands/_index.md`

Add `ait lock` row to command table and usage examples.

### Step 6: Update tests — `tests/test_task_lock.sh`

Add `task_utils.sh` to test setup. New test cases for email auto-detection, fallback, error, and bare-ID shortcut.

## Verification
1. Run `bash tests/test_task_lock.sh` — all existing + new tests pass
2. Run `shellcheck aiscripts/aitask_lock.sh` — no warnings
3. Test manually: `ait lock --help`, `ait lock 42`, `ait lock --list`
4. Verify website builds: `cd website && hugo build --gc --minify`

## Final Implementation Notes
- **Actual work done:** All 6 steps implemented as planned. Exposed `ait lock` as a public CLI command with email auto-detection and bare task-ID shortcut. Updated aitask-pickweb docs to reference `ait lock` instead of `ait own`. Created new website documentation page. Added 5 new tests.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used a `resolve_lock_email()` helper function to share email resolution logic between the `--lock` handler and the bare task-ID handler, avoiding code duplication. Sourced `task_utils.sh` for `get_user_email()` and added `get_user_email_with_fallback()` that mirrors the board TUI's Python logic.

## Post-Review Changes

### Change Request 1 (2026-02-24 23:40)
- **Requested by user:** Clarify in the lock doc page that `ait lock` is not needed before `/aitask-pick` (which handles locking automatically). Make clear it's only for signaling intent to other users. Even `/aitask-pickweb` (the main pre-locking use case) works without pre-locking.
- **Changes made:** Rewrote "Locking vs Ownership" section in `lock.md`. Added new "When to Use `ait lock`" section explaining that `/aitask-pick` handles locking automatically, and listing the actual use cases (pickweb, reserving for later, multi-agent coordination). Updated pickweb section to note pre-locking is recommended but not required.
- **Files affected:** `website/content/docs/commands/lock.md`

## Post-Implementation (Step 9)
Archive task, push.
