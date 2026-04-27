---
Task: t662_aitask_brainstorm_delete_leaves_stale_branch.md
Base branch: main
plan_verified: []
---

## Context

`ait brainstorm delete <N>` does not actually delete the `crew-brainstorm-<N>` git branch when a stale worktree registration exists from a prior aborted init. The Python `delete_session` does `shutil.rmtree` of the worktree directory but does not clear the registration in `.git/worktrees/`, so git still sees the branch as "checked out at <stale path>" and refuses `git branch -D`. Because the failure is silenced by `2>/dev/null || true`, the orphan branch is left behind without any user-visible error, then re-trips the InitFailureModal added in t660.

The right fix is to never leave the branch behind in the first place. The Python TUI cleanup added in t660 (`brainstorm_app.py:3417-3467`) already establishes the correct pattern — `git worktree prune` first, then `git branch -D` — and we mirror it in the bash fallback.

## Files to modify

- `.aitask-scripts/aitask_brainstorm_delete.sh` (lines 101-117) — reorder operations, surface real failures, emit a one-line note when cleanup actually removes a branch.
- `tests/test_brainstorm_cli.sh` — add a regression test that exercises the stale-worktree-registration scenario.

## Reference (correct pattern, already in repo)

`.aitask-scripts/brainstorm/brainstorm_app.py:3417-3467` — `_cleanup_stale_crew_branch_and_retry()`:
- Runs `git worktree prune` first.
- Then `git branch -D <crew_branch>`, treating non-zero exit as a real failure.
- `git push origin --delete` is best-effort and never fails the cleanup.

## Implementation

### 1. Fix `aitask_brainstorm_delete.sh`

Replace the `NOT_FOUND:*|NOT_TERMINAL:*` arm of the `case` block (lines 105-112) with:

```bash
NOT_FOUND:*|NOT_TERMINAL:*)
    # Prune first — a stale worktree registration in .git/worktrees/
    # would otherwise pin "crew-${CREW_ID}" as "checked out elsewhere"
    # and `git branch -D` would refuse.
    git worktree prune 2>/dev/null || true
    if git show-ref --verify --quiet "refs/heads/crew-${CREW_ID}"; then
        if git branch -D "crew-${CREW_ID}" >/dev/null 2>&1; then
            info "Cleaned: stale crew-${CREW_ID} branch removed"
        else
            warn "Failed to delete stale branch crew-${CREW_ID}"
        fi
    fi
    # Best-effort remote cleanup — silent on failure (no remote, no perms,
    # branch never pushed, etc. are all acceptable).
    git push origin --delete "crew-${CREW_ID}" 2>/dev/null || true
    ;;
```

Key changes vs. the current code:
- `git worktree prune` runs first.
- `git show-ref --verify` gates the deletion so we only emit the info line when there actually was a stale branch to remove (avoids noisy output on the happy path).
- `git branch -D` no longer swallows its failure — we redirect output for cleanliness but inspect the exit code and `warn` if it failed for some other reason (e.g. not fully merged into anything reachable, which would be unexpected here).
- `git push origin --delete` stays silent — it's best-effort and remotes commonly don't have the branch.

The order across the broader block is now: `git worktree remove --force` (in `aitask_crew_cleanup.sh`, when applicable) → fallback prune → branch-D → remote push-delete.

### 2. Add regression test in `tests/test_brainstorm_cli.sh`

Insert a new test after Test 9 (existing `brainstorm delete removes session`). The setup must reproduce the actual failure mode: session exists, branch exists, but worktree directory is gone with the registration still present.

```bash
# --- Test 9b: brainstorm delete cleans up stale crew branch ---
echo "Test 9b: brainstorm delete cleans up stale crew branch"
TMPDIR_T9B="$(setup_test_repo)"
(
    cd "$TMPDIR_T9B"
    bash .aitask-scripts/aitask_brainstorm_init.sh 998 >/dev/null 2>&1

    # Synthesize the stale state: create a worktree on the crew branch,
    # then rmtree the directory without unregistering it. This mirrors
    # what `delete_session` does on a partial init.
    mkdir -p .agentcrews
    git worktree add .agentcrews/stale-crew-brainstorm-998 -b crew-brainstorm-998 >/dev/null 2>&1
    rm -rf .agentcrews/stale-crew-brainstorm-998

    # Sanity: the branch should be present before delete.
    if git show-ref --verify --quiet "refs/heads/crew-brainstorm-998"; then
        _inc_pass
    else
        _inc_fail
        echo "FAIL: stale branch setup did not create crew-brainstorm-998"
    fi

    output=$(bash .aitask-scripts/aitask_brainstorm_delete.sh 998 --yes 2>&1)
    assert_contains "delete outputs DELETED" "DELETED:998" "$output"
    assert_contains "delete reports cleanup" "Cleaned: stale crew-brainstorm-998 branch removed" "$output"

    # Branch should be gone after delete.
    if git show-ref --verify --quiet "refs/heads/crew-brainstorm-998"; then
        _inc_fail
        echo "FAIL: crew-brainstorm-998 branch still present after delete"
    else
        _inc_pass
    fi

    # `git worktree list` should not reference the stale path.
    wt_list=$(git worktree list 2>&1)
    if echo "$wt_list" | grep -q "stale-crew-brainstorm-998"; then
        _inc_fail
        echo "FAIL: stale worktree registration still in 'git worktree list'"
    else
        _inc_pass
    fi
)
cleanup_test_repo "$TMPDIR_T9B"
```

Notes:
- The test uses task number `998` to avoid colliding with Test 9's `999`.
- It does NOT depend on `aitask_brainstorm_init.sh` creating a worktree itself; the worktree is created and broken explicitly so the regression target is unambiguous.
- The `info "Cleaned: …"` message uses ANSI color codes from `terminal_compat.sh`. `assert_contains` uses `grep -qi` (case-insensitive substring), and the `Cleaned: stale …` substring is plain text — color escapes wrap the whole line and don't appear inside the substring being matched, so the assertion is stable.

## Verification

1. **Run the brainstorm CLI test suite:**
   ```bash
   bash tests/test_brainstorm_cli.sh
   ```
   New Test 9b must pass; Tests 9 and 10 (existing delete coverage) must continue to pass.

2. **Lint the modified script:**
   ```bash
   shellcheck .aitask-scripts/aitask_brainstorm_delete.sh
   ```

3. **Manual repro (the original t660 reproduction):**
   - `ait brainstorm <N>` → "Initialize Blank" → wait for crew creation
   - Cancel/abort somewhere mid-session
   - `ait brainstorm delete <N>` → should print `Cleaned: stale crew-brainstorm-<N> branch removed`
   - `git branch --list 'crew-brainstorm-<N>'` → empty
   - `git worktree list` → no stale entry for the deleted session
   - Re-run `ait brainstorm <N>` → InitSessionModal should appear (no fall-through to InitFailureModal)

## Step 9: Post-Implementation

Standard post-implementation flow per `task-workflow/SKILL.md` — no separate worktree (profile `fast` set `create_worktree: false`), so:
- Step 8: user review → commit code (`bug: …(t662)`) and plan file separately.
- Step 9: archive task via `aitask_archive.sh 662`, push.
