---
Task: t173_task_workflow_startup_improvement.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Create `aitask_own.sh` to consolidate Step 4 of task-workflow

## Context

Step 4 of `task-workflow/SKILL.md` currently requires the LLM to execute 4 separate shell operations sequentially (store email, lock task, update metadata, git add/commit/push). These operations are purely mechanical — no LLM reasoning needed — but they add noise to the context window and slow down execution. This refactors them into a single `aitask_own.sh` script, matching the pattern established by `aitask_archive.sh` for Step 9.

## Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| **Create** | `aiscripts/aitask_own.sh` | New script (~130 lines) |
| **Modify** | `.claude/skills/task-workflow/SKILL.md` | Replace manual Step 4 operations with single script call |
| **Modify** | `.claude/skills/aitask-pick/SKILL.md` | Replace Step 0c manual commands with `aitask_own.sh --sync` |
| **Modify** | `.claude/skills/aitask-explore/SKILL.md` | Replace sync step with `aitask_own.sh --sync` |
| **Modify** | `.claude/skills/aitask-fold/SKILL.md` | Replace sync step with `aitask_own.sh --sync` |
| **Modify** | `.claude/skills/aitask-review/SKILL.md` | Replace sync step with `aitask_own.sh --sync` |
| **Modify** | `seed/claude_settings.local.json` | Whitelist `aitask_own.sh` |
| **Modify** | `.claude/settings.local.json` | Whitelist `aitask_own.sh` (active settings) |

## 1. Create `aiscripts/aitask_own.sh`

**Interface:**
```bash
# Full ownership (lock + update + commit + push):
./aiscripts/aitask_own.sh <task_id> [--email <email>]

# Sync-only mode (pull + cleanup stale locks, no task_id needed):
./aiscripts/aitask_own.sh --sync
```

**What it does — full ownership mode (in order):**
1. Best-effort `git pull --ff-only` to sync with remote
2. Best-effort stale lock cleanup via `aitask_lock.sh --cleanup`
3. If `--email` provided: append to `aitasks/metadata/emails.txt` and deduplicate
4. Acquire atomic lock via `aitask_lock.sh --lock` (best-effort)
5. Update task status to `Implementing` (+ `assigned_to` if email) via `aitask_update.sh --batch`
6. `git add aitasks/ && git commit && git push` (push is best-effort)

**What it does — sync-only mode (`--sync`):**
1. Best-effort `git pull --ff-only`
2. Best-effort stale lock cleanup via `aitask_lock.sh --cleanup`
3. Exit immediately (no task operations)

**Structured output protocol (stdout, for LLM parsing):**
- `OWNED:<task_id>` — success (full mode only)
- `LOCK_FAILED:<owner>` — lock held by another user (exit 1, aborts before any changes)
- `LOCK_INFRA_MISSING` — lock infrastructure not initialized (exit 1, aborts with message "Run 'ait setup' to initialize lock infrastructure")
- `SYNCED` — sync-only mode completed successfully

**Structural template:** Follow `aitask_archive.sh` pattern — shebang, `set -euo pipefail`, source `terminal_compat.sh`, help function, argument parsing, main function.

**Key edge cases:**
- No email → skip lock silently (no warning, user chose this), call `aitask_update.sh` without `--assigned-to`
- Lock contention → print `LOCK_FAILED:<owner>`, exit 1 before any metadata changes
- Lock infra missing → print `LOCK_INFRA_MISSING`, exit 1 with message to run `ait setup`
- Push failure → warn but exit 0 (local commit is sufficient)
- Idempotent re-run → check `git diff --cached --quiet` before committing
- Child task IDs (e.g., `16_2`) → supported natively via regex `^t?[0-9]+(_[0-9]+)?$`
- `--sync` without task_id → valid, does pull+cleanup only

**Lock error detection:** Parse `aitask_lock.sh` stderr to distinguish:
- `"already locked by"` → lock contention (`LOCK_FAILED`)
- Any other failure (fetch failed, no remote) → infrastructure missing (`LOCK_INFRA_MISSING`)

## 2. Modify `task-workflow/SKILL.md` Step 4

**Keep unchanged:** The email selection logic (reading emails.txt, profile check for `default_email`, AskUserQuestion for email selection). These require LLM interaction.

**Replace lines 100-123** (from `- **Acquire atomic lock**` through `git push`) with a single block:

```markdown
- **Claim task ownership (lock, update status, commit, push):**
  If email was provided:
  ```bash
  ./aiscripts/aitask_own.sh <task_num> --email "<email>"
  ```
  If no email (user selected "Skip"):
  ```bash
  ./aiscripts/aitask_own.sh <task_num>
  ```

  **Parse the script output:**
  - `OWNED:<task_id>` — Success. Proceed to Step 5.
  - `LOCK_FAILED:<owner>` — Task claimed by another user. Inform user and return to task selection.
  - `LOCK_INFRA_MISSING` — Lock infrastructure not initialized. Inform user to run `ait setup` and abort.
```

Also update the `aitask_lock.sh` "Called by" header comment to add `aitask_own.sh`.

## 3. Modify calling skills — replace Step 0c sync commands

In all four calling skills, replace the two manual sync commands:
```bash
git pull --ff-only --quiet 2>/dev/null || true
./aiscripts/aitask_lock.sh --cleanup 2>/dev/null || true
```
with:
```bash
./aiscripts/aitask_own.sh --sync
```

**Files to update:**
- `.claude/skills/aitask-pick/SKILL.md` — Step 0c
- `.claude/skills/aitask-explore/SKILL.md` — sync step
- `.claude/skills/aitask-fold/SKILL.md` — sync step
- `.claude/skills/aitask-review/SKILL.md` — sync step

The description text around the command can stay the same (best-effort sync), just replace the two commands with one.

## 4. Whitelist `aitask_own.sh` in Claude Code settings

Add `"Bash(./aiscripts/aitask_own.sh:*)"` to the `permissions.allow` array in:
- `seed/claude_settings.local.json` (the template copied during installation)
- `.claude/settings.local.json` (the active settings for current repo)

This replaces the need for `aitask_lock.sh` and `git pull` to be individually whitelisted (they're now called internally by the script, not by the LLM).

## 5. Verification

1. Run `bash -n aiscripts/aitask_own.sh` — syntax check
2. Run `./aiscripts/aitask_own.sh --help` — verify help output
3. Run `./aiscripts/aitask_own.sh --sync` — test sync-only mode
4. Run `./aiscripts/aitask_own.sh 173 --email "dario-e@beyond-eye.com"` on the current task to verify end-to-end (task is already Implementing, so this tests idempotent re-run)
5. Verify SKILL.md changes are coherent by reading the full Step 4 section

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/aitask_own.sh` (~190 lines) consolidating Step 4 operations (email storage, lock, status update, commit, push) plus a `--sync` mode for pre-task-selection sync. Updated 8 files total: the new script, task-workflow SKILL.md, 4 calling skill SKILL.md files, 2 settings files, and aitask_lock.sh header comment.
- **Deviations from plan:** Script came out at ~190 lines instead of estimated ~130, mostly due to the comprehensive help text. No functional deviations.
- **Issues encountered:** None — all verification steps passed (syntax check, help output, sync-only mode, idempotent re-run).
- **Key decisions:** (1) In full ownership mode, `--sync` operations (pull + lock cleanup) run before lock acquisition for maximum freshness. (2) When no email is provided, lock is silently skipped (not an error) since the user explicitly chose "Skip". (3) `LOCK_INFRA_MISSING` causes hard abort with instruction to run `ait setup`, per user feedback.

## Step 9 (Post-Implementation)

Archive t173, commit, push per standard workflow.
