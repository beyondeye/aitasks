---
Task: t2376_shadow_q_harness_budget_cross_process_lock.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2376 — shadow_q harness: cross-process batch lock for the paid commands

## Context

`aidocs/benchmarks/shadow_q/harness.py` `Budget` serializes reservations with an
in-process `threading.Lock` only. Its fsynced journal
(`runs/<batch>/budget_journal.jsonl`) makes the invocation cap survive a restart
of **one** process. It does not hold across two processes running at the same
time: each calls `Budget.recover()`, reads the same `used`, and both `acquire()`
the same next slot, so the cap can be exceeded (spawned from t2368's review).

t2368's runner (`adhoc_live_check.py`) works around this with its own
`BatchLock`: an exclusive, non-blocking `flock` on
`runs/<batch>/budget_journal.jsonl.lock`, taken before `recover()` and held for
the whole run. The harness's own paid commands (`smoke`, `pilot`, `judge`,
`rejudge`, all built through `_experiment()`) take no lock.

Goal: move the lock into the harness, make every paid harness command hold it
for its whole lifetime, and have the runner use the harness's lock, so one lock
covers both tools. Two further guarantees come with it:
- switching entry points cannot raise a batch's approved invocation cap;
- the lock, now reachable from any `--batch` value, cannot create or truncate
  files outside `runs/`.

The existing batches, `pilot` and `t2368`, both satisfy the new name rule. Out of scope: the token/cost headroom note in the task (a
documented stop-launch threshold, not a defect), so `HeadroomBudget` stays.

## Design

The lock belongs to the **command**, not to `Budget`. Putting it in
`Budget.recover()` would make a second `Budget` on the same journal in one process
fail, which breaks `test_cap_and_pending_reservations_survive_a_restart` (it
builds two budgets in one process to stand in for a restart). `flock` locks belong
to the open file description, so a second `BatchLock` in the same process is
refused too, which is what lets the tests exercise the conflict in-process.

The runner's refusal shape stays the same: `RUN_REFUSED:<reason>`, exit 1, nothing
recovered, nothing launched.

**The lock alone does not protect the runner's approved cap.** `_experiment()`
always uses `limits.json` `pilot.invocation_cap` (80). So a `pilot --batch t2368`
run after the runner exits would recover the runner's journal (`used` ≤ 24) and
could spend up to 80. The runner's approved cap is 24, and its other thresholds
differ as well. The harness therefore keeps a small registry of **runner-owned
batches**, and its paid commands refuse those batches outright, before any lock
or file is created. Each entry point keeps the cap it was approved for, and
switching entry points cannot raise it. This covers the existing t2368 journal,
which records no cap. (Pinning the cap inside the journal was rejected: that
journal has no pinned cap, so whichever entry point wrote the first pin would
win.)

**Batch names come from the command line.** `RUNS_PUBLIC / args.batch` accepts an
absolute path or `..`, and the lock is now created *before* store validation. So
the batch name is validated before any path is built. The lock file is also
opened without truncation and without following symlinks.

## Steps

### 1. `aidocs/benchmarks/shadow_q/harness.py`

- `import fcntl` and `import functools`.
- Add a `JOURNAL_NAME = "budget_journal.jsonl"` constant and a
  `batch_journal(batch) -> Path` helper. It returns
  `RUNS_PUBLIC / batch / JOURNAL_NAME` and reads `RUNS_PUBLIC` at call time, so
  the tests' patching still applies. Both `_experiment()` and the runner use it.
  It **validates first** and raises `ValueError` when:
  - the name does not match `^[A-Za-z0-9][A-Za-z0-9._-]*$` (this rules out
    absolute paths, `/`, `..` segments and a leading `.`);
  - **the batch name is not the journal's identity.** Let
    `root = RUNS_PUBLIC.resolve()` and `want = root / batch / JOURNAL_NAME`.
    Refuse unless `Path(RUNS_PUBLIC / batch / JOURNAL_NAME).resolve() == want`.
    Being contained in the root is not enough: a batch-directory symlink to
    *another in-root batch* (`runs/foo -> t2368`) or a journal symlink between
    two in-root batches both resolve inside the root, yet they would let the raw
    name `foo` skip the owned-batch check, or let two lock paths guard one
    journal. Requiring the resolved path to equal the lexical one removes every
    symlink alias, inside the root or outside it. A symlinked `RUNS_PUBLIC`
    itself stays fine, because `root` is resolved;
  - the journal exists with `st_nlink != 1`. A hard link is the one alias
    `resolve()` cannot see.

  The name is therefore the one identity that the ownership check, the journal
  path and the lock path all derive from. The lock file is opened with
  `O_NOFOLLOW`, so it cannot be redirected either.
- Add the runner-owned batch registry:
  `RUNNER_BATCHES = {"t2368": ("adhoc_live_check.py", 24)}`, mapping the batch to
  its owning runner and that runner's approved cap. Add a comment: a paid harness
  command never spends from these batches, because their approved cap and
  thresholds belong to the runner.
- Add the lock in the `Budget` section, moved from the runner with the same
  semantics and the same lock-file name (`<journal>.lock`, already in
  `.gitignore`):

  ```python
  class BatchBusy(RuntimeError):
      """Another process (or another command in this one) holds the batch lock."""

  class BatchLock:
      """Exclusive, non-blocking flock for one batch's budget journal.

      The journal makes the cap durable across restarts of one process; this lock makes
      it hold across concurrent processes: recovery and every reservation of a batch
      happen in the one lock holder. flock locks belong to the open file description,
      so a second BatchLock is refused even inside the same process, and the kernel
      drops the lock when the holder dies (no stale lock file to clean up).
      """
      _held: set[str] = set()   # lock paths this process holds

      def __init__(self, journal): self.path = Path(str(journal) + ".lock"); self.fd = None
      def __enter__(self):  mkdir parents;
                            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
                            # no O_TRUNC: an existing file is never emptied;
                            # O_NOFOLLOW: a planted symlink fails with OSError (ELOOP)
                            flock(fd, LOCK_EX | LOCK_NB);
                            on BlockingIOError: close fd, raise BatchBusy(f"another process holds {self.path}");
                            any other OSError (open or flock): close fd if open,
                              raise BatchBusy(f"cannot lock {self.path}: {exc}")  # fail closed
                            BatchLock._held.add(str(self.path)); return self
      def __exit__(self, *_): discard from _held; LOCK_UN; os.close(fd)
      @classmethod
      def held(cls, journal) -> bool: return str(journal) + ".lock" in cls._held
  ```

  Also add a short note to the `Budget` docstring: the journal is durable for one
  process at a time, and concurrent processes are serialized by `BatchLock`,
  which every paid command holds.
- Add the decorator `_batch_locked(cmd)`. Before it builds or creates anything:
  - it calls `batch_journal(args.batch)`. On `ValueError` it prints
    `RUN_REFUSED:invalid batch name <repr>` and returns 1;
  - if `args.batch in RUNNER_BATCHES`, it prints
    `RUN_REFUSED:batch <b> belongs to <runner> (approved cap <n>); run it through that runner`
    and returns 1.

  Then it takes `BatchLock(journal)` around the whole command body. On `BatchBusy`
  it prints `RUN_REFUSED:<exc>` and returns 1. Apply it to
  `cmd_smoke`, `cmd_pilot`, `cmd_judge` and `cmd_rejudge`. Because it wraps the
  body, the lock is taken before `_experiment()` (and so before `recover()`) and
  held through the last `_save_budget`.
- Guard in `_experiment()`, before `recover()`: if
  `not BatchLock.held(journal)`, raise
  `RuntimeError("_experiment() needs the batch lock: decorate the command with @_batch_locked")`.
  This fails closed, so a future paid command added without the decorator crashes
  in its first test instead of running unlocked.

### 2. `aidocs/benchmarks/shadow_q/adhoc_live_check.py`

- Delete its `RunnerBusy` and `BatchLock` classes and the `fcntl` import. Keep
  the names as re-exports of the harness's classes:
  `BatchLock = H.BatchLock` and `RunnerBusy = H.BatchBusy`, with a one-line
  comment saying the lock is the harness's own, shared with
  `smoke`/`pilot`/`judge`/`rejudge`. The existing test refers to `A.BatchLock` /
  `A.RunnerBusy`.
- `cmd_run`: compute the journal **inside** the refusal handling.
  `batch_journal()` now raises `ValueError` for an aliased or hard-linked journal,
  and today's `journal = …` line sits before the `try:`, so the error would escape
  as a traceback. The new shape is:

  ```python
  try:
      journal = H.batch_journal(BATCH)
  except ValueError as exc:
      print(f"RUN_REFUSED:{exc}")
      return 1
  pub = journal.parent
  ```

  `pub` is derived from the validated journal, not from a second, unvalidated
  join. The existing `try: with BatchLock(journal): … except RunnerBusy` block
  follows unchanged. It still takes the lock before `make_budget()` →
  `recover()`, and still prints `RUN_REFUSED:{exc}`. Both refusals happen before
  `resolve_store`, before recovery and before any launch.
- The runner keeps `INVOCATION_CAP = 24` as its own constant. A test pins that it
  equals the cap in `H.RUNNER_BATCHES[BATCH]`, so the two can never drift silently.
- Module docstring: "one runner process at a time" becomes "one process at a time
  per batch: the harness's batch lock, shared with the harness commands".

### 3. `tests/test_shadow_q_harness.py`

Existing `test_second_runner_is_refused_while_the_lock_is_held` and
`test_cap_and_pending_reservations_survive_a_restart` stay unchanged and must stay
green. Add a `TestBatchLock(Base)` class.

**Shared stubs, applied in BOTH processes.** The same stubs the child uses are
also installed in the parent, by `setUp` with restore in `tearDown`:
`require_manifest`, `resolve_agents`, `environment_record` and `store_commit`.
The parent also gets the recovery spy. The real `require_manifest` rejects the
synthetic store with `SystemExit` *before* `recover()`. Without the parent stub,
a contender that wrongly gets past the lock (the late-lock mutant) would die in
the manifest check rather than reach the spy, and the test would go red for the
wrong reason. With the stubs, every contender that is not refused reaches
`recover()`, and the spy reports it.

**Module identity.** The child imports from the test module's own `SQ` path,
passed as an argument and never hard-coded. It prints `harness.__file__`, and the
test asserts that this equals `H.__file__`. So parent and child always exercise
the same copy, which is also what makes the mutation runs below trustworthy.

The tests:

- **`test_two_harness_commands_on_one_batch`**: a real second process.
  - Before the child starts, write `runs/b/answers.json` = `[]` into the
    synthetic private store.
  - A child `python3 -c` process imports `harness` and `judge` from `shadow_q`
    and points `RUNS_PUBLIC` at the case directory. Stand-ins replace only the
    parts that need the private store, real agents or judging output:
    - `require_manifest`, `resolve_agents`, `environment_record` and
      `store_commit`;
    - `H.rebuild_scores_json`, replaced by `lambda *a: {}`; the real one reads
      `scores.jsonl` and the private blind map;
    - `judge.judge_batch`, replaced by a function that prints `HOLDING`
      (flushed), blocks on `sys.stdin.readline()`, and then returns
      `{"calibration": {}}`, the key `cmd_judge` prints.

    The child then runs the real
    `H.main(["--store", <store>, "judge", "--batch", "b"])` (`--store` is a
    top-level option, so it goes before the subcommand). The real decorator,
    `_experiment()` and `recover()` therefore run in the child.
  - The parent waits for `HOLDING` (with a timeout), then snapshots the journal
    bytes. The child's `recover()` wrote the baseline.
  - **Recovery spy.** For the parent-side contenders, wrap `H.Budget.recover` in
    a spy that records each call and raises. A lock taken *after* recovery would
    then show up as a spy call even though replaying an existing journal leaves
    its bytes unchanged.
  - The parent then runs `H.main([...])` in-process for each of `smoke`,
    `pilot`, `judge`, and `rejudge --trials x --tag t` on batch `b`. Each must:
    - return 1;
    - print `RUN_REFUSED`;
    - make zero recovery-spy calls;
    - leave the journal byte-identical (no write);
    - launch no fake CLI (no `state/*.count`).
  - While the child still holds batch `b`, `H.BatchLock(batch_journal("other"))`
    can be acquired, which shows the lock is per batch.
  - Release: write a newline to the child's stdin. The child must exit 0, and
    its stdout must carry `CALIBRATION:` and `BUDGET:`. That proves the child ran
    the whole command under the lock, not that it crashed early. Afterwards
    `H.BatchLock` on batch `b` is acquirable, because the lock was released.
- **`test_runner_and_harness_share_one_lock`**: `A.BatchLock is H.BatchLock` and
  `A.RunnerBusy is H.BatchBusy`. While `A.BatchLock(H.batch_journal(A.BATCH))` is
  held, `A.cmd_run` is refused with `RUN_REFUSED`. (This is the same lock a
  harness command on any batch takes.)
- **`test_switching_entry_points_cannot_raise_the_approved_cap`**:
  - Run `A.make_budget()` on the t2368 journal and fill it to the runner's cap
    (24 reservations with usage), as `test_cap_and_pending…` does.
  - Then, with no lock held, run `H.main([...])` for each of `smoke`, `pilot`,
    `judge`, `rejudge` with `--batch t2368`. Each must:
    - return 1;
    - print `RUN_REFUSED` and `belongs to adhoc_live_check.py`;
    - make zero recovery-spy calls;
    - leave the journal byte-identical;
    - launch no fake CLI;
    - create no lock file. A pre-existing lock file from the runner run is fine;
      only its content and mtime must be unchanged.
  - Also assert `A.INVOCATION_CAP == H.RUNNER_BATCHES[A.BATCH][1]`.
- **`test_batch_names_cannot_leave_the_runs_root`**:
  - For `/abs/x`, `../x`, `a/../../x`, `.hidden`, `a/b` and an empty name, each
    paid command returns 1 with `RUN_REFUSED:invalid batch name`, and nothing is
    created outside, or anywhere under, the case dir's runs root.
  - **Aliases are refused (each made with real temporary links):**
    - a batch dir that is a symlink to a directory outside `RUNS_PUBLIC`;
    - `runs/foo -> runs/t2368`: `smoke`/`pilot`/`judge`/`rejudge --batch foo`
      are refused, the t2368 journal is byte-identical, recovery-spy calls are
      zero, and no fake CLI is launched. Without the identity check this alias
      would get past the owned-batch rule;
    - `runs/b2/budget_journal.jsonl -> ../b1/budget_journal.jsonl`: `--batch b2`
      is refused while nothing holds `b1`'s lock. Without the check, two lock
      paths would guard one journal;
    - a hard link `runs/b3/budget_journal.jsonl` to `b1`'s journal is refused
      (`st_nlink`).
- **`test_runner_refuses_an_aliased_journal`**: the runner's own path.
  - Make `runs/t2368/budget_journal.jsonl` a symlink to another batch's journal.
    In a second case, make it a hard link to one.
  - `A.cmd_run(args)` must return 1 and print `RUN_REFUSED`, with no traceback
    (the call itself must not raise).
  - Recovery-spy calls must be zero, and `A.make_budget` (also spied) must never
    be called.
  - No fake CLI is launched, no lock file is created, and the link target's
    bytes are unchanged.
  - A pre-fix control is listed below.
  - A pre-existing lock file with content keeps its bytes after a
    `BatchLock` enter and exit (no truncation).
  - A lock path that is a planted symlink raises `BatchBusy` and leaves the
    symlink target unchanged.
- **`test_experiment_refuses_without_the_batch_lock`**: calling
  `H._experiment(args)` directly raises `RuntimeError` naming the decorator.
  Nothing is written to the journal.

Pre-fix controls (verification only, not committed): run the new tests against
mutant scratch copies of the `shadow_q` dir in the scratchpad. Never use
`git restore` or a stash (the worktree is shared and dirty). Each mutant must go
red on the assertion named here:

| mutant | must fail |
|---|---|
| `@_batch_locked` removed from `cmd_smoke` | two-commands test, `smoke` refusal (the guard's `RuntimeError` replaces `RUN_REFUSED`) |
| lock taken inside `_experiment()` **after** `recover()` (decorator and guard dropped) | two-commands test, recovery-spy assertion |
| `RUNNER_BATCHES` check removed | cap-switch test, `RUN_REFUSED`/no-recovery assertion |
| batch-name validation removed | batch-name test |
| `os.open` with `O_TRUNC` and no `O_NOFOLLOW` | the no-truncation and symlink assertions |

| batch-identity check removed (containment only) | alias tests (`foo -> t2368`, journal symlink) |
| runner's `batch_journal` call moved back before any `ValueError` handling | runner-alias test (`ValueError` escapes the call instead of `RUN_REFUSED`) |

**Mutation setup.** The test file inserts
`Path(__file__).resolve().parents[1] / "aidocs/benchmarks/shadow_q"` at
`sys.path[0]`, so putting a copy first on `sys.path` would not work. Instead each
mutant is a scratch tree that mirrors the repo layout, under the session
scratchpad: `<m>/aidocs/benchmarks/shadow_q/` (a full copy of the dir, then
mutated) and `<m>/tests/test_shadow_q_harness.py` (a copy). Run with
`python3 <m>/tests/test_shadow_q_harness.py TestBatchLock`. The test's own `SQ`
then resolves to the mutant, in both the parent and, through the passed path,
the child. Two checks confirm the wiring:
- before reading a mutant's result, a one-line probe prints `H.__file__` under
  that driver and confirms it lies inside `<m>`;
- the module-identity assertion above confirms that the child imported the same
  file.

The unmutated copy must pass under the same driver (positive control). Each
mutant must fail on **its named assertion**, read from the failure output, not
merely fail. The real modules are never edited for this.

### 4. `aidocs/benchmarks/shadow_q/README.md`

Right after the table, add a short "Budget across processes" paragraph:

- Every paid command (`smoke`/`pilot`/`judge`/`rejudge`) and
  `adhoc_live_check.py run` holds an exclusive per-batch lock
  (`runs/<batch>/budget_journal.jsonl.lock`) for its whole run. A second process
  on the same batch is refused with `RUN_REFUSED`, so the invocation cap holds
  across concurrent processes.
- A batch owned by a runner (`t2368`, cap 24) is refused by the harness's own
  paid commands. Its approved cap is the runner's, so switching entry points
  cannot raise it.
- Batch names are restricted to `[A-Za-z0-9._-]`. A batch directory or journal
  that is a symlink or hard link is refused, so a batch name always names exactly
  one journal and one lock.

## Verification

- `python3 tests/test_shadow_q_harness.py`: all tests pass (the baseline had 112;
  the new run should have 118). Run it with the default `TMPDIR`, because a
  redirected `TMPDIR` under a `.claude` ancestor trips the sandbox ancestor check.
- `python3 tests/test_shadow_scan_sessions.py`: still green (it imports the same
  modules).
- Each pre-fix control mutant above goes red on its named assertion, and the
  unmutated copy goes green under the same driver (positive control).
- `python3 aidocs/benchmarks/shadow_q/check_public.py --staged` before the commit.
- No paid session is launched by any of this. Everything runs on fake CLIs.

## Step 9 (Post-Implementation)

Commit the code (`bug: … (t2376)`) with explicit paths only. Commit the plan via
`./.aitask-scripts/aitask_task_commit.sh`, then archive per the workflow's Step 9.

## Risk

### Code-health risk: low
None identified.

The change is confined to the benchmark harness, its runner and its tests. No
framework script or skill reads them. The one coupling it adds (a paid command
must hold the lock) is enforced in code by the `_experiment()` guard, not left as
a convention.

### Goal-achievement risk: low
None identified.

The lock is the runner's proven `flock` mechanism. It now covers every paid
harness command, and the new test exercises a real second process against one
batch. The review found two gaps that the lock alone leaves, and the plan closes
both:
- the runner-owned batch's approved cap (closed by the owned-batch refusal);
- unrestricted batch names reaching filesystem creation before validation
  (closed by name validation and a non-truncating, no-follow open).

A second review found symlink and hard-link aliases that would let the owned-batch
rule, or the lock, be bypassed. Those are closed by the batch-name identity check
(resolved journal path == lexical path, `st_nlink == 1`).

Each fix has its own test and pre-fix control.
