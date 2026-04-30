---
Task: t723_crash_recovery_pid_anchor_in_pick_workflow.md
Base branch: main
plan_verified: []
---

# Plan: t723 — Crash Recovery via PID Anchor in Pick Workflow

## Context

When tmux (or the host shell) crashes mid-implementation, the agent dies but the task's `status: Implementing` and lock file persist. On re-pick, today's flow detects this via `RECLAIM_STATUS:` (emitted whenever `prev_status == Implementing` and `prev_assigned == EMAIL`), but:

- The user-visible prompt says *"no active lock holds it"* — wrong for the common same-host crash case where the lock IS still held.
- We can't tell *"prior agent crashed"* from *"prior agent live and rerunning"* — both look the same to `aitask_lock.sh` (silent re-lock on hostname match).
- The user accepts/declines reclaim with no orientation on what the prior agent already changed.
- All reclaim branches are inlined in `task-workflow/SKILL.md` Step 4 — should live in their own procedure file per the project's "extract new procedures" convention.

This task adds a PID anchor (`pid` + `pid_starttime`) to lock metadata, introduces a new `RECLAIM_CRASH:` signal when the anchored process is gone, surveys in-progress work before prompting, and extracts the reclaim handling into a dedicated `crash-recovery.md` procedure.

Folds and resolves t694 (which asked whether same-host stale-lock warnings warrant a time-threshold UX). PID liveness is a sharp binary signal that sidesteps the threshold question entirely.

---

## Files to modify / create

### Modify
- `.aitask-scripts/aitask_lock.sh` — write `pid`/`pid_starttime` to lock YAML; emit `PRIOR_LOCK:` signal on re-acquire; source new lib
- `.aitask-scripts/aitask_pick_own.sh` — capture `PRIOR_LOCK:` signal; emit `RECLAIM_CRASH:` when prior PID is dead
- `.claude/skills/task-workflow/SKILL.md` — Step 4 reclaim handling becomes a thin dispatcher to the new procedure; Step 7 ownership-guard reuses procedure for cross-host case; add procedure to the bottom Procedures list

### Create
- `.aitask-scripts/lib/pid_anchor.sh` — sourced helper: `get_pid_starttime()`, `is_lock_holder_alive()`
- `.aitask-scripts/aitask_backfill_pid_anchor.sh` — one-shot helper to retrofit existing `Implementing` locks
- `.claude/skills/task-workflow/crash-recovery.md` — new procedure file
- `tests/test_crash_recovery_pid_anchor.sh` — new test, modeled on `tests/test_lock_reclaim.sh`
- 5 whitelist mirrors (see Step 8)

---

## Step 1 — `lib/pid_anchor.sh` (new file)

```bash
#!/usr/bin/env bash
# Single source of truth for PID-anchor helpers used by lock/pick scripts.
# Idempotent: safe to source multiple times.

[[ -n "${_AIT_PID_ANCHOR_LOADED:-}" ]] && return 0
_AIT_PID_ANCHOR_LOADED=1

# Linux: read /proc/<pid>/stat field 22 (jiffies since boot — invariant per
# process; survives PID recycling because new processes get fresh starttime).
# macOS: returns "-" — starttime check is skipped on Darwin (PID-recycling
# is a known minor edge case there; PID liveness via kill -0 still works).
get_pid_starttime() {
    local pid="${1:-}"
    [[ -z "$pid" || "$pid" == "-" ]] && { echo "-"; return; }
    [[ ! -r "/proc/$pid/stat" ]] && { echo "-"; return; }
    local raw
    raw=$(cat "/proc/$pid/stat" 2>/dev/null) || { echo "-"; return; }
    # comm field may contain spaces/parens — split after the LAST ')'
    local after_comm="${raw##*) }"
    local fields
    read -ra fields <<<"$after_comm"
    # fields[19] is original field 22 (state ppid pgrp ... -> starttime is 20th after stripping "pid (comm)")
    echo "${fields[19]:--}"
}

# Returns 0 if pid is running and (when starttime != "-") starttime matches.
is_lock_holder_alive() {
    local pid="${1:-}" starttime="${2:--}"
    [[ -z "$pid" || "$pid" == "-" ]] && return 1
    kill -0 "$pid" 2>/dev/null || return 1
    if [[ -n "$starttime" && "$starttime" != "-" ]]; then
        local current
        current=$(get_pid_starttime "$pid")
        [[ "$current" == "$starttime" ]] || return 1
    fi
    return 0
}
```

Make executable: `chmod +x .aitask-scripts/lib/pid_anchor.sh` (script-only file; no whitelist touchpoints since it is sourced, never invoked directly).

---

## Step 2 — `aitask_lock.sh` changes

### 2a — Source the helper

Near the existing source lines at the top of `aitask_lock.sh`:
```bash
source "$SCRIPT_DIR/lib/pid_anchor.sh"
```

### 2b — Determine the PID to anchor

Add helper near `get_hostname()` (~line 72):
```bash
get_lock_pid() {
    # PPID is the agent's bash/claude process. When it dies (tmux crash),
    # kill -0 returns ESRCH — that's our crash signal.
    echo "$PPID"
}
```

### 2c — Capture prior lock content BEFORE overwriting

In `acquire_lock()`, immediately after the existing fetch (around line 136 — `git fetch origin "$BRANCH"`), before assembling the new YAML:
```bash
# Read prior lock content (if any) so we can surface it for crash-recovery
# detection in aitask_pick_own.sh. After fetch, refs/remotes/origin/$BRANCH
# is fresh — no extra network roundtrip needed.
local prior_yaml=""
if git rev-parse --verify "origin/$BRANCH:$lock_file" >/dev/null 2>&1; then
    prior_yaml=$(git show "origin/$BRANCH:$lock_file" 2>/dev/null || true)
fi
if [[ -n "$prior_yaml" ]]; then
    local prior_pid prior_starttime prior_host prior_locked_at
    prior_pid=$(echo "$prior_yaml" | grep '^pid:' | sed 's/pid: *//')
    prior_starttime=$(echo "$prior_yaml" | grep '^pid_starttime:' | sed 's/pid_starttime: *//')
    prior_host=$(echo "$prior_yaml" | grep '^hostname:' | sed 's/hostname: *//')
    prior_locked_at=$(echo "$prior_yaml" | grep '^locked_at:' | sed 's/locked_at: *//')
    # Empty fields collapse to "-" so the parser in pick_own can rely on shape.
    echo "PRIOR_LOCK:${prior_pid:--}|${prior_starttime:--}|${prior_host:--}|${prior_locked_at:--}"
fi
```

### 2d — Write PID fields into new lock YAML

Replace the existing YAML assembly (lines 178-182):
```bash
local lock_pid lock_starttime
lock_pid=$(get_lock_pid)
lock_starttime=$(get_pid_starttime "$lock_pid")
lock_yaml="task_id: $task_id
locked_by: $email
locked_at: $(get_timestamp)
hostname: $(get_hostname)
pid: $lock_pid
pid_starttime: $lock_starttime"
```

### 2e — Backward compat for existing locks

Lock files written by older versions lack `pid:`/`pid_starttime:`. The `prior_pid` parser above returns empty → emitted as `-` → `is_lock_holder_alive` treats `-` as not-alive → flow falls into `RECLAIM_STATUS:` branch (preserves today's behavior). No explicit migration needed.

---

## Step 3 — `aitask_pick_own.sh` changes

### 3a — Source the helper

Near the existing sources at top:
```bash
source "$SCRIPT_DIR/lib/pid_anchor.sh"
```

### 3b — Capture `PRIOR_LOCK:` from acquire output

The existing flow (line 167-169) already pipes/captures `lock_output` from `acquire_lock`. Extend the parsing in `acquire_lock` (the wrapper in `aitask_pick_own.sh:152-170`) to ALSO capture `PRIOR_LOCK:`:

```bash
# Existing forward of LOCK_RECLAIM:
echo "$lock_output" | grep '^LOCK_RECLAIM:' || true
# NEW: forward PRIOR_LOCK: too
echo "$lock_output" | grep '^PRIOR_LOCK:' || true
```

Then in `main()` (~line 280), capture the PRIOR_LOCK fields by running acquire_lock through a tee:

Actually the cleaner path: `acquire_lock` is called as `acquire_lock "$TASK_ID" "$EMAIL" || lock_result=$?` (line 301). The function in `aitask_pick_own.sh` already echoes `LOCK_RECLAIM:`/`LOCK_FAILED:` to stdout — just add the same forwarding for `PRIOR_LOCK:`. Then in `main()`, capture stdout of `acquire_lock` to a variable so we can grep for `PRIOR_LOCK:` after the call. Refactor:

```bash
local acquire_output
acquire_output=$(acquire_lock "$TASK_ID" "$EMAIL" 2>&1) || lock_result=$?
echo "$acquire_output"  # forward to caller (preserves LOCK_RECLAIM/LOCK_FAILED)

local prior_pid="-" prior_starttime="-" prior_host="-" prior_locked_at="-"
local prior_line
prior_line=$(echo "$acquire_output" | grep '^PRIOR_LOCK:' | head -1)
if [[ -n "$prior_line" ]]; then
    IFS='|' read -r prior_pid prior_starttime prior_host prior_locked_at \
        <<<"${prior_line#PRIOR_LOCK:}"
fi
```

### 3c — Emit `RECLAIM_CRASH:` when prior PID is dead

Replace the existing post-claim block (lines 329-336) with:

```bash
if [[ "$prev_status" == "Implementing" && -n "$EMAIL" \
      && "$prev_assigned" == "$EMAIL" ]]; then
    # Prior status indicates a reclaim. Decide which signal to emit.
    # LOCK_RECLAIM: was already emitted by aitask_lock.sh if cross-host.
    # If same host AND prior PID is gone (or starttime mismatches) → CRASH.
    # Otherwise → STATUS (the lock-anomaly fallback).
    local current_host
    current_host=$(hostname 2>/dev/null || echo "unknown")
    if [[ "$prior_host" == "$current_host" ]] \
       && ! is_lock_holder_alive "$prior_pid" "$prior_starttime"; then
        echo "RECLAIM_CRASH:${prior_locked_at}|${prior_host}|${prior_pid}"
    else
        echo "RECLAIM_STATUS:${prev_status}|${prev_assigned}"
    fi
fi
```

Note: when `LOCK_RECLAIM:` (cross-host) was emitted by `aitask_lock.sh`, we still emit one of `RECLAIM_CRASH:` / `RECLAIM_STATUS:` here — that's fine, the SKILL.md dispatcher will prefer `LOCK_RECLAIM:` over the others when multiple signals are present.

---

## Step 4 — `crash-recovery.md` (new procedure file)

Create `.claude/skills/task-workflow/crash-recovery.md`:

```markdown
# Crash Recovery Procedure

Called from task-workflow Step 4 (and Step 7 ownership guard) when one or
more reclaim signals are emitted by `aitask_pick_own.sh`. Surveys
in-progress work, displays a case-appropriate prompt, and returns the
user's decision (`reclaim` | `decline`).

## Inputs (from caller context)

- `task_id`, `task_name`, `task_file`, `EMAIL`
- Parsed signal fields:
  - `signal_type`: one of `LOCK_RECLAIM`, `RECLAIM_CRASH`, `RECLAIM_STATUS`
    (when multiple signals are emitted, prefer in this order:
    `LOCK_RECLAIM` > `RECLAIM_CRASH` > `RECLAIM_STATUS`)
  - For `LOCK_RECLAIM`: `prev_hostname`, `prev_locked_at`, `current_hostname`
  - For `RECLAIM_CRASH`: `prev_locked_at`, `prev_hostname`, `prev_pid`
  - For `RECLAIM_STATUS`: `prev_status`, `prev_assigned_to`

## Step 1 — Survey in-progress work

The previous agent may have left uncommitted changes the user should know
about before deciding to reclaim. Run these read-only checks:

1. Worktree check:
   `git worktree list --porcelain`
   If a line `branch refs/heads/aitask/<task_name>` is present, capture the
   `worktree <path>` two lines above. `cd <path>` for the next checks.
   Otherwise run them on the current directory.

2. Status + diff:
   `git status --porcelain | head -20`
   `git diff --stat HEAD | tail -10`

3. Plan file:
   `./.aitask-scripts/aitask_query_files.sh plan-file <task_id>`
   If `PLAN_FILE:<path>` is returned, tail the file for the most-recent
   marker — "Final Implementation Notes", a checked-step marker, or a
   "Post-Review Changes" section.

Build a short summary block (3-6 lines):
```
Prior in-progress work:
- Worktree: <path or "(current branch)">
- N modified files (M staged), K untracked
- Plan: <one-line progress hint>
```

If there are no uncommitted changes and no plan progress, the summary is
"Prior in-progress work: none detected".

## Step 2 — Case-specific prompt

Use `AskUserQuestion`:

- `LOCK_RECLAIM` (multi-PC):
  Question: "Task t<N> is already in `Implementing`, claimed by you on
  `<prev_hostname>` since `<prev_locked_at>` (current host:
  `<current_hostname>`).\n\n<survey>\n\nReclaim and continue here?"

- `RECLAIM_CRASH` (same-host crash):
  Question: "Previous agent on this machine appears to have crashed (PID
  `<prev_pid>` no longer running since `<prev_locked_at>`).\n\n<survey>\n\n
  Resume with prior work intact?"

- `RECLAIM_STATUS` (anomaly — lock missing or pre-PID-anchor lock):
  Question: "Task t<N> shows status `Implementing` already assigned to
  you, but no PID anchor matches your environment.\n\n<survey>\n\n
  Reclaim and continue here?"

Header: "Reclaim"

Options:
- "Reclaim and continue" (description: "Resume work — the lock is held here, prior in-progress changes remain intact")
- "Pick a different task" (description: "Release the lock, revert to Ready, choose another task")

## Step 3 — Handle decision

If "Reclaim and continue": return `reclaim` to caller.

If "Pick a different task": run lock release, revert status, commit, push:
```
./.aitask-scripts/aitask_lock.sh --unlock <task_id> 2>/dev/null || true
./.aitask-scripts/aitask_update.sh --batch <task_id> --status Ready --assigned-to ""
./ait git add aitasks/
./ait git commit -m "ait: Revert t<task_id> to Ready (reclaim declined)" 2>/dev/null || true
./ait git push
```
Return `decline` to caller.
```

## Step 5 — `task-workflow/SKILL.md` Step 4 dispatcher refactor

Replace lines 140-158 (the existing `LOCK_RECLAIM:`/`RECLAIM_STATUS:` branch) with a thinner dispatcher:

```
- One of `LOCK_RECLAIM:`, `RECLAIM_CRASH:`, or `RECLAIM_STATUS:` (in addition to `OWNED:`) — task was already in `Implementing`. When multiple are present, prefer `LOCK_RECLAIM` > `RECLAIM_CRASH` > `RECLAIM_STATUS`. Parse the signal-specific fields (see below) and execute the **Crash Recovery Procedure** (see `crash-recovery.md`) with `signal_type` and the parsed fields.

  Signal field formats:
  - `LOCK_RECLAIM:<prev_hostname>|<prev_locked_at>|<current_hostname>`
  - `RECLAIM_CRASH:<prev_locked_at>|<prev_hostname>|<prev_pid>`
  - `RECLAIM_STATUS:<prev_status>|<prev_assigned_to>`

  When the procedure returns:
  - `reclaim` → proceed to Step 5 normally.
  - `decline` → return to the calling skill's task selection. Do NOT proceed.
```

Also update the "Procedures" list at the bottom of `task-workflow/SKILL.md`:
```
- **Crash Recovery Procedure** (`crash-recovery.md`) — Surveys in-progress work and prompts the user when a reclaim signal is detected (multi-PC, same-host crash, or lock anomaly). Referenced from Step 4 and Step 7 ownership guard.
```

## Step 6 — `task-workflow/SKILL.md` Step 7 ownership guard

Lines 247-266 already detect a cross-host re-lock and surface the same prompt as Step 4's `LOCK_RECLAIM:` branch. Update to call the **Crash Recovery Procedure** with `signal_type=LOCK_RECLAIM` instead of inlining the AskUserQuestion. Same-host crash recovery is moot here (Step 7 only fires after Step 4 already succeeded — `aitask_pick_own.sh` already surfaced any crash signal).

## Step 7 — Tests

Create `tests/test_crash_recovery_pid_anchor.sh`, modeled on `tests/test_lock_reclaim.sh` (paired bare+local repo, hostname shim). Cases:

1. **Lock writes PID fields:** acquire lock; `git show origin/aitask-locks:t<N>_lock.yaml` contains `pid:` and (on Linux) `pid_starttime:` lines.
2. **Same-host crash recovery:** manually overwrite the lock YAML with `pid: 999999` (known-dead) + `pid_starttime: 99999999` + same hostname; set task status `Implementing` + `assigned_to: <email>`; run `aitask_pick_own.sh <N> --email <email>`; assert output contains `RECLAIM_CRASH:`.
3. **PID-recycling defense (Linux only):** lock with `pid: $$` (live) but `pid_starttime: 99999999` (mismatch); assert `RECLAIM_CRASH:`.
4. **Live agent — no recovery signal:** lock with `pid: $$` and current `pid_starttime` of `$$`; assert no `RECLAIM_CRASH:` is emitted; instead emits `RECLAIM_STATUS:` (legacy fallback because we're not actually a fresh agent).
5. **Cross-host still emits `LOCK_RECLAIM:`:** lock with `hostname: PC_A`; pick under `TEST_HOSTNAME=PC_B`; assert `LOCK_RECLAIM:` appears.
6. **Backward compat:** lock written without `pid:`/`pid_starttime:` fields; assert no `RECLAIM_CRASH:`, falls back to `RECLAIM_STATUS:`.
7. **macOS portability stub:** if `[[ "$(uname)" == "Darwin" ]]`, skip starttime-related assertions but verify `pid:` is still written and `kill -0`-only liveness check works.

Pattern reference: `tests/test_lock_reclaim.sh` lines 54-110 for harness setup, lines 139-142 for `git show` verification.

## Step 8 — Backfill existing `Implementing` tasks

One-time helper: `.aitask-scripts/aitask_backfill_pid_anchor.sh` (new). Run once as part of deploying this change so that tasks currently stuck in `status: Implementing` (e.g., from a prior tmux crash) can be reclaimed via the new `RECLAIM_CRASH:` flow instead of the legacy `RECLAIM_STATUS:` fallback.

Behavior:

1. List all tasks under `aitasks/` (excluding `archived/`) with `status: Implementing`.
2. For each, fetch its lock from `origin/aitask-locks` (one fetch up front, then `git show` per task).
3. If the lock file is missing → no backfill possible (the `RECLAIM_STATUS:` branch will still handle it on next pick).
4. If the lock file exists AND lacks `pid:` (pre-anchor lock) → rewrite the lock YAML with `pid: 0` and `pid_starttime: -`. `pid: 0` is a sentinel that fails `kill -0` (you cannot signal init or process group 0 from userspace as a regular user via `kill -0 0` — and even where it doesn't fail, the starttime mismatch on `-` skips that check and lets `kill -0` decide). Verify portability: `kill -0 0` on Linux returns `Operation not permitted` (errno EPERM, exit 1) for non-root users, which our `is_lock_holder_alive` treats as "dead" via the `kill -0 ... || return 1` line. (If we want to be defensive, use `pid: 1` only if process 1 doesn't have to be alive — but PID 1 IS always alive on a running system, so it would falsely report "alive". Use `pid: 0`.)
5. If the lock file exists AND already has a `pid:` field → skip (assume it was written by the new code).
6. Commit the rewritten locks on `aitask-locks` branch with message `ait: Backfill PID anchor for N Implementing locks`.

**Edge case to verify during implementation:** does `kill -0 0` actually return non-zero on Linux for the current user? If it returns 0 (e.g., on some kernels or in containers), use `pid: -1` instead (definitely invalid). The implementation MUST include a self-test at script start: try `kill -0 <chosen_sentinel>` and confirm exit != 0; abort with a clear error if not.

Script structure mirrors existing one-off helpers (e.g., look at the structure of `aitask_lock.sh --cleanup` for the lock-branch-rewrite pattern).

**Invocation:** run manually once per deployed PC: `./.aitask-scripts/aitask_backfill_pid_anchor.sh`. Print summary: `Backfilled N locks; M already had PID anchors; K locks missing entirely (RECLAIM_STATUS will handle).`

**Whitelist touchpoints (per CLAUDE.md "Adding a New Helper Script"):**
- `.claude/settings.local.json` permissions.allow: `"Bash(./.aitask-scripts/aitask_backfill_pid_anchor.sh:*)"`
- `.gemini/policies/aitasks-whitelist.toml`: `[[rules]]` with `commandPrefix = "./.aitask-scripts/aitask_backfill_pid_anchor.sh"`
- `seed/claude_settings.local.json`: mirror of the above
- `seed/geminicli_policies/aitasks-whitelist.toml`: mirror
- `seed/opencode_config.seed.json`: `"./.aitask-scripts/aitask_backfill_pid_anchor.sh *": "allow"`
- (Codex needs no entry.)

**Test:** add to `tests/test_crash_recovery_pid_anchor.sh` — case 8: write a pre-anchor lock + Implementing task; run backfill; verify lock now has `pid: 0` and a re-pick emits `RECLAIM_CRASH:`.

## Step 9 — Resolves t694 (folded)

Document in Final Implementation Notes that PID liveness is the resolution: no time threshold, no project_config/userconfig key, aliveness is binary. t694's investigation question becomes moot.

---

## Verification

- `bash tests/test_crash_recovery_pid_anchor.sh` — all cases pass on Linux. macOS: cases 1, 2 (PID-only), 4, 5, 6 must pass; case 3 (starttime defense) skipped on Darwin.
- `shellcheck .aitask-scripts/aitask_lock.sh .aitask-scripts/aitask_pick_own.sh .aitask-scripts/lib/pid_anchor.sh` — clean.
- Manual end-to-end:
  1. `/aitask-pick <some-task>`; let it claim and reach plan mode.
  2. `kill -9 $$` from a sibling shell to simulate tmux crash (or `tmux kill-server`).
  3. Restart tmux/Claude; `/aitask-pick <same-task>`.
  4. Verify the prompt reads "Previous agent on this machine appears to have crashed (PID … since …)" and includes the in-progress work survey.
  5. Verify "Pick a different task" cleanly reverts to Ready.

## Out of scope

- Multi-PC reclaim wording (untouched — t692 already handles it; `LOCK_RECLAIM:` flows through unchanged).
- Auto-recovery / auto-resume of partially-implemented work (we surface state; user decides).
- `aitask_lock.sh --cleanup` semantics (still archive-only).
- Cross-user lock takeover (already handled).

## Step 10 — Post-Implementation

Standard archival flow per `task-workflow/SKILL.md` Step 9. Folded task t694 will be deleted by `aitask_archive.sh` automatically (status `Folded`, content already incorporated above).

After merging this task to `main` and before next-pick, run the backfill once on the dev PC:
```
./.aitask-scripts/aitask_backfill_pid_anchor.sh
```
This converts any pre-existing `Implementing` locks (likely including the user's tmux-crashed work) so they surface via `RECLAIM_CRASH:` on next `/aitask-pick`.

## Final Implementation Notes

- **Actual work done:** Shipped exactly as planned across 4 new files and 9 modified files. PID anchor (`pid:` + `pid_starttime:`) is now written to lock YAML; `aitask_pick_own.sh` emits a new `RECLAIM_CRASH:` signal when the prior agent's PID is dead (or starttime mismatches → defends PID recycling); a new `crash-recovery.md` procedure dispatches case-specific prompts (multi-PC vs. same-host crash vs. lock anomaly) and surveys in-progress work before asking the user to reclaim. Backfill helper retrofits pre-anchor locks. 18-case test suite added. 9 existing test setups updated to copy the new `lib/pid_anchor.sh` helper.

- **Deviations from plan:** None of substance. Two small implementation-time refinements:
  1. `is_lock_holder_alive` got an explicit `pid == "0"` guard so `pid: 0` is the unambiguous "treat as crashed" sentinel — independent of platform-specific `kill -0 0` semantics. The backfill script's self-test then reduces to a sanity check on the helper.
  2. Backfill script needed `find -L` (follow symlinks) because `aitasks/` is a symlink to `.aitask-data/aitasks` in this repo's data-worktree layout. Caught and fixed during dry-run.

- **Issues encountered:** Initial test 5 (pre-anchor lock backward-compat) failed because my new field-extraction lines (`prior_pid=$(grep '^pid:' | sed ...)`) hit `set -euo pipefail` when grep didn't match, killing the script. Fixed by adding `|| true` to those greps — same pattern the existing code already uses elsewhere. After fix, all 18 cases pass on first try.

- **Key decisions:**
  - Used `$PPID` rather than `$$` as the anchor PID. The lock script is invoked by the agent's bash/claude process; `$PPID` IS the agent process. When the agent dies (tmux crash), `kill -0 $PPID` returns ESRCH — exactly the signal we want.
  - Sentinel `pid: 0` chosen over `pid: -1` because the `is_lock_holder_alive` helper guards `pid == "0"` explicitly, making the sentinel platform-independent.
  - Cross-host reclaim retains its existing wording — `LOCK_RECLAIM:` flows through unchanged. `crash-recovery.md` dispatches by signal type.
  - Backfill uses a single batch commit on `aitask-locks` rather than one commit per lock — keeps history clean and avoids race-prone serial pushes.

- **Upstream defects identified:**
  - `tests/test_archive_verification_gate.sh:?` and `tests/test_archive_carryover.sh:?` — pre-existing test failures (15 + 4 cases) caused by `aitask_verification_parse.sh` sourcing `lib/aitask_path.sh` and `lib/python_resolve.sh` which the test setups don't copy. Errors look like `lib/aitask_path.sh: No such file or directory`. Unrelated to this task; surfaces a pattern: any new lib helper sourced by a script needs to be added to the copy-list of every test that exercises that script. Worth a focused follow-up that audits all test setup helpers for completeness.
  - `aitask_lock.sh:408` — pre-existing `SC2086` shellcheck warning (`"$ARCHIVED_DIR"/t${tid}_*.md` should quote `${tid}`). Cosmetic; not exercised by current code paths.

- **Resolves t694:** Folded in. PID liveness gives a sharp binary signal — no time threshold, no `project_config.yaml` / `userconfig.yaml` key required. Investigation question becomes moot.

- **Backfill ran live:** 6 Implementing tasks (t713_2, t717_2, t718_1, t719_1, t721, t723) had pre-anchor locks. All 6 now have `pid: 0` sentinel + `pid_starttime: -`. Next `/aitask-pick` of any of them will fire `RECLAIM_CRASH:` and route through the new procedure. t723's own lock was also rewritten — natural consequence of being acquired before this code shipped; will self-heal on next lock refresh inside this session or any future re-claim.
