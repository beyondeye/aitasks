---
Task: t1269_report_silent_git_failures_in_sync_and_chatlink.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1269 — Report silent git failures in `task_sync` and chatlink task creation

## Context

t1265 fixed `task_push()`: a completely failed push used to be byte-for-byte
indistinguishable from a successful one (no output, exit 0). It now classifies
the failure, exposes `TASK_PUSH_*` globals in-process, warns on stderr, and
prints a structured token via `ait git push --batch`.

Two neighbours of the same defect class were deliberately left out of t1265's
scope and are this task's subject:

1. **`task_sync()`** (`.aitask-scripts/lib/task_utils.sh:194-201`) still has the
   original shape — `git pull --rebase --quiet 2>/dev/null || true`, return 0,
   no outcome reporting at all. It runs on **every** pick / explore / fold /
   review / pr-import (via `aitask_pick_own.sh --sync`, called from Step 0c of
   each of those skills), so a permanently failing sync — dirty data worktree,
   wedged rebase, unreachable remote, missing upstream — silently leaves the
   agent working from a stale task list, which is exactly the multi-PC state the
   sync exists to prevent. Worse, `aitask_pick_own.sh` then prints a literal
   `SYNCED`.
2. **`.aitask-scripts/chatlink/task_create.py:119-129`** shells out to
   `ait git push` and audits a warning on `push.returncode != 0`. Since
   `task_push` returns 0 for every push outcome, that branch is effectively
   unreachable: a failed push after chat-intake task creation is never logged
   and the commit silently stays local. t1265 shipped the `--batch` contract
   this caller needs; nothing consumed it.

**Goal:** keep both call sites best-effort and non-fatal, but stop them being
silent — report *what* is unreconciled and *why*, with an actionable hint,
reusing t1265's classifier and hint table rather than forking them.

## Design

### 1. `task_sync()` outcome contract (`.aitask-scripts/lib/task_utils.sh`)

Mirrors the `TASK_PUSH_*` block that sits directly below it in the same file.

```bash
# Outcome of the most recent task_sync call. task_sync always returns 0 (the
# best-effort contract) — read these when the outcome matters.
#
# BOTH counts are sampled AFTER the pull cycle and are read against the LOCAL
# upstream ref. TASK_SYNC_UNPUSHED is authoritative (HEAD is local).
# TASK_SYNC_UNPULLED is NOT: `git pull --rebase` refuses before it fetches when
# the worktree is dirty, and an unreachable remote never updates the ref either,
# so on a failed sync it reports the remote side as of the LAST SUCCESSFUL FETCH
# and can read 0 while the remote has in fact moved. Never present it as a
# current reading of the remote.
TASK_SYNC_STATUS=""     # synced | up-to-date | no-remote | failed
TASK_SYNC_REASON=""     # classifier code when failed (see _task_push_classify)
TASK_SYNC_UNPUSHED=""   # local commits not on upstream; "" when undeterminable
TASK_SYNC_UNPULLED=""   # cached upstream commits not merged; "" when undeterminable
```

`task_sync()` becomes:

```bash
task_sync() {
    TASK_SYNC_STATUS=""; TASK_SYNC_REASON=""
    TASK_SYNC_UNPUSHED=""; TASK_SYNC_UNPULLED=""

    # No remote at all (solo / offline-only repo): nothing to reconcile.
    if ! _task_push_has_remote; then
        TASK_SYNC_STATUS="no-remote"
        return 0
    fi

    local before_head after_head pull_err="" detail=""
    before_head="$(_task_sync_head)"

    if pull_err="$(_task_pull_rebase 2>&1)"; then
        after_head="$(_task_sync_head)"
        if [[ "$before_head" == "$after_head" ]]; then
            TASK_SYNC_STATUS="up-to-date"
        else
            TASK_SYNC_STATUS="synced"
        fi
        TASK_SYNC_UNPUSHED="$(_task_push_unpushed_count)"
        TASK_SYNC_UNPULLED="$(_task_sync_unpulled_count)"
        return 0
    fi

    TASK_SYNC_STATUS="failed"
    TASK_SYNC_REASON="$(_task_push_classify "" "$pull_err")"
    TASK_SYNC_UNPUSHED="$(_task_push_unpushed_count)"
    TASK_SYNC_UNPULLED="$(_task_sync_unpulled_count)"
    if [[ "$TASK_SYNC_REASON" == "unknown" ]]; then
        detail="$(_task_push_first_line "$pull_err")"
        if [[ -n "$detail" ]]; then detail=" (git: ${detail})"; fi
    fi
    _task_sync_warn "$detail"
    return 0
}
```

**Reuse, no forks** (all already in `task_utils.sh`): `_ait_data_git` (the
`LC_ALL=C` data-worktree seam), `_task_pull_rebase`, `_task_push_has_remote`,
`_task_push_unpushed_count`, `_task_push_upstream`, `_task_push_first_line`,
`_task_push_classify`, `_task_push_reason_hint`, `warn`
(`lib/terminal_compat.sh`, writes to stderr).

Calling `_task_push_classify "" "$pull_err"` is the intended reuse shape: the
`dirty_worktree` / `rebase_conflict` arms match on the rebase argument, the
`remote_unreachable` / `no_upstream` arms match the combined blob, and `diverged`
matches only the push argument — correctly inert for a pull-only cycle.

**`assert_data_worktree_clean` is deliberately NOT added.** `task_sync` does not
call it today; adding it would make a wedged worktree `die` (exit 1) inside
`aitask_pick_own.sh` (which runs `set -euo pipefail`), aborting every pick.
Instead the wedged case surfaces as `rebase_conflict` with its recovery hint —
loud, but still non-fatal.

Two small probes, following the "probes never leak non-zero" rule from
`aidocs/framework/shell_conventions.md` (they are consumed via `$(...)` inside
`set -e` scripts):

```bash
_task_sync_head()           { _ait_data_git rev-parse HEAD 2>/dev/null || true; }
_task_sync_unpulled_count() { _ait_data_git rev-list --count 'HEAD..@{upstream}' 2>/dev/null || true; }
```

### 2. Shared classifier gains a `no_upstream` arm

A configured remote with **no upstream for the current branch** (a freshly
created or re-pointed task-data branch, a detached/renamed data branch) is a real
and currently mis-served state: `git pull --rebase` fails with *"There is no
tracking information for the current branch."* and `git push` with *"The current
branch … has no upstream branch."* Both fall through to `unknown` today, whose
hint is *"reason unknown; run './ait git-health' and inspect the data worktree
manually"* — the wrong recovery for a one-command fix. Add one arm to
`_task_push_classify`, matched on the combined blob (no substring overlap with
any existing arm, so ordering relative to `remote_unreachable` is not
load-bearing):

```bash
    case "$blob" in
        *"no upstream branch"*|*"no tracking information"*)
            echo "no_upstream"; return 0 ;;
    esac
```

and the matching hint arm:

```bash
    no_upstream)
        echo "task-data branch has no upstream; set one with 'git branch --set-upstream-to=origin/<branch>' (or run 'ait setup' to repair the data branch)" ;;
```

This widens t1265's documented reason vocabulary, so
`website/content/docs/commands/sync.md`'s `FAILED:<reason>` row must list
`no_upstream` alongside the existing codes. **Confirm the two substrings
empirically before finalizing** (they are long-standing git strings, but the test
below depends on them):

```bash
git -C <fixture> pull --rebase 2>&1 | head -3     # expect "no tracking information"
git -C <fixture> push          2>&1 | head -3     # expect "no upstream branch"
```

The `unknown` fallback stays as the safety net: an unmatched message still warns
and quotes git's own first line, so no failure mode becomes silent.

### 3. Hint table gains a retry-command parameter

`_task_push_reason_hint`'s `remote_unreachable` arm hard-codes
`retry './ait git push'`, the wrong recovery after a failed *pull*. Add an
optional second argument instead of forking the table:

```bash
_task_push_reason_hint() {
    local retry_cmd="${2:-./ait git push}"
    ...
    remote_unreachable)
        echo "remote unreachable (network, auth, or no configured destination); retry '${retry_cmd}' once connectivity is restored" ;;
```

The push path is unchanged (default arg); `_task_sync_warn` passes `./ait sync`.
The parenthetical is reworded once to be direction-neutral —
verified: nothing under `tests/`, `website/`, or `.aitask-scripts/` pins the old
`no push destination` wording (only the definition itself).

### 4. `_task_sync_warn` — honest counts, and silence when nothing is at risk

`task_sync` runs on every pick, so the silence policy matters as much as the
warning. Mirrors `_task_push_warn`'s "warn only when commits are stranded".
`upstream` is `" with origin/aitask-data"` when `_task_push_upstream` is
non-empty, else `""`.

| State | Message |
|---|---|
| both counts empty (no upstream / undeterminable) | `task data sync failed (unreconciled commit counts unavailable) — <hint><detail>` |
| unpushed > 0 or unpulled > 0 | `task data not reconciled<upstream>: <N> local unpushed, <M> remote unpulled (remote side as of the last successful fetch — this sync may not have refreshed it) — <hint><detail>` |
| counts are 0 **and** reason is `dirty_worktree` / `rebase_conflict` | `task data sync failed — <hint><detail>` — a local-state blocker keeps every future sync *and push* failing, so it is worth saying even with nothing pending |
| counts are 0, reason is `remote_unreachable` / `no_upstream` / `unknown` | **silent** — the offline / solo case, nothing at risk |

The parenthetical in row 2 is the point of the wording: `<M>` is read from the
local upstream ref, which a failed sync may never have refreshed, so the message
must not present it as the current remote state. `<N>` (local unpushed) carries
no such caveat and is stated plainly.

Written with explicit `if` / `case` blocks (never a trailing `[[ … ]] && x=…`),
per t1265's `set -e` lesson. A `case` with no matching arm returns 0.

### 5. `aitask_pick_own.sh --sync` stops printing a literal lie

`sync_remote()` (`:134-137`) calls `task_sync`; `main()` (`:264-270`) then
echoes an unconditional `SYNCED`. Map the outcome instead:

```bash
    if [[ "$SYNC_ONLY" == true ]]; then
        if [[ "$TASK_SYNC_STATUS" == "failed" ]]; then
            echo "SYNC_FAILED:${TASK_SYNC_REASON}"
        else
            echo "SYNCED"
        fi
        return 0
    fi
```

Every non-failure outcome (`synced` / `up-to-date` / `no-remote`) keeps printing
`SYNCED`, byte-identical to today, so the six skills that call `--sync` as a
non-blocking best-effort step are unaffected. Add `SYNC_FAILED:<reason>` to the
script's header "Output format" block (`:16-23`).

### 6. `chatlink/task_create.py` — consume the `--batch` line

- Default `push_argv` becomes `[str(repo_root / "ait"), "git", "push", "--batch"]`.
- Keep the `returncode != 0` branch: it is genuinely reachable (the wedged-worktree
  `assert_data_worktree_clean` `die` is t1265's one documented exit-0 exception),
  as are `OSError` / `TimeoutExpired`.
- Add stdout parsing on the rc == 0 path. Take the last non-blank line,
  ANSI-stripped with the module's existing `_ANSI_RE`:

| Token | Action |
|---|---|
| `FAILED:<reason>:<count>` | `audit.warning("task push failed (%s) — commit is local only", token)` — the token carries both reason and count |
| `PUSHED` / `NOTHING` / `NO_REMOTE` | nothing — all three are ordinary success outcomes |
| non-empty, unrecognised | `audit.warning("task push outcome unparseable: %r — commit may be local only", ...)` |
| empty stdout | nothing — preserves the injected-`push_argv` test seam (`("true",)`) |

The success set is a module constant (`_PUSH_OK_TOKENS = ("PUSHED", "NOTHING",
"NO_REMOTE")`) so the three tokens are declared in one place and each is
covered by its own test below — a parser typo that treats `NOTHING` (the common
"nothing to push" flow) or `NO_REMOTE` (every local-only repo) as unparseable
would otherwise emit a false audit warning on the most frequent paths.

Update the module docstring's push note to state that the outcome now comes from
the `--batch` line, not the return code.

## Files to modify

| File | Change |
|---|---|
| `.aitask-scripts/lib/task_utils.sh` | `TASK_SYNC_*` globals; `_task_sync_head` / `_task_sync_unpulled_count` probes; `task_sync` rewrite; `_task_sync_warn`; `_task_push_classify` `no_upstream` arm; `_task_push_reason_hint` `no_upstream` arm + optional `retry_cmd` |
| `.aitask-scripts/aitask_pick_own.sh` | `--sync` prints `SYNC_FAILED:<reason>` on failure; header output-format block |
| `.aitask-scripts/chatlink/task_create.py` | default `push_argv` gains `--batch`; `_PUSH_OK_TOKENS`; token parsing + audit; docstring |
| `tests/test_task_push.sh` | sync status assertions on existing Tests 6/7 + the new blocks below |
| `tests/test_chatlink_flow.sh` | push-outcome spy cases in the `task_create` block |
| `website/content/docs/commands/sync.md` | `no_upstream` row in the `FAILED:<reason>` table; short note that the same reasons/hints back the pre-pick task-data pull |

## Tests

### `tests/test_task_push.sh` (already owns the `task_sync` coverage, Tests 6–7)

Existing Tests 1–15 must keep passing unchanged. Every block below uses the
file's existing helpers (`setup_remote_and_clone`, `setup_branch_mode`,
`advance_remote`, `reload_task_utils`) and captures stderr to a **file**, never
via `$(...)` — a subshell would discard the `TASK_SYNC_*` globals the assertions
read (the trap t1265's Test 5 documents).

- **Extend Tests 6/7** (legacy + branch mode rebase pull) — add
  `assert_eq "TASK_SYNC_STATUS is synced" "synced" "$TASK_SYNC_STATUS"`.

- **Up to date (legacy).** `setup_remote_and_clone`; no `advance_remote`;
  `task_sync 2>err.txt`. Expect: rc 0, `TASK_SYNC_STATUS=up-to-date`,
  `TASK_SYNC_UNPUSHED=0`, `TASK_SYNC_UNPULLED=0`, `err.txt` **empty**
  (negative control against per-pick noise).

- **No remote configured.** `setup_remote_and_clone`; `git remote remove origin`;
  `task_sync 2>err.txt`. Expect: rc 0, `TASK_SYNC_STATUS=no-remote`,
  `TASK_SYNC_REASON=""`, `err.txt` **empty**.

- **Flagship: dirty data worktree blocks the pull (branch mode).**
  `setup_remote_and_clone`; `setup_branch_mode`; `cd "$TEST_MAIN_DIR"`;
  `_AIT_DATA_WORKTREE=".aitask-data"`;
  `git -C .aitask-data config rebase.autoStash false` (so the outcome does not
  depend on the developer's global config); commit one local file in
  `.aitask-data`; `advance_remote "remote_only.txt"`; then append to the
  **tracked** `init.txt` in `.aitask-data` without staging it.
  Expect: rc 0, `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=dirty_worktree`,
  `TASK_SYNC_UNPUSHED=1`, `TASK_SYNC_UNPULLED=0` (pins the documented
  stale-upstream caveat — `pull --rebase` refuses *before* it fetches, so the
  local upstream ref never moved), `err.txt` contains `1 local unpushed`,
  `last successful fetch`, and `ait syncer`, and
  `.aitask-data/remote_only.txt` **does not exist** (proof the sync really
  failed, so the assertions are not vacuous).

- **Wedged rebase (legacy).** `setup_remote_and_clone`; commit `conflict.txt`
  with content `local`; `advance_remote` a commit that writes `conflict.txt`
  with content `remote`; `task_sync 2>err.txt`.
  Expect: rc 0, `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=rebase_conflict`,
  `err.txt` contains `rebase --abort`. Counts are **not** asserted (mid-rebase
  HEAD makes them meaningless). Finish with
  `git rebase --abort 2>/dev/null || true` so the fixture is left recoverable.

- **Unreachable remote, one commit pending (legacy).** As Test 5's setup —
  commit `orphan.txt`, then `git remote set-url origin /nonexistent/path/repo.git`.
  Expect: rc 0, `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=remote_unreachable`,
  `err.txt` contains `1 local unpushed` and `./ait sync` (pins that the sync path
  gets the sync retry command, not `./ait git push`).

- **Unreachable remote, nothing pending (legacy).** Same, but with **no** local
  commit after the clone. Expect: rc 0, `TASK_SYNC_STATUS=failed`,
  `TASK_SYNC_REASON=remote_unreachable`, `TASK_SYNC_UNPUSHED=0`, `err.txt`
  **empty** — the noise negative control the offline case depends on.

- **Remote configured, current branch has no upstream (legacy).**
  `setup_remote_and_clone`; `git checkout -q -b data_no_upstream`;
  commit one file; `task_sync 2>err.txt`. (The remote is still configured, so
  `_task_push_has_remote` is true and the `no-remote` short-circuit does not
  fire.) Expect: rc 0, `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=no_upstream`,
  `TASK_SYNC_UNPUSHED=""` and `TASK_SYNC_UNPULLED=""` (both `rev-list` probes
  fail on the missing `@{upstream}` and must swallow it, not abort), and
  `err.txt` contains `counts unavailable` and `set-upstream-to`. This is the
  block that proves the path is neither silent, nor non-zero-exit, nor
  mis-classified.

- **Classifier reuse (pure unit, no git).** Fed straight to
  `_task_push_classify` with an **empty push argument**, proving the sync call
  shape does not change the verdict:
  - `("", "error: cannot pull with rebase: You have unstaged changes.")` → `dirty_worktree`
  - `("", "CONFLICT (content): Merge conflict in t42.md")` → `rebase_conflict`
  - `("", "fatal: '/nonexistent/repo.git' does not appear to be a git repository")` → `remote_unreachable`
  - `("", "There is no tracking information for the current branch.")` → `no_upstream`
  - `("fatal: The current branch data has no upstream branch.", "")` → `no_upstream`
    (the push side of the same new arm)

- **Hint table (pure unit).** `_task_push_reason_hint no_upstream` contains
  `set-upstream-to`; `_task_push_reason_hint remote_unreachable` contains
  `./ait git push` (default preserved); `_task_push_reason_hint remote_unreachable "./ait sync"`
  contains `./ait sync` and **not** `./ait git push`. Pins both directions of
  the shared table.

- **`aitask_pick_own.sh --sync` tokens (end-to-end).** Using the existing
  `setup_fake_aitask_repo` scaffold as Tests 8/15 do, plus
  `cp .aitask-scripts/lib/task_utils.sh .aitask-scripts/lib/pid_anchor.sh` and
  `.aitask-scripts/aitask_pick_own.sh` into the fixture (`--sync` mode touches
  only `task_sync` + `aitask_lock.sh --cleanup`, which is already `|| true`).
  - healthy fixture → stdout `SYNCED`, rc 0
  - `git remote set-url origin /nonexistent/repo.git` + one pending commit →
    stdout `SYNC_FAILED:remote_unreachable`, rc 0

Fixtures are built with `git init` / `git clone` / `mkdir` — never `cp -a` of a
repo that has worktrees (absolute `.git/worktrees` gitdir pointers make a copied
repo commit back into the original).

### `tests/test_chatlink_flow.sh` (`task_create` spy block, ~line 300)

Add a `mk_push_spy(dirpath, out, rc=0)` helper alongside the existing
`mk_spy_script` (same shape: record argv, print `out`, `exit rc`). Each case
below runs `create_task_from_payload(vp, repo_root=fixture, initiator_tag="U1",
audit=<fresh AuditSpy>, create_script=spy, push_argv=(str(push_spy),))` and
asserts on that spy's lines.

| Push spy stdout | Expected audit |
|---|---|
| `FAILED:dirty_worktree:3` | `audit.has("warning", "FAILED:dirty_worktree:3")` |
| `PUSHED` | **no** line matching `push failed` or `unparseable` |
| `NOTHING` | **no** line matching `push failed` or `unparseable` |
| `NO_REMOTE` | **no** line matching `push failed` or `unparseable` |
| `weird output` | `audit.has("warning", "unparseable")` |
| *(empty — the existing `("true",)` seam)* | **no** push warning |

`NOTHING` and `NO_REMOTE` get their own warning-free cases rather than riding on
the default-argv fixture: they are the two most frequent real outcomes (no
change to push; local-only repo), and a parser that mis-classified either would
emit a false audit warning on the common path while every other case still
passed.

**Default argv carries `--batch`:** a *separate* fixture dir containing an
executable `ait` stub that records its argv and prints `NOTHING`; call
`create_task_from_payload` with **no** `push_argv` and assert the recorded argv
is `["git", "push", "--batch"]` and that no push warning was audited. This must
not reuse the existing `fixture`, whose missing `ait` is exactly what makes the
current `"real create: push failure (no ait) audited + non-fatal"` check pass.

## Verification

```bash
bash tests/test_task_push.sh      # "N passed, 0 failed", exit 0
bash tests/test_task_git.sh       # existing task_sync/task_push integration
bash tests/test_chatlink_flow.sh
bash tests/test_crash_recovery_pid_anchor.sh   # exercises aitask_pick_own.sh
bash tests/test_lock_reclaim.sh
shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_pick_own.sh
```

**Live check — read-only on this repository.** Only the success path is exercised
against the real `.aitask-data`; nothing dirties or mutates it:

```bash
./.aitask-scripts/aitask_pick_own.sh --sync   # expect: SYNCED, exit 0, no warning
```

Every failure path is exercised in a **disposable clone** under the session
scratchpad, never in the live data worktree:

```bash
S="$SCRATCH/t1269_live" && rm -rf "$S" && mkdir -p "$S"
git clone -q "$(git -C .aitask-data remote get-url origin)" "$S/data"
# dirty it, run task_sync in that clone, observe SYNC_FAILED:dirty_worktree
rm -rf "$S"                                    # cleanup
```

Afterwards confirm the real worktree is untouched: `git -C .aitask-data status
--porcelain` prints nothing and `./ait git-health` reports clean.

**Harness-failure proof** (per "prove the test harness can fail"): after the
suites are green, temporarily stub `_task_sync_warn` to a no-op and confirm
`tests/test_task_push.sh` exits **1** naming the missing warnings; separately
revert `chatlink/task_create.py`'s token parsing and confirm
`tests/test_chatlink_flow.sh` fails on the `FAILED:` audit check. Restore both.
A *passing* negative control means the test is not discriminating.

## Risk

### Code-health risk: medium

- `task_sync` is on the hot path of every pick / explore / fold / review /
  pr-import, and the new probes are consumed via `x="$(probe)"` inside
  `aitask_pick_own.sh`, which runs `set -euo pipefail`; a probe leaking a
  non-zero status would abort the caller with no visible error · severity:
  medium · → mitigation: every probe ends in `|| true` and every branch is an
  explicit `if`/`case`; pinned by the no-remote, up-to-date and **no-upstream**
  blocks, which run `task_sync` on paths where `rev-parse` / `rev-list` /
  `remote` all return non-zero.
- Turning a previously silent failure into a per-pick warning risks noise for
  offline / single-machine users · severity: medium · → mitigation: the
  `no-remote` path and the "failed but nothing unreconciled" path stay silent,
  each pinned by an empty-stderr negative control.
- `TASK_SYNC_UNPULLED` is read from a possibly-stale local upstream ref and can
  under-report when the pull failed before fetching · severity: medium · →
  mitigation: the warning text itself carries the caveat ("remote side as of the
  last successful fetch — this sync may not have refreshed it"), it is restated
  in the globals' comment and the user docs, and the flagship test asserts
  `TASK_SYNC_UNPULLED=0` in exactly that state so the caveat is pinned rather
  than assumed.
- Adding a `no_upstream` arm and a `retry_cmd` parameter touches a classifier and
  hint table the push path already depends on · severity: low · → mitigation: the
  new arm's substrings do not overlap any existing arm (the `unknown` fallback
  fixture `"fatal: something nobody has seen before"` is unaffected), the
  parameter defaults to the current value so the push path is byte-identical, and
  both are pinned by pure unit assertions on each side.

### Goal-achievement risk: low

- Both defects are precisely located and the fix shape is already proven by
  t1265 in the same file · severity: low · → mitigation: none needed.
- The chatlink change depends on `ait git push --batch` printing its token on
  stdout while the warning goes to stderr; if that ever inverted, the parser
  would go quiet or spuriously warn · severity: low · → mitigation: all three
  success tokens plus the failure and unparseable shapes get their own
  assertions, and the default-argv test drives a real `ait`-shaped stub.
- The `no_upstream` arm depends on two literal git message substrings that could
  drift across git versions · severity: low · → mitigation: the substrings are
  confirmed empirically before the tests are written, both message shapes (pull
  and push) are pinned, and an unmatched message still lands in `unknown`, which
  warns and quotes git's own first line — no drift makes the path silent.
- `aitask_pick_own.sh --sync` gains a new stdout token · severity: low · →
  mitigation: no skill or script parses that token today (verified by grep); the
  success token is unchanged, and the new one is documented in the script header.

No mitigation tasks are proposed: each identified risk is covered by a test in
this task (the `set -e` probe safety and the noise regression by the empty-stderr
negative controls, the shared classifier/hint changes by the two-direction unit
tests, and the stale-count caveat by the flagship assertion plus the warning
wording itself).

## Post-implementation

Per **Step 9**: current-branch profile, merge target `main`, no worktree to clean
up; then archive via `./.aitask-scripts/aitask_archive.sh 1269`. `risk_evaluated`
is the only active gate.
