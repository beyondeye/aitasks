---
Task: t692_pick_warn_when_reclaiming_self_locked_task_across_pcs.md
Base branch: main
plan_verified: []
---

# Implementation Plan — t692 Pick warn when reclaiming self-locked task across PCs

## Context

**Bug.** Running `/aitask-pick 688` on PC B silently succeeded even though t688 was already locked + in `Implementing` by the same user (`dario-e@beyond-eye.com`) on PC A. Expected: a clear warning + confirmation prompt before reclaiming work that is already in flight on another machine.

**Root cause** (verified by reading the four call sites):

| # | File | Lines | Behavior |
|---|------|-------|----------|
| 1 | `.aitask-scripts/aitask_lock.sh` | 156-163 | Same-email re-lock is a silent "refresh". Hostname stored in lock YAML (line 171) but never compared. |
| 2 | `.aitask-scripts/aitask_pick_own.sh` | 222-232, 305 | `update_task_status` sets `Implementing` unconditionally; never reads prior status. |
| 3 | `.claude/skills/task-workflow/SKILL.md` | 137-164 (Step 4) | Only prompts on `LOCK_FAILED` (different email). Same-email-different-host case never trips a prompt. |
| 4 | `.claude/skills/task-workflow/SKILL.md` | 228-245 (Step 7 guard) | `status==Implementing && assigned_to==me` → "ownership already acquired, proceed normally". Designed for plan-mode deferral; *masks* multi-PC reclaim. |

The primary signal is the **lock YAML on `aitask-locks` branch** (artifact-of-truth: `locked_by` + `hostname` + `locked_at`). Status fields in the task file are a secondary signal for the rare "lock missing but status stuck in Implementing" anomaly.

**Outcome.** When PC B picks a task whose lock holder matches their email but `hostname` differs (or `locked_at` is older than a threshold), surface an `AskUserQuestion` describing the prior session and offering "Reclaim and continue" / "Pick a different task". Same when the task file says `Implementing` + `assigned_to == me` but no current lock matches this host (belt-and-suspenders).

## Design

Four-layer fix. Layers 1+3 are the primary path; Layers 2+4 close edge gaps.

### Layer 1 — `.aitask-scripts/aitask_lock.sh` (`lock_task`, lines 108-204)

Where today the same-email branch is silently accepted (`debug "Lock already held by same user, refreshing"`), emit a structured signal **before** falling through to the refresh-and-push path. Compare against `get_hostname()` (line 72-74); only trigger when the hostname differs (or `locked_at` is older than a threshold — see Open Question Q1).

**New structured stdout line** (printed once before the existing success messaging):
```
LOCK_RECLAIM:<prev_hostname>|<prev_locked_at>|<current_hostname>
```

Refresh proceeds as today (do not `die`). Same-host same-email re-locks remain fully silent (idempotent same-PC re-pick is a legal no-op).

Implementation sketch (replaces current lines 156-163):
```bash
if [[ "$locked_by" == "$email" ]]; then
    debug "Lock already held by same user, refreshing"
    local current_hostname
    current_hostname=$(get_hostname)
    if [[ -n "$locked_hostname" && "$locked_hostname" != "unknown" \
          && "$locked_hostname" != "$current_hostname" ]]; then
        echo "LOCK_RECLAIM:${locked_hostname}|${locked_at}|${current_hostname}"
    fi
else
    echo "LOCK_HOLDER:${locked_by}|${locked_at}|${locked_hostname}"
    die "Task t$task_id is already locked by $locked_by (since $locked_at, hostname: $locked_hostname)"
fi
```

### Layer 2 — `.aitask-scripts/aitask_pick_own.sh` (`main`, lines 252-312)

Two changes:

**a) Surface the `LOCK_RECLAIM:` signal.** `acquire_lock` (lines 154-190) currently captures `lock_output` from `aitask_lock.sh` but only inspects it on failure (case 1). Extend the success path to grep `lock_output` for `LOCK_RECLAIM:` and re-print the line on stdout so `aitask_pick_own.sh`'s caller (task-workflow Step 4) can see it.

Smallest change: add after the `[[ $lock_exit -eq 0 ]] && return 0` line:
```bash
if [[ $lock_exit -eq 0 ]]; then
    echo "$lock_output" | grep '^LOCK_RECLAIM:' || true
    return 0
fi
```

**b) Pre-claim status check (belt-and-suspenders).** Right after the email is resolved (after line 276, before `store_email`), read the task file's current `status` and `assigned_to`. If status is `Implementing` AND `assigned_to == "$EMAIL"`, capture this as `prev_status` / `prev_assigned`. Then, after the `OWNED:$TASK_ID` line, emit:
```
RECLAIM_STATUS:<prev_status>|<prev_assigned_to>
```
This catches the rare "lock missing but task status still Implementing" anomaly that Layer 1 cannot see. The signal is *additive*; it does not replace `OWNED:`.

**Why both signals?** Layer 1's `LOCK_RECLAIM:` is artifact-of-truth (lock YAML on the dedicated branch). Layer 2's `RECLAIM_STATUS:` is a secondary check off the task file. Step 4 will surface a prompt if either is present. In the common case (lock still held), both fire and Step 4 deduplicates by surfacing one prompt.

**Output examples:**
- Common multi-PC reclaim (lock held): two extra lines + `OWNED:692`.
- Lock cleaned but status stuck: only `RECLAIM_STATUS:` + `OWNED:692`.
- Same-PC re-pick (no change): only `OWNED:692` (silent, as today).

### Layer 3 — `.claude/skills/task-workflow/SKILL.md` Step 4 (lines 137-164)

Add a new branch to the output-parsing list, between `OWNED:` and `LOCK_FAILED:`:

> - **`LOCK_RECLAIM:<prev_hostname>|<prev_locked_at>|<current_hostname>` and/or `RECLAIM_STATUS:<prev_status>|<prev_assigned_to>`** (either or both, in addition to `OWNED:`) — Task was already in `Implementing` claimed by you on a different machine. Use `AskUserQuestion`:
>   - Question: "Task t\<N\> is already in `Implementing`, claimed by you on `<prev_hostname>` since `<prev_locked_at>` (current host: `<current_hostname>`). Reclaim and continue here?"
>   - Header: "Reclaim"
>   - Options:
>     - "Reclaim and continue" — proceed to Step 5 (the lock has already been refreshed to this host by `aitask_lock.sh`; the `OWNED:` line confirms it).
>     - "Pick a different task" — release the lock here (so PC A can resume), revert the task to `previous_status` (`Ready`), and return to the calling skill's task selection (Step 1 of pick).
>
> If only `RECLAIM_STATUS:` was emitted (no `LOCK_RECLAIM:`), present the same prompt with the hostname/timestamp omitted: "Task t\<N\> shows status `Implementing` already assigned to you, but no active lock holds it. Reclaim and continue here?"

When the user selects "Pick a different task":
- Release the lock: `./.aitask-scripts/aitask_lock.sh --unlock <task_num> 2>/dev/null || true`
- Revert status: `./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""`
- Commit: `./ait git add aitasks/ && ./ait git commit -m "ait: Revert t<N> to Ready (reclaim declined)" && ./ait git push`

This conforms to the existing `LOCK_FAILED:` branch pattern (lines 140-151).

### Layer 4 — `.claude/skills/task-workflow/SKILL.md` Step 7 guard (lines 228-245)

Tighten the same-user fast-path to also compare hostname. Today:

> If status is `Implementing` AND `assigned_to` matches the current user's email: Ownership was already acquired in Step 4. Proceed normally.

New wording:

> If status is `Implementing` AND `assigned_to` matches the current user's email: Read the active lock holder via `./.aitask-scripts/aitask_lock.sh --check <task_id>` and compare its `hostname:` field against `hostname` (running shell). If they match — ownership was already acquired in Step 4 on this host. Proceed normally. If they differ (or `--check` returns no lock at all), surface the same `AskUserQuestion` as Step 4's `LOCK_RECLAIM:` branch and follow the user's choice.

This closes the plan-mode-deferred-Step-4 corner case. Cheap (one extra `--check` call) and only fires when the existing fast-path would otherwise mask a reclaim.

## Files to modify

| File | Change |
|------|--------|
| `.aitask-scripts/aitask_lock.sh` | Lines 156-163: emit `LOCK_RECLAIM:` on same-email-different-host. |
| `.aitask-scripts/aitask_pick_own.sh` | `acquire_lock` (~line 167): forward `LOCK_RECLAIM:` from inner output. `main` (~line 277): pre-claim status read + `RECLAIM_STATUS:` emission. |
| `.claude/skills/task-workflow/SKILL.md` | Step 4: new parsing branch for `LOCK_RECLAIM:` / `RECLAIM_STATUS:`. Step 7 guard: hostname check before the silent fast-path. |
| `tests/test_lock_reclaim.sh` (new) | See Verification below. |

**No changes needed** to `aitask_update.sh`, `aitask_lock_diag.sh`, board TUI, or other skills (`aitask-pickrem`, `aitask-pickweb`). Web/remote pickers run on disposable single-use environments where multi-PC reclaim doesn't apply.

## Verification

### Manual reproduction (post-implementation)
1. On PC A, run `/aitask-pick <N>` and stop after status flips to `Implementing` (e.g., abort during plan mode).
2. From PC B (same user/email), run `/aitask-pick <N>`.
3. Confirm: an `AskUserQuestion` appears with the message format from Layer 3, showing PC A's hostname and `locked_at`, offering "Reclaim and continue" / "Pick a different task".
4. Choose "Pick a different task" → confirm task reverts to `Ready`, lock is released, and the picker returns to its label/task-selection step.
5. Choose "Reclaim and continue" → confirm the lock YAML on `aitask-locks` now records PC B's `hostname:`, status remains `Implementing`, workflow continues into Step 5.

### Automated test — `tests/test_lock_reclaim.sh`

Model on `tests/test_lock_force.sh` (the closest analog — paired-repo helper, mocked `pick_own.sh` invocations).

**Test 1 — `LOCK_RECLAIM:` emitted on same-email-different-host re-lock at the lock-script level:**
- `setup_paired_repos` (bare remote + two local clones).
- Local 1: lock t1 as `alice@test.com`. Manually edit the lock YAML on the locks branch to set `hostname: pc-A` (since real hostname is whatever the test runner has — controlling it makes the assertion deterministic). Push.
- Local 2: with `HOSTNAME` env var or by stubbing `get_hostname` (e.g., `hostname` returning `pc-B`), run `aitask_lock.sh --lock 1 --email alice@test.com`. Capture stdout.
- Assert exit 0, assert stdout contains `LOCK_RECLAIM:pc-A|`, assert stdout contains `|pc-B`.
- Verify the lock YAML on the remote has been refreshed (new `hostname: pc-B`).

**Test 2 — Same-host same-email re-lock stays silent (no LOCK_RECLAIM):**
- Lock t1 as alice from local1. Re-lock t1 as alice from local1.
- Assert no `LOCK_RECLAIM:` in stdout.

**Test 3 — `RECLAIM_STATUS:` emitted by `pick_own.sh` when task already in Implementing:**
- Set up task file with `status: Implementing` + `assigned_to: alice@test.com`.
- No lock present (simulate "lock cleaned but status stuck" anomaly).
- Run `aitask_pick_own.sh 1 --email alice@test.com`.
- Assert stdout contains `RECLAIM_STATUS:Implementing|alice@test.com`, also contains `OWNED:1`.

**Test 4 — Forwarding works through `pick_own.sh`:**
- Same setup as Test 1, but invoke through `aitask_pick_own.sh`.
- Assert stdout contains both `LOCK_RECLAIM:` and `OWNED:`.

**Test 5 — Syntax check:** `bash -n` for both scripts.

`get_hostname` in `aitask_lock.sh` shells out to `hostname`. Tests can override by exporting `HOSTNAME` and using a wrapper, or by patching the script copy in the test fixture (the test helpers already `cp` the scripts into the scratch dir — easy to `sed` `hostname` → `echo "$TEST_HOSTNAME"` after copy).

### Existing tests — keep passing
- `tests/test_task_lock.sh` Test 9 (line 232): "Same email re-lock succeeds (refresh)" — currently asserts exit 0. Still passes (`LOCK_RECLAIM:` is on stdout, not stderr; exit code unchanged).
- `tests/test_lock_force.sh` Tests 1-5 — unchanged; force-unlock path is on a different branch (different email).

## Resolved scope decisions

**Same-host stale-lock UX is out of scope** for this task (user-confirmed: "different-host only, for same-host create followup investigation task"). Layer 1's hostname comparison is the only trigger; no `locked_at` threshold logic in this PR.

**Follow-up task to create during this implementation** (before Step 9 archival): a standalone investigation task — `t<N>_investigate_same_host_stale_lock_warning_ux.md`, priority `low`, effort `low`, issue_type `chore`, labels `aitask_pick,task_workflow`. Body: "Investigate whether same-host stale locks (e.g. user started a task in the morning, returned after lunch) warrant a warning analogous to t692's multi-PC reclaim prompt. Define need/scope/threshold/UX before implementation. Consider: typical session lengths, hostname-tracking edge cases (Docker/SSH renames), interaction with `--cleanup`."

Creation command (issued during Step 8, before code commit, so the task ID is allocated and committed independently — it does NOT participate in the t692 fold/archive flow):
```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name "investigate_same_host_stale_lock_warning_ux" \
  --priority low --effort low --type chore \
  --labels "aitask_pick,task_workflow" \
  --desc-file - <<'EOF'
... investigation brief as above ...
EOF
```

**Q (lock release on "Pick a different task").** When the user picks "Pick a different task", we *unlock* (not *force-unlock*). `aitask_lock.sh --unlock` doesn't check ownership — it just removes the lock file. So plain `--unlock` works since we (PC B) just refreshed the lock to ourselves at the `LOCK_RECLAIM:` step. PC A's previous lock state was already overwritten by Layer 1 — declining the reclaim must release the lock so PC A (or anyone else) can later resume cleanly.

## Out of scope
- Stale-lock auto-expiry (time-based expiry of live locks is a separate concern; `--cleanup` only handles archived tasks).
- Cross-user lock takeover UX (already handled by `LOCK_FAILED` + force-unlock prompt).
- Brainstorm/board TUI parallel paths — those use the same `aitask_lock.sh` so they get the new signal for free, but surfacing a prompt in the TUI is a separate UX concern.

## Step 9 reference

Standard Step 9 cleanup applies (no worktree to remove since we're on the current branch). Code commit follows the `bug:` prefix per the issue_type. Plan file commit uses the `ait:` prefix.

## Final Implementation Notes

- **Actual work done:** All four layers landed exactly as designed.
  - Layer 1 (`aitask_lock.sh:156-169`): added 11-line block inside the existing same-email branch that calls `get_hostname()` and emits `LOCK_RECLAIM:<prev_hostname>|<prev_locked_at>|<current_hostname>` only when `locked_hostname` is non-empty, not "unknown", and differs from current. Refresh-and-push path unchanged.
  - Layer 2a (`aitask_pick_own.sh:166-172`): `acquire_lock` now greps the captured `lock_output` for `^LOCK_RECLAIM:` and re-prints to stdout on the success path before returning 0.
  - Layer 2b (`aitask_pick_own.sh:269-292, 329-336`): refactored `task_file=$(resolve_task_file ...)` to run unconditionally before email resolution; captured `prev_status` / `prev_assigned` from the file; emit `RECLAIM_STATUS:<prev_status>|<prev_assigned>` after `OWNED:` only when prev_status==Implementing and prev_assigned matches current EMAIL.
  - Layer 3 (`task-workflow/SKILL.md` Step 4): added a new parsing branch between `FORCE_UNLOCKED` and `LOCK_FAILED` that handles either or both signals, with two question variants (with-hostname / without-hostname) and a "Pick a different task" branch that unlocks + reverts status to Ready + commits + pushes.
  - Layer 4 (`task-workflow/SKILL.md` Step 7 guard): the same-user fast-path now runs `aitask_lock.sh --check <task_id>`, parses `hostname:`, and only treats the existing ownership as confirmed when the host matches (or no lock exists). Hostname mismatch routes to the same prompt as Step 4's `LOCK_RECLAIM:` branch.
- **Deviations from plan:** None. The plan's design held up; no surprises during implementation.
- **Issues encountered:** Pre-existing unstaged edits in `brainstorm_app.py`, `agent_command_screen.py`, `section_viewer.py` from other in-flight tasks (t690/t688/etc.) — kept out of the t692 commit by staging only the four modified files explicitly.
- **Key decisions:**
  - Hostname comparison is the **primary** signal (artifact-of-truth: lock YAML on the dedicated branch). Status check is the **secondary** signal — runs in `aitask_pick_own.sh`, not `aitask_lock.sh`, so it stays out of the lock-script's hot path.
  - Same-host stale-lock UX explicitly deferred to a follow-up investigation task (per user direction during planning) — see "Resolved scope decisions" above.
  - "Pick a different task" uses plain `--unlock` (not `--force-unlock`): `aitask_lock.sh --unlock` is ownership-agnostic and PC B holds the refreshed lock at this point, so the regular path works.
  - Test hostname stubbing: created a `bin/hostname` shim in the scratch repo that reads `TEST_HOSTNAME` from the environment, then `PATH="$tmp/bin:$PATH"` to override per-invocation. Cleaner than sed-patching the lock script.
- **Upstream defects identified:** None.
- **Tests:** New `tests/test_lock_reclaim.sh` (20 assertions, all pass) covering: same-host silence, different-host LOCK_RECLAIM emission, lock YAML refresh, pick_own forwarding, RECLAIM_STATUS for stuck-status anomaly, fresh-pick silence, syntax. Existing `test_task_lock.sh` (37/37) and `test_lock_force.sh` (16/16) continue to pass — Test 9 of the former specifically validates that same-email re-lock still exits 0 (LOCK_RECLAIM is on stdout but doesn't change the exit code).
