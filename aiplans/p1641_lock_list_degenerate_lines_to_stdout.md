---
Task: t1641_lock_list_degenerate_lines_to_stdout.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1641 — Keep `ait lock --list` stdout records-only

## Context

`list_locks()` in `.aitask-scripts/aitask_lock.sh` emits a machine-readable
record per lock on stdout:

```
t<id>: locked by <email> on <host> since <ts>
```

But four *degenerate* paths print human prose on that same stream via `info()`
(`.aitask-scripts/lib/terminal_compat.sh:19` — `echo -e "${BLUE}$1${NC}"`), so
the "no locks" cases put **ANSI-escaped prose onto a data channel**:

| line | `aitask_lock.sh` | condition |
|---|---|---|
| `No locks (no remote configured)` | 416 | `has_remote` false |
| `No locks (branch not initialized)` | 421 | `git fetch` of the lock branch fails |
| `No locks` | 427 | `rev-parse origin/<branch>^{tree}` fails |
| `No active locks` | 437 | branch readable, zero `*_lock.yaml` blobs |

Its sibling `warn()` already redirects to stderr (`>&2`); `info()` does not.

Any consumer must therefore strip ANSI escapes *and* pattern-match the record
shape, treating everything else as "no record" — otherwise a degenerate line
reads as a lock. Today's two consumers happen to survive:
`aitask_board.py::refresh_lock_map` (line 1862) regex-matches
`^t(\S+): locked by (.+?) on (.+?) since (.+)$` and drops non-matches; t1569_3
sidestepped the CLI entirely by reading the `origin/aitask-locks` tree. So this
is **latent**, not breaking — a trap for the next consumer, which is exactly the
kind of "parse the CLI" reach a future parallel-admission checker would make.

**Intended outcome:** stdout of `--list` carries lock records and nothing else.
The human-facing prose survives, on stderr, so `ait lock --list` still reads well
interactively.

**The contract is "recognized records", not "the lock tree is empty".**
`list_locks()` deliberately skips any `*_lock.yaml` blob with no `task_id:` field
(line 447 — `debug` + `continue`), and Test 13c pins that. So empty stdout means
*no recognized lock records*, which is **not** proof that the lock tree holds
nothing actionable — a malformed blob is invisible except under `--debug`. Every
wording below (help text, website docs, code comment) must say the weaker,
true thing; publishing "empty means no locks" would invite exactly the wrong
inference from the next consumer. Making malformed files reportable is a
separate behavioural question and is **not** in this task.

**All four degenerate paths are reachable** — verified, not assumed. The
`rev-parse` one (line 427) is the non-obvious case: `git fetch origin <branch>`
exits 0 while `origin/<branch>` does not resolve whenever `remote.origin.fetch`
is absent, since nothing then updates the remote-tracking ref. Confirmed
directly:

```
$ git config --unset remote.origin.fetch && git update-ref -d refs/remotes/origin/aitask-locks
$ git fetch origin aitask-locks -q ; echo $?          # 0
$ git rev-parse "origin/aitask-locks^{tree}"          # fatal: ambiguous argument … (128)
```

`has_remote()` is `git remote get-url origin` (line 55), which still passes in
that state, so the path is genuinely entered. That recipe is the fixture for it
in step 3.

## Scope decision on `check_lock()`

The task asks to "check `check_lock()` at the same time: it prints the whole
lock YAML to stdout". Reviewed (`aitask_lock.sh:378-401`): that YAML **is** the
record — the only stdout write is `git show "origin/$BRANCH:$lock_file"`, and
consumers parse it as data (`task-workflow` Step 7's pre-implementation
ownership guard parses the `hostname:` line; `aitask-pickweb` calls it for exit
status). There is no prose to remove, so **no behavioural change** — the same
contract simply gets written down and pinned by a test.

`lock_task()`'s `success "Locked task t$task_id"` (line 296) is on stdout
alongside its `LOCK_RECLAIM:` / `LOCK_HOLDER:` structured records — the same
defect class at a **different verb with a different consumer**
(`aitask_pick_own.sh`). Per the confirmed risk mitigation it is handled **in this
task** as the inline post-phase below — but **documentation-only**: no verb other
than `--list` changes its output here, because no test in this repo could detect a
regression in one if it did.

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_list_stdout_channel]` **Before touching `aitask_lock.sh`**,
   write the new/rewritten Test 13b assertions (step 3 below) — `assert_eq ""
   "$stdout"` plus the stderr `assert_contains_ci` — and run
   `bash tests/test_task_lock.sh`. Confirm the stdout-purity assertion **FAILS**
   against the current unfixed code and that the failure names that assertion.
   Only then proceed to step 1. If it passes unfixed, the assertion is vacuous
   (wrong capture, wrong variable) — fix the test before fixing the script.

### 1. `.aitask-scripts/aitask_lock.sh` — route the four lines to stderr

Add one named helper immediately above `list_locks()`, next to the existing
`_lock_field()` helper, so the four sites share a single documented decision
rather than four bare `>&2` redirects:

```bash
# Degenerate "no locks" messages are prose for humans, not records. --list's
# stdout is a machine-readable channel — one `t<id>: locked by <who> on <host>
# since <ts>` line per RECOGNIZED lock — and info() wraps its argument in ANSI
# color escapes, so emitting these on stdout forces every consumer to strip
# escapes and pattern-match the record shape just to tell "no locks" from a
# lock. Empty stdout means "no recognized lock records" — NOT that the lock
# tree is empty: a blob with no task_id: is skipped below and is visible only
# under --debug (t1641).
_list_note() { info "$1" >&2; }
```

Then swap the four `info "…"` calls in `list_locks()` for `_list_note "…"`
(lines 416, 421, 427, 437). Wording and exit statuses are unchanged — all four
paths still `return 0`.

Also extend the header comment on `check_lock()` (line ~378) with the same
contract, stated as a constraint on future edits: stdout is the lock record
(raw YAML), consumers parse it, so no informational prose may be added there.

### 2. `--help` and website docs — state the contract

Both must state the **weaker, true** contract (see Context): *only recognized
lock-record lines are written to stdout; empty stdout means no recognized
records, not that the lock branch is empty; informational messages go to stderr.*

- `aitask_lock.sh` `show_help()` (line ~674): extend the `--list` row accordingly.
  Match the existing style of the `--cleanup` row, which already documents its
  exit codes and "Failures warn on stderr".
- `website/content/docs/commands/lock.md` (the `--list` row at line 27): document
  the record shape and the stdout/stderr split, so a consumer has a contract to
  code against — including the caveat that an unrecognized `*_lock.yaml` blob is
  skipped and surfaces only under `--debug`. Current-state prose only, per
  `aidocs/framework/documentation_conventions.md`.

### 3. `tests/test_task_lock.sh` — pin the split in both directions

The stdout-purity assertions are the point of the change; the stderr assertions
stop the messages from being silently deleted instead of moved.

- **Test 13b** (empty lock branch, line ~509) currently captures with
  `2>/dev/null` and asserts stdout *contains* `No active locks` — it inverts
  after the fix. Rewrite to capture the streams separately:
  `assert_eq "" "$stdout"` (exact, not `contains` — a substring match is what
  lets this class hide) plus `assert_contains_ci … "No active locks" "$stderr"`.
- **New cases — one per remaining degenerate path.** All four exits get a
  fixture; none may be left to a reachability argument, or a future edit can put
  that one line back on stdout with the suite still green. Each asserts empty
  stdout + the message on stderr:
  - branch-not-initialized: paired repos, no `--init` (the `git fetch` failure
    path at line 421);
  - **`rev-parse` failure (line 427)** — the path with no coverage today. Fixture
    (verified reachable, see Context): `setup_paired_repos`, `--init`, then
    ```bash
    git -C "$dir/local" update-ref -d refs/remotes/origin/aitask-locks
    git -C "$dir/local" config --unset remote.origin.fetch
    ```
    `has_remote` still passes and `git fetch origin aitask-locks` still exits 0,
    so `list_locks` reaches the `rev-parse` guard and emits `No locks`. Assert
    empty stdout, `No locks` on stderr, exit 0. Add a comment naming *why* the
    two git commands put the repo in that state, so the fixture is not
    "simplified" back into unreachability later.
  - no-remote: the existing Test 22 fixture shape (`TMPDIR_22`, line ~755).
    Test 22 itself uses `2>&1` so it stays green either way — tighten it to
    assert stdout is empty and the prose is on stderr, otherwise it cannot
    distinguish the fix from the bug.
- **Unrecognized-blob contract:** extend Test 13c (stray `notalock_lock.yaml`) to
  assert that stdout carries the real record and *nothing* for the stray blob —
  pinning "empty means no recognized records" as a deliberate, documented
  behaviour rather than an accident.
- **Positive control:** Test 13 (line ~470) and Test 13d already assert records
  on stdout; add an explicit "records still go to stdout" assertion to 13b's
  neighbourhood is unnecessary — instead assert in Test 13 that stdout contains
  *only* record lines (every line matches the board regex already extracted at
  line 574). This is what proves the redirect did not over-reach and swallow
  records too.
- **`check_lock` contract:** extend Test 6 (line ~165, unlocked task) to assert
  stdout is exactly empty, and Test 5 (line ~154, locked task) already asserts
  the YAML fields — together these pin "records only, nothing when absent".

Note `tests/test_task_lock.sh` bodies run at top level (not in `( … )`
subshells) for these cases, so no `assert_counters_init` opt-in is needed; keep
new cases in the same style as their neighbours.

### 4. Consumer check (no change expected)

`refresh_lock_map` (`aitask_board.py:1862`) reads only `result.stdout` and
regex-filters, so removing prose from stdout is a strict narrowing — it cannot
regress. `tests/lib/board_fixture.py` stubs the call out entirely. No board-side
edit; verified, not assumed.

### Post-phase (risk mitigations)

1. `[sweep_lock_stdout_prose_sites]` **Documentation-only — this phase changes no
   verb's output.** t1641 targets `--list`; `aitask_pick_own.sh` captures `2>&1`
   and so cannot detect a regression in any other verb's stream split, and the
   direct-CLI callers of `ait lock <task>` / `--init` / `--cleanup` are humans
   with no regression test between them. Changing a second verb's output on that
   evidence would be unverifiable. So: audit and **write the contract down**,
   change nothing.
   - Write a short per-verb stdout/stderr contract comment at each verb, stating
     what its stdout is (records, prose, or both) and who consumes it:
     - `lock_task` (`success "Locked task t$task_id"`, line 296) — stdout carries
       **both** prose and the `LOCK_RECLAIM:` / `LOCK_LIVE_HOLDER:` /
       `LOCK_UNVERIFIABLE_HOLDER:` / `PRIOR_LOCK:` / `LOCK_HOLDER:` records.
       Consumer `aitask_pick_own.sh:359,441` merges `2>&1` and prefix-greps, so it
       is insensitive to the split — **and line 386 parses the *prose*
       `already locked by <email>`** as a legacy fallback when no `LOCK_HOLDER:`
       line is present. That prose is load-bearing; the comment must say so, so a
       later "obvious" cleanup does not silently break the fallback.
     - `init_lock_branch` (108/112/121) and `cleanup_locks` (565/582) — prose
       only; no structured record shares their stdout (`--cleanup`'s verdict
       rides exit codes 11/12). The comment records that, so a future record
       added to either verb does not inherit the mix by default.
   - **Precondition for any future behavioural change here** (record it in the
     comment): an explicit per-verb stdout contract plus a direct-CLI regression
     test for that verb must exist *first*. If the audit finds a change that
     genuinely warrants making, do **not** make it in this task — record it at
     Step 8d as a follow-up carrying that precondition.
   - Record the per-verb outcome (documented; nothing changed) in the Final
     Implementation Notes, so the "same class elsewhere" residual is explicitly
     closed as *documented*, not silently dropped.

## Verification

```bash
bash tests/test_task_lock.sh                 # PASS summary, exit 0
bash tests/test_pick_own_scoped_commit.sh    # post-phase: lock acquisition path intact
shellcheck .aitask-scripts/aitask_lock.sh
bash -n .aitask-scripts/aitask_lock.sh
```

Manual, in this repo (which has a remote and a lock branch):

```bash
./ait lock --list 1>/dev/null                # prose only, on stderr
./ait lock --list 2>/dev/null                # recognized records only
./ait lock --list                            # unchanged for a human reader
```

Negative control: revert one `_list_note` back to `info` and confirm the new
stdout-purity assertion fails — a passing suite against the unfixed line would
mean the assertion is vacuous.

Board smoke: `ait board` still shows lock badges for any currently locked task
(exercises `refresh_lock_map` against the narrowed stdout).

## Risk

### Code-health risk: low
- Moving the four messages to stderr silences them for any caller that captures
  **only** stdout and shows it to a human. Verified there is no such caller today
  (`refresh_lock_map` parses records and drops non-matches; no shell caller reaches
  `--list`), so this is a contained, reversible narrowing · severity: low ·
  → mitigation: TBD
- Test 13b must be rewritten from `assert_contains_ci "No active locks"` on stdout
  to a stdout/stderr split; a loose rewrite would leave the fix unpinned and the
  suite green against the unfixed code · severity: low ·
  → mitigation: inline pre-phase characterize_list_stdout_channel
- The same defect class remains at three other `aitask_lock.sh` sites that mix
  prose into a stdout carrying records (`lock_task` line 296 `success`, plus
  `init_lock_branch` / `cleanup_locks`). The post-phase documents rather than
  changes them, so the residual is knowingly carried, not closed · severity: low ·
  → mitigation: inline post-phase sweep_lock_stdout_prose_sites
- Accepted residual: empty `--list` stdout does not prove the lock branch is
  clean — a `*_lock.yaml` blob with no `task_id:` is skipped and visible only
  under `--debug`. Documented as the contract and pinned by the extended Test
  13c; making malformed blobs reportable is deliberately not in this task ·
  severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- The task asks to "check `check_lock()` at the same time … a separate but
  related shape question"; this plan resolves it as **review-only, no behavioural
  change** (its stdout is already records — raw lock YAML — with no prose). If the
  user intended an actual shape change there, the task ships incomplete on that
  half · severity: medium · → mitigation: TBD
- The task offers two fixes — stderr, or emit nothing. This plan picks stderr to
  preserve the interactive UX; "emit nothing" would satisfy the same stdout
  contract with different human-facing behaviour · severity: low ·
  → mitigation: TBD

### Planned mitigations
- timing: pre-phase | name: characterize_list_stdout_channel | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — rewritten Test 13b could leave the fix unpinned | desc: Land the stdout-purity assertion first and confirm it fails against the unfixed script before applying the redirect.
- timing: post-phase | name: sweep_lock_stdout_prose_sites | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the same prose-on-a-record-stream class remains in lock_task / init_lock_branch / cleanup_locks | desc: Documentation-only audit of those three verbs — write a per-verb stdout/stderr contract naming each verb's consumer and the load-bearing prose at aitask_pick_own.sh:386, plus the precondition (per-verb contract + direct-CLI regression test) any future behavioural change there must meet. Changes no output.

## Step 9 (Post-Implementation)

Standard closure: commit as `bug: Keep ait lock --list stdout records-only
(t1641)`, run the `risk_evaluated` gate (materialized active set for this task),
then merge/archive per Step 9.
