---
Task: t1725_3_sweep_per_file_deferral_record_tree_state_gate_and_wire.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_4_resolve_holder_pane_and_prompt_state.md, aitasks/t1725/t1725_5_syncer_and_board_deferral_screen_with_commit_on_behalf.md, aitasks/t1725/t1725_6_document_actionable_sync_deferrals.md, aitasks/t1725/t1725_7_manual_verification_sync_deferrals_actionable_and_safe_to_co.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_1_abort_conflicted_pull_rebase_in_task_utils.md, aiplans/archived/p1725/p1725_2_refuse_task_data_writes_on_wedged_worktree_and_create_id_bur.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-09 16:00
---

# t1725_3 — per-file deferral record, tree-state rebase gate, wire + parser, `--commit-for-task`

## Context

`ait syncer` currently tells a user only `Sync deferred: protected_dirty (1 file(s)
held by other sessions)`. The shell already knows which file, which task, who holds
it and what would clear it — `aitask_sync.sh` builds a prescriptive line per file in
`SKIP_REPORT` — but that report goes to **stderr** while stdout carries one lossy
roll-up token, so nothing reaches the TUI. On 2026-09-07 a single deferral of this
shape cost a full session of manual forensics.

Two further defects compound it: "held by other sessions" is simply **wrong** when
the holder is the user's own parked pane (all 13 locks on the branch belonged to
this user), and an **untracked** file needlessly defers the whole rebase even though
`git rebase` ignores an untracked path unless an incoming commit creates it.

This task makes the deferral a **complete per-file record on the wire** and makes the
rebase gate **tree-state aware**, so cases where nothing actually blocks the rebase
stop deferring. It is child 3 of t1725; `aiplans/p1725_…md` section "Child 3" is the
authoritative contract. t1725_4 (pane + prompt state) and t1725_5 (TUI screen) build
on the record defined here. It also implements the sync-side half that t1696
suggested — the fast-forward when `local_ahead == 0`.

**Explicit non-goal (inherited from the parent):** this does not promise a sync can
never be deferred while live sessions hold files. Deferring on another live session's
modified file stays correct (t1599_3). What changes is that the user can see why, who
and what to do — and that non-blocking cases stop deferring.

## Verification pass (2026-09-09) — what changed under this plan

The plan was written against a tree that has since moved, and three inbox notes said
so. Verified against `21ad464fe`:

- **t1727's note is accurate.** `aitask_sync.sh` is 1202 lines and every line number
  in that note matches. All numbers in the previous plan draft were ~125 lines stale;
  `task_utils.sh` moved further still (`get_user_email` is **2145**, not 1533/1985;
  `task_data_converge` is **1554**, not 943).
- **`do_push`'s gate has no `remote_ahead` term.** Both plans claimed `_rebase_blocked`
  replaces "both `(( ${#PROTECTED_DIRTY[@]} )) && remote_ahead > 0` sites". Only
  `main:1153` has that shape. `do_push:1060` is `(( ${#PROTECTED_DIRTY[@]} ))` alone
  and fires *before* the retry fetch.
- **The specified `_rebase_blocked` would break Test 3.** Its three conditions never
  mention `remote_ahead`; Test 3 is tracked-dirty + `local_ahead=1` + `remote_ahead=0`,
  which trips "tracked && local_ahead > 0" and would defer — the exact asymmetry Test 3
  exists to forbid. **The predicate must short-circuit to "not blocked" when
  `remote_ahead == 0`** (there is no rebase to block).
- **Test 1 cannot be preserved as written** — it *is* the scenario the fast-forward
  fixes (tracked dirty, `local_ahead=0`, `remote_ahead=1`, incoming touches only
  `t30_gamma.md`). Under the new gate it fast-forwards and reports `PULLED`. Per user
  decision it gains a local commit so `local_ahead=1`, which re-blocks it and keeps the
  original regression pinned in its still-true form.
- **`DEFERRED_FILE:` contains the substring `DEFERRED`.** Tests 2, 3, 6 and 20 assert
  `assert_not_contains "DEFERRED"` against whole stdout, so the continuation lines must
  be emitted **only** alongside the status line, never merely because records exist.
- **`${#PROTECTED_DIRTY[@]}` counts skip *events*, not files** — one `live_lock` event
  covers all of a task's paths. Per-path records change what the status line's "N" means.
- `_lock_snapshot:425` does discard `lemail` (`: "$lemail"`), as claimed.
- **t1725_4's probe does not exist** (`ait_tmux_pane_for_pid`, `lib/pane_state_probe.py`
  are absent), so `--require-waiting` is reachable only in its fail-closed direction here.
- `tests/test_sync_protect_paths.sh` does not exist yet; `tests/test_sync_auto_commit_scoping.sh` does (276 lines).
- `sync_fixture.sh` has **no** userconfig-email helper; lock YAMLs hard-code
  `locked_by: other@x.com`. The `self` / `other` / `unverified` wire rows need one.

Three further defects were raised in plan review and confirmed against the source.
All three are **fail-open** — each makes the gate or the parser conclude "safe" on
input it did not actually understand:

- **`INCOMING` must be NUL-safe.** The draft used `$(task_git diff --name-only …)`
  while the sweep's paths come from `status --porcelain -z` (line 558) raw and
  unquoted. Two independent failures: a newline path is line-split, and git C-quotes
  unusual paths by default, so neither form compares equal. `$( )` also eats NUL —
  which is exactly why the dirty scan already writes to a file (comment at 552-554).
  Fixed in step 10.
- **The retry fetch's failure is swallowed.** Line 1068 is literally
  `_git_with_timeout fetch origin 2>/dev/null || true`. Recomputing the gate on a
  stale `@{u}` can read `remote_ahead=0` and report "not blocked" over unseen
  incoming changes. Fixed in step 13.
- **CR is not the only line boundary, and `%0D` alone is an incomplete fix.** Python's
  `str.splitlines()` breaks on **nine** characters beyond LF — CR, VT, FF, FS, GS, RS,
  NEL and (after UTF-8 decoding) U+2028 / U+2029 — every one a legal git-path byte.
  Verified this session: `'a\x0bb'.splitlines()` → `['a','b']`, while
  `'a\x0bb'.split('\n')` → `['a\x0bb']`. Fixed in step 18 by adding `%0D` **and**
  splitting on `"\n"`, so the guarantee rests on one verifiable rule rather than on
  enumerating a CPython implementation detail.

A second review round raised two more, both confirmed:

- **The runner cannot decode a non-UTF-8 path.** `run_sync_batch` uses
  `subprocess.run(..., text=True)` — locale codec, `errors="strict"`. Verified: a raw
  `0xFF` raises `UnicodeDecodeError` *inside* `subprocess.run`, and the `except` clauses
  cover only `TimeoutExpired` / `FileNotFoundError`, so it escapes `run_sync_batch` and
  crashes the syncer and board actions. Latent today via captured stderr; this task puts
  paths on stdout and makes it a main-path failure. Fixed in step 24 with
  `encoding="utf-8", errors="surrogateescape"` (round-trip verified) plus a documented
  convention on `DeferredFile`.
- **The `INCOMING` temp file had no cleanup.** The draft allocated it at call-site scope
  in a script with no `trap`, whose deferral, conflict and network paths all `exit` from
  nested functions — so every affected sync would leak one file. Fixed in step 10 by
  encapsulating allocation, read and `rm -f` in `_load_incoming` with **no exit point
  between them**, which removes the need for a trap rather than adding one.

## Files

| File | Change |
|---|---|
| `.aitask-scripts/aitask_sync.sh` | the whole task: record, classes, gate, wire, flags |
| `.aitask-scripts/lib/sync_action_runner.py` | `DeferredFile`, `SyncResult.deferred_files`, parsing |
| `tests/test_sync_protect_paths.sh` | **new** — the pre-phase forced-path harness |
| `tests/test_sync_rebase_gate.sh` | **new** — the pre-phase gate truth table (incl. hostile paths) |
| `tests/test_sync_deferral_and_quarantine.sh` | Test 1 fixup; AC2, wire, flag and race tests |
| `tests/lib/sync_fixture.sh` | new `set_userconfig_email`; `pre_push` seam support |
| `tests/test_sync_action_runner.py` | continuation parsing, decode round-trips, closed-set scan |

Current anchors in `aitask_sync.sh` (re-derive before editing — this file moves):
header protocol comment `12-29`, `show_help` 75 (protocol block `92-108`), flag parse
`129-138`, `PROTECTED_DIRTY=()` 248, `_note_skip` 254, `_sync_test_seam` 280, `_protect`
289, `_pct_encode` 317, `_pct_decode` 330, `declare -A LOCK_*` 399, `_lock_snapshot` 404,
`_holder_verdict` 434, `_sweep_dirty` 609, `_commit_group` 763, `report_skipped` 866,
`do_fetch` 877, `count_local_ahead` 898, `do_pull_rebase` 909, `do_push` 1027 (gate
1060-1064, bare pull 1074), `main` 1096 (gate comment 1135-1147, gate 1153-1157).

### Pre-phase (risk mitigations)

1. **[characterize_sync_paths_never_empty_stdout]** — *before any restructure.* New
   `tests/test_sync_protect_paths.sh`: scan `_protect\s+"([a-z_]+)"` from the script
   source so a new reason cannot be missed, drive **every** reason through
   `aitask_sync.sh --batch`, and assert stdout is non-empty and starts with a
   recognised token each time. Reachability per reason: planted live lock
   (`live_lock`), `lock_yaml_unknown_pid` (`unknown_liveness`), unreachable origin for
   the lock branch (`locks_unavailable`), a staged path (`staged_elsewhere`), an
   ownerless file (`ownerless`), a cross-task rename (`ambiguous_rename`), the
   `pre_group_commit` seam (`content_changed`), the `pre_commit_phase` seam
   (`lock_acquired_during_scan`), a wedged/unwritable scratch (`scan_failed`), a held
   data-index lock (`lock_contended`). Any reason with no reachable driver is listed
   in an explicit `UNREACHABLE` set in the test with a one-line justification, so the
   scan can never pass vacuously. **Commit green against the current script, then
   restructure.**

2. **[rebase_gate_truth_table]** — *before rewriting the gate.* New
   `tests/test_sync_rebase_gate.sh`. Pin the gate decision as an explicit table rather
   than an emergent property. **Drive it end-to-end through `run_sync` on the real
   fixture, not by sourcing the script** — `aitask_sync.sh` calls `main` on its last
   line, so sourcing it would execute a sync, and adding a `LIB_ONLY` guard to a
   production script purely for a test is the wrong trade. Each cell is a fixture
   shape (tree state × local commits × remote advance × whether the advance touches
   the protected path) asserted on the batch verdict. Assert the verdict for every
   cell of
   `{tracked, untracked, unknown} × {local_ahead 0, >0} × {remote_ahead 0, >0} ×
   {path incoming, not incoming}`. The cells that must read **not blocked** include
   the two this verification pass found: `remote_ahead == 0` with anything (Test 3),
   and `tracked / local_ahead == 0 / remote_ahead > 0 / not incoming` (the t1696
   fast-forward). Run every `incoming` cell **twice** — once with an ordinary path and
   once with a path containing a newline — so the membership test is exercised on the
   input that breaks a line-oriented `INCOMING` (step 10). Written before the rewrite
   so the table is a specification, not a transcript of whatever the new code happens
   to do.

## Steps

### 3a. Per-file record

3. Replace `PROTECTED_DIRTY=()` with parallel arrays `PROT_REASON PROT_TASK PROT_PATH
   PROT_STATE PROT_HOLDER PROT_EMAIL PROT_HOST PROT_PID PROT_PANE PROT_PANE_STATE
   PROT_ACTION`. `PROT_PANE` / `PROT_PANE_STATE` are always empty here (t1725_4 fills
   them). Keep a separate `PROTECTED_COUNT`-style guard only if a call site needs the
   old truthiness; prefer `(( ${#PROT_REASON[@]} ))`.

4. `_protect <reason> <task> <path> <tree_state> <human line>`. Every array is appended
   in lockstep — **one `_protect` body, never per-call-site appends**, so the arrays
   cannot drift in length. `_note_skip` still receives the human line, so
   `report_skipped`'s stderr output is byte-identical for the reasons whose text is
   unchanged.

5. Convert all **16** call sites (12 distinct reasons). They fall into four shapes,
   which is what decides how many records each produces:
   - **per-path, path already in scope** — `ownerless` (660), `ambiguous_rename` (668),
     `unverifiable` (677, 681): one record, real path.
   - **per-task, expand to one record per path of that task** — `locks_unavailable`
     (700), `live_lock` (719), `unknown_liveness` (720), `lock_acquired_during_scan`
     (736). All four sit inside `_sweep_dirty` where `ent_path`/`ent_owner` are in
     scope, so the expansion is a filter over those arrays.
   - **per-group, inside `_commit_group`** — `staged_elsewhere` (774), `unverifiable`
     (784), `content_changed` (790), `commit_failed` (820): iterate the `paths` array
     the function already received.
   - **path-less** — `scan_failed` (546, 561), `lock_contended` (584): empty path,
     `tree_state=unknown`.

6. **Carry the porcelain state.** `_sweep_dirty` parses `xy` per entry but does not
   retain it, so add a third parallel array `ent_state` alongside `ent_path`/`ent_owner`:
   `??` → `untracked`, anything else → `tracked`. A rename's `orig` half is recorded
   `tracked` (git only emits `R` when both halves are staged).

7. `_lock_snapshot` keeps the email: add `LOCK_EMAIL` to the `declare -A` at 399 and to
   the reset at 405, and replace `: "$lemail"` with `LOCK_EMAIL["$lid"]="$lemail"`.

### 3b. Holder classification

8. `_holder_class <tid>` → `self | other | remote | unverified | none`.
   `self` **only** when every identity is present and verified: `LOCK_EMAIL[$tid]`
   non-empty, `get_user_email` non-empty, the two equal, `LOCK_HOST[$tid]` non-empty
   and not `unknown`, `hostname` resolvable and equal to it. Any missing or malformed
   identity → `unverified`, never `self` — **an empty local email must not compare
   equal to an empty lock email.** `other` = same verified host, different non-empty
   email; `remote` = different host; `none` = unlocked.

9. Human line / `PROT_ACTION` per class (this is where "held by other sessions"
   disappears — sweep every occurrence, including the two status lines):
   - **self**: `t<id>: <path> — held by YOUR OWN live session on this host (pid <pid>[, pane <pane>]) — finish or answer that session; or commit on its behalf: ./ait sync --commit-for-task <id>`
   - **other**: `held by <email>'s live session on <host> (pid <pid>) — left for that session`
   - **remote**: `held on <host> (liveness cannot be verified from here) — left for that host`
   - **unverified**: `held by a session whose identity could not be verified (lock email / local userconfig email missing) — left as is`
   - `ownerless` / `ambiguous_rename` / `staged_elsewhere` / … keep their existing
     prescriptive text verbatim.

### 3c. Rebase gate

10. **Build `INCOMING` NUL-safely — never `$(diff --name-only)`.** The membership test
    compares against paths the sweep read from `status --porcelain -z` (line 558):
    **raw and unquoted**. A plain `task_git diff --name-only HEAD..@{u}` in a command
    substitution fails *two* independent ways, both **fail-open** (the gate concludes
    "not incoming" and proceeds into the very overwrite condition 4 exists to stop):
    a path containing a newline is split into two false names, and — separately — git
    **C-quotes** paths with unusual bytes by default, so `"aitasks/t10\nfoo.md"` never
    compares equal to the raw porcelain path. `$( )` also discards NUL, which is why
    the dirty scan already writes to a file (see its comment at 552-554).

    Mirror that existing pattern, but **encapsulate it so the temp file cannot leak**.
    The script has no `trap` at all, and `main` / `do_pull_rebase` / `do_push` all
    `exit` from nested functions, so a bare `incf="$(mktemp)"` at call-site scope would
    be abandoned on every deferral, conflict and network path:

    ```bash
    declare -A INCOMING=()
    _load_incoming() {                     # 0 = INCOMING is authoritative, 1 = unknown
        INCOMING=()
        local incf p rc=0
        incf="$(mktemp)" || return 1
        task_git diff --name-only -z HEAD..@{u} > "$incf" 2>/dev/null || rc=$?
        if [[ $rc -eq 0 ]]; then
            while IFS= read -r -d '' p; do INCOMING["$p"]=1; done < "$incf"
        fi
        rm -f "$incf"
        return $rc
    }
    ```
    **No trap is needed, and that is a property to preserve, not an accident:** between
    `mktemp` and `rm -f` there is no exit point. `diff` is on
    `_ait_git_subcmd_is_readonly`'s allowlist so `task_git` cannot `die()` there, the
    `|| rc=$?` absorbs the status under `set -e` (a bare call would abort *after* the
    file existed), and the read loop cannot exit. Anything added inside that window
    must keep it exit-free or the function needs a trap.

    Membership is then `[[ -n "${INCOMING[$path]:-}" ]]` — the `:-` guard is required
    under `set -u`. **`_load_incoming` returning non-zero means the incoming set is
    unknown, and an unknown set is not an empty one: treat every record as blocking
    (fail closed).**

11. `_rebase_blocked <local_ahead> <remote_ahead>` (reading `PROT_*` and the
    script-scope `INCOMING` map built above, once, after `do_fetch`). **Decision
    order:**

    1. `remote_ahead == 0` → **not blocked, unconditionally.** There is no rebase to
       block; `do_push` needs no clean tree. *This is the clause the previous draft
       omitted, and the one Test 3 pins.*
    2. any record with `tree_state=unknown` → blocked (we cannot reason about it).
    3. any `tracked` record **and** `local_ahead > 0` → blocked (a rebase needs a
       clean tree).
    4. any record (`tracked` or `untracked`) whose path ∈ `INCOMING` → blocked (the
       checkout would overwrite it).
    5. otherwise → not blocked.

    Rewrite the comment at 1135-1147 to state this five-way rule; the current text
    ("`git pull --rebase` refuses with unstaged changes") becomes untrue.

12. `main`, replacing the gate at 1153-1157 and threading into step 7:
    - blocked → `_emit_protected_deferral`; `exit 0` (unchanged shape).
    - not blocked, `remote_ahead > 0`, `local_ahead == 0` →
      `task_git merge --ff-only --quiet @{u}`, `did_pull=true` on success. This mirrors
      `task_data_converge`'s ff-only rule (`task_utils.sh:1554`). A fast-forward never
      conflicts, and git refuses it only if it would overwrite a dirty file — which
      condition 4 already excluded. On failure, fall through to the existing
      `do_pull_rebase` path rather than inventing a new error token.
    - not blocked, `remote_ahead > 0`, `local_ahead > 0` → `do_pull_rebase` as today
      (only untracked, non-incoming records can remain).

    `merge` is on neither the read-only nor the recovery allowlist, so
    `assert_data_worktree_clean` runs — but `main`'s step-1b `_worktree_wedged` check
    already exited on a wedged worktree, so it is a no-op here. **No allowlist change,
    and none should be made:** widening it would let a merge run on a wedged tree.

13. **The retry fetch must succeed before anything is recomputed.** Line 1068 is
    `_git_with_timeout fetch origin 2>/dev/null || true` — the failure is swallowed
    outright. Recomputing the gate on top of that is unsound: `@{u}` is then stale, so
    `remote_ahead` can read `0`, hit condition 1, and report "not blocked" while an
    unseen incoming commit is touching a protected path — the correct safe outcome
    replaced by a later generic `ERROR:push_rebase_failed` / `ERROR:push_failed`.
    Capture the status and branch on it, mirroring `do_fetch`'s existing contract
    (877-896): rc 124 or any non-zero → `batch_out "NO_NETWORK"`, `iwarn`, and
    `exit 0`. **Never recompute `local_ahead` / `remote_ahead` / `INCOMING` from a
    fetch that did not succeed.**

14. **Push-retry re-gate on fresh inputs.** Replace `do_push`'s pre-fetch bail
    (1060-1064) with a post-fetch decision: after the *successful* retry fetch,
    recompute `local_ahead`, `remote_ahead` and `INCOMING`; re-run `_rebase_blocked`; blocked →
    `_emit_protected_deferral` and `return 2`; otherwise route through `do_pull_rebase`
    and delete the bare `task_git pull --rebase --quiet` at 1074 (the t1725_1 note's
    finding 1 — it leaves `rebase-merge` behind on conflict). Note `do_pull_rebase`
    ends the process with `exit 0` after `batch_out "CONFLICT:…"` in batch mode; that
    is the intended reporting path, and the `publication_blocked` guard at 1049 must
    stay **ahead** of the new gate.

15. Add a marker-gated `pre_push` seam (`_sync_test_seam pre_push`, same mechanism as
    `pre_commit_phase`) immediately before the **first** push, so a test can advance
    the remote between the gate and the push.

### 3d. Wire

16. Status line keeps its prefix and the closed three-reason set (`DEFERRED_REASONS`
    **unchanged**):
    `DEFERRED:protected_dirty:<N> file(s) block the rebase: live_lock=<k> ownerless=<m> …`
    `<N>` is now the number of **records** (per-path), not skip events — a deliberate
    semantic change. `test_every_emitted_deferred_reason_is_declared` scans
    `batch_out\s+"DEFERRED:([^":$]*)` and still captures `protected_dirty`, so it
    keeps passing; `test_metadata_commit_seam.sh:298` asserts the same prefix and also
    keeps passing.

17. New `batch_detail()` — stdout, batch mode only, **deliberately not `batch_out`**,
    so `_emitted_tokens` (`batch_out\s+"([^"]*)"`) does not read a detail line as a
    status. One continuation line per record, **after** the status line:

    `DEFERRED_FILE:<sub_reason>|<task>|<path>|<tree_state>|<holder>|<email>|<host>|<pid>|<pane>|<pane_state>|<action>`

    The record is the **complete per-file snapshot** — every field a consumer renders
    is on the wire, so no TUI re-derives locks, pane state or files.

18. **Close the line-boundary hole — LF is not the only one.** The record is consumed
    by Python, and `str.splitlines()` treats **nine** further characters as line
    boundaries, *every one of which is a legal byte in a git path*: CR `\x0D`, VT
    `\x0B`, FF `\x0C`, FS `\x1C`, GS `\x1D`, RS `\x1E`, NEL `\x85`, and (after UTF-8
    decoding) U+2028 / U+2029. Verified this session: `'a\x0bb'.splitlines()` →
    `['a','b']`. The current codec encodes only `%`, `|` and LF, so a path, host,
    email, action or pane value containing any of the nine corrupts the record.
    **Fix both halves — one alone is insufficient:**

    - **Codec:** add `%0D` for CR to `_pct_encode`, and to `_pct_decode` in the
      order `%0A`, `%0D`, `%7C`, **`%25` last**. CR is the one that also matters
      outside Python — a trailing CR would otherwise be read as field data and makes
      the stderr report and the persisted quarantine record unreadable. The codec is
      shared with `_quarantine_add` / `_quarantine_load_and_prune`; the change is
      symmetric, and an already-persisted record containing a raw CR still decodes
      unchanged, so there is no migration.
    - **Parser:** `parse_sync_output` must split on `"\n"`, **not** `splitlines()`.
      Encoding all nine would rest the guarantee on correctly enumerating a CPython
      implementation detail — including two characters that only become boundaries
      after UTF-8 decoding. Splitting on LF alone is one verifiable rule that holds
      for every byte a git path can contain, and it makes the encoder's job exactly
      the three characters it already handles plus CR.

19. **`_pct_encode` every textual field**: `path`, `action`, `email`, `host`, `pane`.
    A git path may contain `|`, LF and CR; `hostname` and `locked_by` are
    user-controlled; a tmux session name may contain them too. Closed/numeric fields stay
    bare and are validated by the parser: `sub_reason` (closed set), `task`
    `^[0-9]+(_[0-9]+)?$`, `tree_state` `tracked|untracked|unknown`, `holder`
    `self|other|remote|unverified|none`, `pid` `^[0-9]*$`, `pane_state`
    `^(waiting_[a-z0-9_]+|active|)$`.

20. Both emission sites go through one `_emit_protected_deferral` (status line +
    records). **Emit records only from that function.** Four existing tests assert
    `assert_not_contains "DEFERRED"` on whole stdout and `DEFERRED_FILE:` contains that
    substring, so a record emitted merely because `PROT_*` is non-empty would break
    Test 3 (which has records and correctly does not defer). `report_skipped` (stderr)
    is unchanged.

21. Update **both** protocol descriptions — the file-header comment block (12-29) and
    `show_help`'s block (92-108). Both currently state "Per-file skip reasons go to
    stderr, not here", which becomes false. Two sites, one truth: each gains the
    `DEFERRED_FILE:` line and a pointer to the other rather than a third restatement.

### 3e. Parser

22. `sync_action_runner.py`: a `DeferredFile` dataclass with one field per wire column;
    `SyncResult.deferred_files: list[DeferredFile] = field(default_factory=list)`
    (**additive** — the two consumers, `syncer_app.py:2210` and
    `board/aitask_board.py:12282`, need no change); `DEFERRED_FILE_REASONS` as a closed
    frozenset of the `_protect` literals, with a scan test mirroring
    `test_every_emitted_deferred_reason_is_declared` over `_protect\s+"([a-z_]+)"`.

23. `parse_sync_output` collects `DEFERRED_FILE:` lines **only** when the first line
    parsed as `DEFERRED`. An unknown sub-reason, a closed-field value outside its
    grammar, or a wrong column count → fail closed to `STATUS_ERROR`, the same rule the
    unknown-reason branch (144-155) already applies. A `DEFERRED_FILE:` line **as the
    first line** stays `unknown status`. Decode every encoded field mirroring
    `_pct_decode` order — `%0A`, `%0D`, `%7C`, **`%25` last**, so a host containing a
    literal `%7C` does not double-decode. Line splitting is `"\n"` only (step 17);
    the existing first-line scan at 118-124 changes with it, which leaves every
    current status token unaffected (they contain no boundary characters) and keeps
    `test_first_line_only_with_trailing_noise` and `test_leading_blank_lines_stripped`
    passing.

24. **Make the subprocess byte-preserving — a git path need not be valid UTF-8.**
    `run_sync_batch` (213-221) uses `subprocess.run(..., capture_output=True,
    text=True)`, which decodes with the locale codec and **`errors="strict"`**. A path
    containing a single `0xFF` therefore raises `UnicodeDecodeError` *inside
    `subprocess.run`*, before `parse_sync_output` is ever reached — and the `except`
    clauses cover only `TimeoutExpired` and `FileNotFoundError`, so it propagates out
    of `run_sync_batch` and crashes the caller (`syncer_app.py:2210`,
    `aitask_board.py:12282`). Verified this session: strict → `UnicodeDecodeError:
    'utf-8' codec can't decode byte 0xff in position 57`.

    This is latent today (such a path already reaches the captured **stderr**), but
    this task puts paths on **stdout**, which is the whole point of it — so it becomes
    reachable on the main path and must be fixed here.

    Keep the wire format unchanged and fix the decode: pass
    `encoding="utf-8", errors="surrogateescape"` to `subprocess.run`. Pin `encoding`
    explicitly rather than relying on `text=True` + the ambient locale, so the
    convention is one documented codec instead of whatever `LC_ALL` happens to be.
    Round-trip verified: `'…a\udcffb'.encode("utf-8", "surrogateescape")` yields the
    original `a\xffb`.

    **Document the convention on `DeferredFile`:** textual fields are decoded with
    Python's filesystem-surrogate convention, so `path` / `host` / `email` / `pane`
    may contain lone surrogates and must be re-encoded with
    `.encode("utf-8", "surrogateescape")` to recover the original bytes. Rendering
    such a value safely to a terminal is **t1725_5's** responsibility, not this
    task's — a consumer that writes one to a strict-UTF-8 stream will raise, and the
    docstring must say so rather than leaving the next child to discover it.

25. **Out of scope, named:** `sync_batch_command` (188-198) builds a hard-coded
    two-element argv with no `extra_args` parameter. Threading `--commit-for-task` from
    a TUI is **t1725_5's** work; this task leaves the builder alone and exposes the
    flags on the CLI only.

### 3f. `--commit-for-task`, `--expect-path`, `--require-waiting`

26. `--commit-for-task <id>[,<id>…]`, evaluated **inside `_holder_verdict`** so it
    applies at *both* lock snapshots (pre-scan and the 5a.2 CAS): a listed task returns
    `free` only if `_holder_class` is `self` **at that evaluation**. A lock that changes
    hands between the two snapshots yields differing verdicts and is skipped as
    `lock_acquired_during_scan` — the existing CAS does this for free. Any other class,
    **including `unverified`**, is refused with a stderr line naming who holds it. The
    override bypasses **neither** 5a.3 (state re-check) nor 5a.4 (publication guard).
    When it does commit on behalf, print to stderr: `t<id>'s session is live — its
    uncommitted edits were committed as they stand now`.

27. `--expect-path <pct-encoded path>` — **repeatable, one argument per path, never a
    CSV** (a comma is a legal path character and `_pct_encode` deliberately leaves it
    alone). With `--commit-for-task`, if the task's dirty group at commit time is not
    exactly that set (any extra **or** missing path), skip it as
    `_protect "commit_scope_changed"` with the delta in the action text.

28. `--require-waiting` (with `--commit-for-task`; the TUI will always pass it): in
    `_commit_group`, after 5a.3 and before the commit, re-probe the holder's pane via
    `ait_tmux_pane_for_pid` + `lib/pane_state_probe.py`. Unless the result is
    `waiting_<kind>`, skip as `_protect "holder_not_waiting"` with the observed state in
    the action text. **Fail closed when the probe is unavailable** — and it *is*
    unavailable until t1725_4 lands, so that is the only behavior reachable here.
    Resolve the probe by presence check, never by `command -v` on a name that might
    resolve to something else. The bare flag without `--require-waiting` remains the
    explicit operator escape.

29. Add the three flags to the parse loop (129-138; an unknown flag already `die`s) and
    document them in `show_help`.

30. `shellcheck .aitask-scripts/aitask_sync.sh` — clean, and note the script has no
    `trap`, so nothing needs unwinding around the new exits.

### Post-phase (risk mitigations)

31. **[deferred_file_bound_to_status_line]** — assert the coupling that four existing
    tests silently depend on: across a matrix of runs that *have* protected records but
    do *not* defer (Test 3's shape, `remote_ahead == 0`; and the fast-forward shape),
    stdout contains **no** `DEFERRED_FILE:` line; and in every run that does defer, the
    first line is `DEFERRED:protected_dirty` and the record count equals the `<N>` in
    it. Pins record emission to the status line so a later refactor cannot re-break
    Tests 2/3/6/20 by emitting records eagerly.

## Verification

**Test 1 fixup (decided this session).** Test 1's fixture is the t1696 fast-forward
case and would now report `PULLED`. Add `printf 'edit20\n' >> …/t20_beta.md` to its
setup so a t20 group commits (`local_ahead=1`); the tracked record then blocks via
condition 3 and `assert_contains "DEFERRED:protected_dirty"` holds, preserving the
original intent (defer rather than `ERROR:pull_rebase_failed`). Tests 2-18b, 19 and 20
were each re-checked against the new gate and are unaffected: 19 blocks via condition 3
after its retry fetch, 20 has no records, 3 is saved by condition 1.

**AC2, both directions** (`tests/test_sync_deferral_and_quarantine.sh`):
1. untracked `aiplans/p10_x.md` + live lock on t10 + remote ahead, no incoming touch →
   **no** `DEFERRED`, pc2's commit pulled, local pushed.
2. tracked `t10_alpha.md` in the same position with a local commit → `DEFERRED:protected_dirty`.
3. untracked, but an incoming commit creates the same path → deferred (condition 4).
4. `local_ahead == 0` + tracked dirty untouched by incoming → **fast-forwarded**, no
   deferral (t1696's scenario, and the case Test 1 used to assert the opposite of).

**Wire rows.** With `TEST_HOSTNAME` plus a new `set_userconfig_email` fixture helper
(writing `aitasks/metadata/userconfig.yaml` in the fixture — `get_user_email` at
`task_utils.sh:2145` reads exactly that path):
`DEFERRED_FILE:live_lock|10|aiplans/p10_x.md|tracked|self|other%40x.com|testhost|<pid>|||…`
Plus `other` (`lock_yaml_live 10 testhost` + a different userconfig email), `remote`
(`lock_yaml_live 10 otherhost`), and `unverified` (no userconfig email; and separately
a lock blob with no `locked_by:`).

**Flags.** `--commit-for-task 10` with class `self` → group committed
(`ait: Auto-commit t10 …`), run pushes, stderr carries the live-session warning; class
`other` → refused, still deferred; class `unverified` → refused; under the
`pre_group_commit` seam → skipped/quarantined exactly as without the flag (negative
control proving no guard is bypassed). `--expect-path`: identical set → committed;
group grown by one → `commit_scope_changed`, **nothing** committed; a path containing a
comma (`aiplans/p10_a,b.md`) round-trips and matches. `--require-waiting` with no probe
→ `holder_not_waiting`, nothing committed (the fail-closed pin; the positive case is
t1725_4's).

**Push-retry race** via the `pre_push` seam: the hook advances the remote from `pc2`
with a commit creating the protected untracked path → push rejected → retry gate blocks
→ `DEFERRED:protected_dirty`, **no** `ERROR:push_rebase_failed`, local bytes unchanged.
Negative control: an unrelated advance → retry rebases → `PUSHED`.

**Hostile-path gate test (step 10).** A protected untracked path containing a **newline**
(`aiplans/p10_a$'\n'b.md`), with an incoming commit that creates that same path →
**deferred**. This is the fail-open case: with a line-oriented `INCOMING` the path is
either split in two or arrives C-quoted, membership misses, and the run proceeds into
the overwrite. Negative control: the same newline path with the incoming commit touching
something else → not deferred, fast-forwarded. Add a second cell with a path containing
a literal `"` and a backslash, which git also C-quotes.

**Retry-fetch failure (step 13).** Drive the `pre_push` seam to make the push rejected,
then force the retry fetch to fail (point `origin` at an unreachable URL from inside the
hook, or set the network timeout to 0): the run must emit **`NO_NETWORK`** — not
`ERROR:push_rebase_failed`, not `ERROR:push_failed`, and **not** a `DEFERRED`/`PUSHED`
verdict computed from a stale `@{u}`. Negative control: the same race with a fetch that
succeeds → the existing Test 19 / 20 outcomes are unchanged.

**Non-UTF-8 path reaches `DeferredFile` (step 24).** A regression test that a path
containing a raw `0xFF` byte survives the whole pipeline: the shell emits it, the
subprocess decodes it under `surrogateescape`, `parse_sync_output` yields a
`DeferredFile`, and `record.path.encode("utf-8", "surrogateescape")` is **byte-identical**
to the original. Drive it through `run_sync_batch` against a stub script, not just
`parse_sync_output` — the failure is inside `subprocess.run`, so a parser-only test
would pass while the real path still raises. Negative control: the same run with the
current `text=True` strict decode raises `UnicodeDecodeError`, which documents what the
fix buys.

**No temp file is left behind (step 10).** Run a **deferring** sync (an early-exit
route: `main` exits from inside the gate, after `_load_incoming` has already run) with
`TMPDIR` pointed at a fixture-private directory, and assert that directory is empty
afterwards. This covers `incf` and the pre-existing `dirtyf` together; if it catches a
`dirtyf` leak on some branch, fix that in the same change — it is the same class.

**Line-boundary round trips (step 18).** In `tests/test_sync_action_runner.py`, pin a
`DEFERRED_FILE:` record whose `path` contains each of CR `\x0D`, VT `\x0B`, FF `\x0C`,
FS `\x1C`, GS `\x1D`, RS `\x1E`, NEL `\x85` and U+2028: every one parses as **one**
record whose decoded path is byte-identical to the input. Assert the same for `host`,
`email`, `action` and `pane`. A control asserting `splitlines()` would have split each
of them documents *why* the parser splits on `"\n"`, so a later "tidy-up" back to
`splitlines()` fails loudly. Shell side: a CR path survives `_pct_encode` →
`_pct_decode` and the persisted quarantine record (extend Test 18b, which already
covers `|` and `%`).

**Parser** (`tests/test_sync_action_runner.py`): continuation parsing; decode of `|` in
a path, in an email, and in a pane target from a session named `a|b`; a host containing
literal `%7C` must **not** double-decode; unknown sub-reason, bad `pane_state`, and
wrong column count each fail closed; first-line `DEFERRED_FILE:` is `unknown status`;
the closed-set scan; `_emitted_tokens` and all six existing DEFERRED tests still pass.

**Test-file conventions.** `test_sync_deferral_and_quarantine.sh` uses top-level
in-process counters with no subshell bodies. The new `tests/test_sync_protect_paths.sh`
must either follow that shape or opt into `assert_counters_init` /
`assert_counters_load` — a subshell body without the opt-in reports zero failures and
exits 0 no matter what failed (t1207).

**Run:**
```bash
bash tests/test_sync_protect_paths.sh
bash tests/test_sync_rebase_gate.sh
bash tests/test_sync_deferral_and_quarantine.sh
bash tests/test_sync.sh
bash tests/test_sync_auto_commit_scoping.sh
bash tests/test_metadata_commit_seam.sh
bash tests/run_all_python_tests.sh --test-dir tests   # verdict on the LAST line
shellcheck .aitask-scripts/aitask_sync.sh
```

## Risk

### Code-health risk: high
- The restructure converts 16 `_protect` call sites from a flat reason list to 11
  lockstep parallel arrays inside a 1202-line script under `set -euo pipefail`, whose
  every non-zero exit surfaces to two TUIs as `ERROR: empty output`. An unset index
  read aborts the run with empty stdout · severity: high · → mitigation: inline pre-phase characterize_sync_paths_never_empty_stdout
- The rebase gate is load-bearing and its specification was **demonstrably wrong**:
  as written it would have broken Tests 1 and 3 in opposite directions. That the
  defect survived both the parent and child plan is evidence the gate's interaction
  with existing pins is not obvious from reading it · severity: high · → mitigation: inline pre-phase rebase_gate_truth_table
- `DEFERRED_FILE:` shares a substring with the `DEFERRED` token that four existing
  tests assert the absence of, so record emission is coupled to the status line by
  convention rather than by construction · severity: medium · → mitigation: inline post-phase deferred_file_bound_to_status_line
- Both the gate and the wire handle **user-controlled bytes** — git paths (any byte
  but NUL), `hostname`, `locked_by`, tmux session names — and every mishandling found
  so far failed **open** or crashed: a line-oriented `INCOMING`, a swallowed retry
  fetch, a codec narrower than Python's line-splitting rule, and a strict UTF-8 decode
  in the runner. The class is "a textual value crosses into something whose notion of a
  line, a field, or a valid character differs from the writer's" — five instances found
  across two review rounds, which is the reason to treat it as a standing hazard of this
  change rather than four fixed bugs ·
  severity: high · → mitigation: inline pre-phase rebase_gate_truth_table (hostile-path cells) + the step-18 / step-24 round-trip pins

### Goal-achievement risk: medium
- The record shape must serve t1725_4 (pane fields) and t1725_5 (TUI screen) sight
  unseen; a later child can find it insufficient. Mitigated structurally by carrying
  the *complete* snapshot on the wire, and by t1725_5's own `wire_fields_cover_screen`
  post-phase in the parent plan · severity: medium · → mitigation: t1725_5 post-phase wire_fields_cover_screen (parent plan)
- `--require-waiting` ships with only its fail-closed direction reachable, since its
  probe lands in t1725_4. The positive path is unexercised until then · severity: low ·
  → mitigation: none — accepted; t1725_4 owns the positive pin

### Planned mitigations
- timing: pre-phase | name: characterize_sync_paths_never_empty_stdout | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health 1 (array restructure → empty stdout) | desc: forced-path harness drives every `_protect` reason under `set -u` and pins non-empty, recognised batch stdout before the record restructure lands
- timing: pre-phase | name: rebase_gate_truth_table | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health 2 (gate spec demonstrably wrong) and code-health 4 (fail-open textual handling) | desc: table test pinning the gate verdict for every tree_state × local_ahead × remote_ahead × incoming cell, each incoming cell run twice (ordinary path and newline path), written before the rewrite so it specifies rather than transcribes
- timing: post-phase | name: deferred_file_bound_to_status_line | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health 3 (DEFERRED substring collision) | desc: assert records appear only alongside the status line and that their count equals its N, so an eager emission cannot re-break Tests 2/3/6/20

Post-inline reassessment (single pass): the three inline phases each bound a concern
with a pinned test, but none shrinks the blast radius — 16 `_protect` call sites still
convert to lockstep arrays and the gate is still rewritten in two places. Code-health
stays **high**; goal-achievement stays **medium**. The five review findings raised
across two later rounds did not change either level: all are instances of code-health
risk 4, which the truth table's hostile-path cells and the step-18 / step-24 round-trip
pins now bound, and none alters what the plan delivers. That two rounds of review each
found fresh instances of the same class is itself the argument for keeping code-health
at **high** rather than relaxing it once the named defects are fixed.

## Implementation notes (2026-09-09)

All 31 steps landed as planned. Deviations and things found while implementing:

- **The characterization harness caught four vacuous drivers before the
  restructure even started**, which is the whole reason it asserts stderr
  evidence and not just a usable stdout token: `pre_group_commit` drives the
  publication guard rather than `content_changed` (the 5a.3 re-check has already
  run by then, so `pre_commit_phase` is the right seam for both it and
  `lock_acquired_during_scan`); a planted lock dir carrying `pid` but no `owner`
  is a tokenless lock the reclaimer is entitled to take, so `lock_contended`
  never fired; and `run_sync` unconditionally exports `AITASKS_LOCK_DIR`, so a
  value passed in from a driver is discarded. Each of the four passed the stdout
  assertion while proving nothing.

- **The scan itself went vacuous mid-task and stayed green.** Moving eight call
  sites onto `_protect_task_paths` / `_protect_group_paths` took the source scan
  from 12 reasons to 6, and the forward check (scanned reason -> driver) has
  nothing to say about a reason that has vanished from the scan. The regex now
  matches all three receivers, and a REVERSE check (every `drive_<reason>` must
  correspond to a scanned reason) makes it unrepeatable.

- **`test_every_emitted_token_is_recognised` was broken by a code comment.** The
  `batch_detail` docstring explains the contract by naming `batch_out "<literal>"`,
  and the scan's regex matched the prose. `_code_only()` now drops whole-line
  shell comments before both token scans -- narrower and more accurate, since a
  literal in a comment reaches `batch_out` exactly never.

- **Test 1 changed, as agreed at planning.** Its fixture is the t1696
  fast-forward case; under the new gate it reports `PULLED`. It gains a t20 edit
  so `local_ahead == 1`, which re-blocks it via rule 3 and keeps the original
  regression (defer rather than `ERROR:pull_rebase_failed`) pinned. Tests 2-20
  were unaffected, exactly as the verification pass predicted.

- **`_rebase_blocked` needs `remote_ahead == 0` as its FIRST clause**, not as an
  input it merely receives. Confirmed by Test 3: tracked-dirty + `local_ahead=1`
  + `remote_ahead=0` trips rule 3 and would defer a push that needs no clean
  tree at all.

- **Two fixture bugs fixed rather than worked around.** `aiplans/` holds no
  committed file, so git never tracked the directory and a fresh clone lacks it
  -- a pc2 helper writing there failed silently and the remote never advanced.
  And `set_userconfig_email` needed the data branch's real `.gitignore` entry,
  or every test using it also gained a phantom `ownerless` record for
  `userconfig.yaml`.

- **Both new guards were mutation-checked.** Reverting `_load_incoming` to a
  line-oriented `diff --name-only` makes the two hostile-path cells fail with
  `ERROR:pull_rebase_failed` -- the predicted fail-open, where the gate waves the
  checkout through and git refuses the overwrite. Restoring `|| true` on the
  retry fetch makes Test 28 fail with `ERROR:pull_rebase_failed` instead of
  `NO_NETWORK`. Both were restored from a backup and re-verified green.

- **Test 28 was vacuous on its first two drafts** and is worth reading before
  editing: breaking the remote before the run makes the step-5 `do_fetch` emit
  `NO_NETWORK` on its own, and appending to `install_racing_pre_push`'s hook puts
  the code after its `exit 0`. The remote has to break from inside the hook, i.e.
  between the two fetches.

- **Two defects found at Step-8 review, both confirmed and fixed:**
  - `locks_unavailable` records were emitted with `holder=none`. `none` is a
    closed value meaning *unlocked*, and that branch exists precisely because
    the lock branch could not be read -- so a record advertising itself as the
    complete snapshot carried a false fact, and a consumer reading it could
    reasonably offer "nobody holds this, commit it". `_holder_class` now returns
    `unverified` whenever the snapshot is unreadable, checked BEFORE the
    `none` shortcut and deliberately not conditioned on `--assume-unlocked`
    (that flag governs whether to commit, not what is known).
    `LOCKS_UNINITIALIZED` stays `none`: there is no lock branch, so nothing is
    locked and the claim is true.
  - `--expect-path` is a single task's contract but was compared against every
    group in turn, so `--commit-for-task 10,20` with one path per task made each
    task see the other's as missing and refused BOTH -- measured: zero commits,
    two `commit_scope_changed` records. Rather than grow a per-id expectation
    syntax for something the caller can express as two runs, the ambiguous
    combination is now refused up front, as are `--expect-path` and
    `--require-waiting` without `--commit-for-task`. Pinned with a control that
    a single-task invocation still commits, so the refusal cannot widen into
    refusing everything.

- **Not done here, deliberately:** `sync_batch_command` still builds a
  hard-coded two-element argv. Threading `--commit-for-task` from a TUI is
  t1725_5's work; the flags are CLI-only in this change.

## Post-Review Changes

### Change Request 1 (2026-09-09 17:05)
- **Requested by user:** Two blocking review findings. (1) `locks_unavailable`
  records were emitted with `holder=none`, a closed value meaning *unlocked*, on
  a branch that exists precisely because the lock branch could not be read.
  (2) `--expect-path` is one global set compared against each task group in
  turn, so a multi-id `--commit-for-task` refuses every group.
- **Changes made:** `_holder_class` answers `unverified` whenever the snapshot
  is unreadable, checked before the `none` shortcut; `LOCKS_UNINITIALIZED` still
  yields `none` because nothing IS locked then. The ambiguous
  `--expect-path` + multi-id combination is refused up front, as are
  `--expect-path` / `--require-waiting` without `--commit-for-task`. Four
  regression tests added (36-39), including one that asserts through
  `parse_sync_output` rather than pattern-matching the wire, plus a control that
  a single-task `--expect-path` still commits. Both guards mutation-checked.
- **Files affected:** `.aitask-scripts/aitask_sync.sh`,
  `tests/test_sync_deferral_and_quarantine.sh`

## Final Implementation Notes

- **Actual work done:** All 31 planned steps, plus the two review fixes above.
  `aitask_sync.sh` gained the eleven-array per-file record, `_holder_class` /
  `_holder_action`, the five-rule `_rebase_blocked` with a NUL-safe `INCOMING`
  set, the fast-forward converge path, a re-gated push retry whose fetch failure
  is no longer swallowed, `batch_detail` + `_emit_protected_deferral`, CR in the
  percent codec, and the three commit-on-behalf flags.
  `sync_action_runner.py` gained `DeferredFile`, `DEFERRED_FILE_REASONS`,
  LF-only line splitting and a surrogateescape subprocess decode. Four test
  files changed and two were created.

- **Deviations from plan:** Only one behavioural deviation, agreed at planning:
  Test 1 gains a local commit because its fixture IS the fast-forward case the
  task introduces. Two scope decisions were kept as planned:
  `sync_batch_command`'s argv is untouched (t1725_5 owns TUI wiring) and
  `--require-waiting` ships fail-closed-only until t1725_4 lands the probe.
  The `--expect-path` contract narrowed at review from "global set" to "one task
  per invocation".

- **Issues encountered:** The characterization harness caught four vacuous
  drivers and the source scan silently halving its own coverage; details in the
  Implementation notes section above. A code comment in `batch_detail` broke
  `test_every_emitted_token_is_recognised` because the scan regex matched prose,
  fixed by making both token scans comment-aware. Two fixture bugs were fixed
  rather than worked around (`aiplans/` is untracked so a fresh clone lacks it;
  `userconfig.yaml` needed the data branch's real `.gitignore` entry).

- **Key decisions:** (1) The parser splits on LF alone rather than encoding all
  nine characters `str.splitlines()` recognises -- one verifiable rule beats
  enumerating a CPython implementation detail. (2) `_load_incoming` keeps its
  mktemp/read/rm window exit-free instead of adding the script's first `trap`.
  (3) The commit-on-behalf guards run before the staging loop, so an abandoned
  group leaves nothing in the shared index. (4) Holder class states what is
  KNOWN and is not softened by `--assume-unlocked`, which governs whether to
  commit.

- **Upstream defects identified:**
  - `tests/test_minimonitor_bottom_pin.py:349 — DegenerateRangeTests::test_pinned_list_that_stops_overflowing_never_goes_negative is load-sensitive and fails under the parallel lane.` Failed at 97% in one full-suite run (`PYTHON SUITE: FAILED`), passed 8/8 standalone, and passed in an immediate re-run (`7200 passed, 0 failed`). It has zero references to anything this task touched. CLAUDE.md carves the `*_live.py` minimonitor module out of the parallel lane for exactly this boot-budget reason; this non-live module shares the sensitivity but is not carved out, so it can turn any developer's suite verdict red at random.

- **Notes for sibling tasks:**
  - **t1725_4** fills `PROT_PANE` / `PROT_PANE_STATE`, which are appended as `""`
    by `_protect` today. The probe hook is already in `_commit_group` behind
    `--require-waiting`: it looks for a `ait_tmux_pane_for_pid` function and a
    `lib/pane_state_probe.py` file, and refuses when either is absent. Landing
    both flips it from always-refusing to actually gating, and
    `tests/test_sync_protect_paths.sh::drive_holder_not_waiting` plus Test 27
    pin the fail-closed direction that must keep working.
  - **t1725_5** needs `sync_batch_command` to grow an argv parameter -- it is
    still a hard-coded two-element list, deliberately. Note `--expect-path` is
    now a ONE-TASK contract: a TUI confirming files across two tasks must issue
    two sync runs. Every field the screen renders is already on the wire; if one
    is missing, extend the record here rather than re-deriving it in the TUI.
  - **t1731** extends the same gate with the diverged case. `_rebase_blocked`
    takes `local_ahead` and `remote_ahead` as parameters and the incoming
    membership test is factored as the `INCOMING` map filled by
    `_load_incoming()`, so a diverged branch can be added as a rule rather than
    re-deriving the facts -- which is what t1731's note asked for.
  - **Fixture helpers added** for everyone downstream: `set_userconfig_email`
    (required for any `self` / `other` holder-class test) and the data branch's
    `.gitignore`.

## Step 9

Standard post-implementation. Commit task/plan files with
`./.aitask-scripts/aitask_task_commit.sh` or a path-scoped `./ait git commit -- <paths>`.
Parent t1725 archives after the last child; t1725_4 and t1725_5 depend on the record
defined here, and t1731 will extend the same gate with the diverged case — leaving
`local_ahead`, `remote_ahead` and the `INCOMING` membership test factored as named
helpers (step 10) is what lets it add a branch rather than re-derive the facts.
