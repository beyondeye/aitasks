---
Task: t1077_fix_id_counter_fetch_failure_diagnostics.md
Base branch: main
plan_verified: []
---

# t1077 — Fix misleading ID-counter fetch-failure diagnostics

## Context

`ait create --batch --commit` can fail to create a parent task with a
misleading atomic-ID error **even when the `aitask-ids` counter branch is
healthy**. Observed live: 5× `Pushed local counter branch to remote
(auto-upgrade)` followed by `Failed to claim task ID after 5 attempts` and a
spurious `Run 'ait setup'`.

**Root cause:** in `aitask_claim_id.sh::claim_next_id()`, the fetch is
`git fetch origin "$BRANCH" --quiet 2>/dev/null` — stderr is discarded and
**any** non-zero exit is treated as "remote branch is missing". When `git
fetch` fails for an *environmental* reason (e.g. an unwritable
`.git/FETCH_HEAD`, network, auth), the code wrongly enters the auto-upgrade
loop: `try_push_local_to_remote` pushes the already-present branch (a no-op
that still prints the "auto-upgrade" line), retries 5×, then dies with a
generic message. `aitask_create.sh` then appends `Run 'ait setup'` to *every*
claim failure, pointing the user at the wrong fix.

**Goal:** the claim path must distinguish *remote branch genuinely absent*
(legit auto-upgrade) from *fetch failed for a real reason* (surface verbatim,
no auto-upgrade, no setup hint), and `aitask_create.sh` must relay the
lower-level error verbatim instead of always blaming setup.

**Scope note:** this is the *diagnostics/messaging* fix only. The
counter-drift / duplicate-ID correctness invariant is **t1079** (same file,
different bug) and is explicitly out of scope here. Changes are kept coherent
with t1079 (both touch `claim_next_id()` / `claim_local`), but no self-heal or
`--resync` is added.

## Files to modify

- `.aitask-scripts/aitask_claim_id.sh` — core fix
- `.aitask-scripts/aitask_create.sh` — relay claim errors verbatim (2 sites)
- `tests/test_claim_id.sh` — regression tests

## Implementation

### 1. `aitask_claim_id.sh` — new helper `remote_branch_state`

Add after `require_remote()` (≈line 55). Echoes one of `PRESENT` / `ABSENT` /
`ERROR:<msg>`. Crucially, `git ls-remote` queries refs **without** writing
`.git/FETCH_HEAD`, so it succeeds (→ `PRESENT`) in exactly the scenario where
`git fetch` fails on a FETCH_HEAD write — that is what disambiguates the bug.

```bash
# Query origin for the counter branch without writing FETCH_HEAD.
# Echoes: PRESENT | ABSENT | ERROR:<message>
remote_branch_state() {
    local ls_out
    if ls_out=$(git ls-remote --heads origin "$BRANCH" 2>&1); then
        if printf '%s' "$ls_out" | grep -q "refs/heads/$BRANCH"; then
            echo "PRESENT"
        else
            echo "ABSENT"
        fi
    else
        echo "ERROR:$(printf '%s' "$ls_out" | tr '\n' ' ')"
    fi
}
```

(The `if ls_out=$(...)` form neutralizes `set -e` on a non-zero `ls-remote`;
verified.)

### 2. `aitask_claim_id.sh` — restructure the Step 1 fetch in `claim_next_id()`

Replace the current fetch block (≈lines 180-189) with stderr capture, an
explicit refspec (reliably updates `origin/$BRANCH` across git versions), and
state-based branching:

```bash
        # Step 1: Fetch latest counter. Capture stderr (don't discard it) and
        # use an explicit refspec so origin/$BRANCH is reliably updated.
        debug "Fetching branch '$BRANCH' from origin..."
        local fetch_err
        if ! fetch_err=$(git fetch origin \
            "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" --quiet 2>&1 >/dev/null); then
            # Fetch failed. Only a genuinely-absent remote branch may trigger
            # auto-upgrade / suggest 'ait setup'. A real fetch/env error
            # (network, auth, unwritable .git/FETCH_HEAD) is surfaced verbatim.
            local rstate
            rstate=$(remote_branch_state)
            case "$rstate" in
                PRESENT)
                    die "Failed to fetch counter branch '$BRANCH' from origin: ${fetch_err:-unknown git fetch error}"
                    ;;
                ERROR:*)
                    die "Cannot reach origin to verify counter branch '$BRANCH': ${rstate#ERROR:}"
                    ;;
                *)  # ABSENT — remote branch missing; auto-upgrade from local.
                    if try_push_local_to_remote; then
                        continue
                    fi
                    die "Counter branch '$BRANCH' is not initialized on origin and no local branch exists to upgrade. Run 'ait setup' to initialize the counter."
                    ;;
            esac
        fi
        debug "Fetch successful"
```

Only the `ABSENT` message mentions `ait setup`; `PRESENT`/`ERROR` do not.

### 3. `aitask_claim_id.sh` — quiet the no-op push in `try_push_local_to_remote`

Capture push output; only print the "auto-upgrade" line when the push actually
created/advanced the remote branch (defense-in-depth against the misleading
line; ≈lines 148-160):

```bash
try_push_local_to_remote() {
    if has_local_branch; then
        debug "Attempting to push local '$BRANCH' to remote (auto-upgrade)..."
        local push_out
        if push_out=$(git push origin "$BRANCH:refs/heads/$BRANCH" 2>&1); then
            if ! printf '%s' "$push_out" | grep -qi "up-to-date"; then
                info "Pushed local counter branch to remote (auto-upgrade)" >&2
            fi
            git fetch origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" --quiet 2>/dev/null || true
            return 0
        fi
        debug "Push of local branch failed: $push_out"
    fi
    return 1
}
```

### 4. `aitask_create.sh` — relay claim errors verbatim (stop always blaming setup)

claim_id.sh now owns the setup hint (only in the uninitialized message), so
create.sh just preserves the lower-level error verbatim:

- Batch finalize (≈line 1989):
  `die "Atomic ID counter failed: ${claim_err:-unknown error}. Run 'ait setup' to initialize the counter."`
  → `die "Atomic ID counter failed: ${claim_err:-unknown error}"`
- Interactive finalize hard-fail (≈line 792): same edit.
- Interactive decline-fallback (≈line 788):
  `die "Aborted. Fix the remote counter or run 'ait setup'."`
  → `die "Aborted. See the counter error above."`
  (the verbatim error was already `warn`ed at ≈line 779; when truly
  uninitialized it already includes the setup hint).

### 5. `tests/test_claim_id.sh` — regression tests

Append two tests using a PATH-shadowing `git` shim that fails `git fetch` but
passes everything else (incl. `ls-remote`) through to real git — validated in a
scratch repo.

- **Test 15 — fetch fails, branch present:** init counter, then claim with the
  shim. Assert: non-zero exit (`assert_exit_nonzero_rc` on captured rc);
  output contains the real fetch error (`FETCH_HEAD`); output does **not**
  contain `auto-upgrade`; output does **not** contain `5 attempts`. This is the
  AC-required regression (no auto-upgrade loop on a real fetch failure).
- **Test 16 — remote unreachable (ls-remote also fails):** shim fails both
  `fetch` and `ls-remote`. Assert non-zero exit and the `Cannot reach origin`
  message (no auto-upgrade, no setup hint).

Existing tests 1-14 must still pass (auto-upgrade Test 14, race Test 6,
no-remote Test 7 unchanged by design).

## Risk

### Code-health risk: medium
- Touches `claim_next_id()`, the load-bearing path for every parent-task ID claim; the success path also switches to an explicit fetch refspec · severity: medium · → mitigation: covered by existing tests 1-14 + new tests 15-16 (in-scope, no separate task)

### Goal-achievement risk: low
- Root-cause-directed and all 5 ACs covered; test approach experimentally validated · severity: low · → mitigation: None

## Verification

1. `bash tests/test_claim_id.sh` → all tests pass (1-16).
2. `bash -n .aitask-scripts/aitask_claim_id.sh && bash -n .aitask-scripts/aitask_create.sh`.
3. `shellcheck .aitask-scripts/aitask_claim_id.sh .aitask-scripts/aitask_create.sh`.
4. Regression sweep of create-path tests that call claim_id transitively:
   `bash tests/test_draft_finalize.sh`, `bash tests/test_file_references.sh`.

See **Step 9 (Post-Implementation)** for cleanup, build/verify gates,
archival, and merge.
