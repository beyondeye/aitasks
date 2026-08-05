---
Task: t1262_beginprocedure_attempt_counter_advances_by_2_per_attempt.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
Output branch: main
---

# t1262 — `begin-procedure` attempt counter advances by 2 per attempt

## Context

The gate ledger records one `attempt=<N>` per gate run. Three places compute
that number when the caller does not supply one, and all three derive it as
"count of **every** `gate:<name>` marker line already in the file, + 1":

| site | file |
|---|---|
| `cmd_begin_procedure` | `.aitask-scripts/aitask_gate.sh:1036-1046` |
| `cmd_append` auto-increment | `.aitask-scripts/aitask_gate.sh:243-256` |
| `build_block` auto-compute (python backend) | `.aitask-scripts/lib/gate_ledger.py:321-324` |

That is wrong because a **completed** attempt leaves **two** markers: the
`running` block `begin-procedure` opens, plus the terminal block the gate skill
appends to close it. So the counter advances by 2 per attempt — observed live on
scratch task t1255 during the t635_27 verification: ATTEMPT **1 → 3 → 5**.

The same rule inflates `cmd_append`'s auto path whenever `attempt=` is absent —
how the workflow records human gates (`aitask_gate_record.sh <t> plan_approved
pass type=human`) and how `gate_orchestrator._handle_human` (line 374) records an
observed signal. A human gate that sat `pending` before passing is numbered
`attempt=2` for its first and only real attempt.

This is a **ledger-accuracy** defect, not a gating one. The retry budget is
unaffected and stays untouched: `_attempts_used()` (`gate_orchestrator.py:80-82`)
counts terminal `fail`/`error` runs, and the budget checks at lines 184/199 are
already correct.

`aidocs/gates/aitask-gate-framework.md:444-446` already illustrates the intended
rule — a `running` block and its terminal closer carrying the **same**
`attempt=1`. Line 327 of the same doc asserts the opposite ("the (attempt)
counter increments per append"); that sentence seeded the bug.

### Three lifecycle defects the naive fix would leave (or create)

Verified empirically on a scratch fixture before writing this plan.

**(a) No single-live-run invariant.** `cmd_begin_procedure` neither rejects nor
reserves against an already-open run, and it computes its count *outside*
`cmd_append`'s lock. Two begins with no terminal between them — a crash/resume
(`procedure-gates` still lists a non-`pass`/`skip` gate, so Step 8 re-dispatches)
or a concurrent launch — today produce:

```
> **🔄 gate:docs_updated** run=2026-08-05T16:08:59Z status=running attempt=1 type=machine
> **🔄 gate:docs_updated** run=2026-08-05T16:08:59Z status=running attempt=2 type=machine
```

Note the **identical run id**: `date -u +%Y-%m-%dT%H:%M:%SZ` has 1-second
resolution. Under plain terminal-counting both blocks would also be `attempt=1`,
i.e. byte-identical — strictly worse than today. Terminal-counting alone is
therefore **not a sufficient fix**.

**(b) Terminal statuses that carry no number.** The auto guard is
`status in (pass, fail)` only, so a direct `skip`/`error` append emits no
`attempt=` while still consuming a number under the terminal set:

```
> **⏭ gate:docs_updated** ... status=skip type=machine          # no attempt=
> **⚠ gate:docs_updated** ... status=error type=machine         # no attempt=
> **❌ gate:docs_updated** ... status=fail attempt=3 type=machine
```

**(c) Correction markers.** `gate_orchestrator.reconcile_terminal:303-305`
appends a **fresh-run-id** `error` when a verifier's self-reported status
contradicts its exit code, reusing the same explicit `attempt`. One dispatch
therefore leaves two terminal markers. (`_attempts_used` counts `fail` *and*
`error`, so it charges that dispatch twice as well — the ordinal and the budget
stay in lockstep here; neither is "right" and they must not be claimed equal by
accident.)

### The rules this change establishes

1. **Ordinal.** `attempt` for a new run = (terminal runs already recorded for
   that gate) + 1, terminal = `pass | fail | skip | error`. `running`/`pending`
   are in-progress bookkeeping and never consume a number, so a `running` block
   and the terminal block closing it share one attempt — the ledger the design
   doc illustrates.
2. **Single live run.** A gate has **at most one live run** (a `running` marker
   with no terminal marker for the same run id). `begin-procedure` **adopts** an
   existing live run — re-printing its `RUN_ID`/`ATTEMPT` and appending nothing —
   instead of opening a second. The check and the append happen under **one**
   hold of the per-task lock.
3. **Every terminal status is numbered.** The auto path fires for all four
   terminal statuses, not just `pass`/`fail`, so no terminal marker consumes a
   number without carrying one.
4. **A correction marker is its own terminal run.** It counts. This is
   deliberate and matches what the retry budget already charges.

Rule 1 is the ordinal; `_attempts_used` is budget consumption. They answer
different questions and coincide on the common path — that is stated at the
source rather than assumed.

## Implementation

### 1. `aitask_gate.sh` — constant, predicate, one ledger-state helper

After `VALID_STATUSES` (line 72):

```bash
# Runs that reached a VERDICT. `running`/`pending` are in-progress bookkeeping
# and never consume an attempt number (t1262). Mirrors TERMINAL_STATUSES in
# lib/gate_ledger.py — the bash<->python parity case in tests/test_gate_ledger.sh
# keeps the two honest.
TERMINAL_STATUSES="pass fail skip error"

is_terminal_status() {
    local s
    for s in $TERMINAL_STATUSES; do [[ "$1" == "$s" ]] && return 0; done
    return 1
}
```

Next to `_gate_run_is_running` (line 151), one awk pass answering both
questions — the terminal count and the live run — so `begin-procedure` needs a
single scan while holding the lock:

```bash
# _gate_run_state <file> <gate> — two lines:
#   OPEN:<run-id>|<attempt>    (both empty when no run is live)
#   TERMINAL:<n>
# A run is LIVE when its latest marker is `running`; any terminal marker with the
# same run id closes it. A marker with no parseable status= counts as neither —
# malformed data must not inflate the counter (t1262).
# 2-arg match() only: gawk's 3-arg form is a hard syntax error under BSD awk and
# is grep-guarded by tests/test_gate_ledger.sh.
_gate_run_state() {
    local file="$1" gate="$2"
    awk -v g="$gate" -v terms=" $TERMINAL_STATUSES " '
        /^>[[:space:]]*\*\*/ && /gate:/ {
            if (!match($0, /gate:[A-Za-z0-9_]+/)) next
            if (substr($0, RSTART + 5, RLENGTH - 5) != g) next
            if (!match($0, /status=[A-Za-z]+/)) next
            st = substr($0, RSTART + 7, RLENGTH - 7)
            rid = ""; if (match($0, /run=[^ ]+/)) rid = substr($0, RSTART + 4, RLENGTH - 4)
            if (index(terms, " " st " ") > 0) {
                n++; if (rid != "") last[rid] = st
            } else if (st == "running" && rid != "") {
                if (!(rid in seen)) { seen[rid] = 1; order[++k] = rid }
                last[rid] = st
                if (match($0, /attempt=[0-9]+/)) att[rid] = substr($0, RSTART + 8, RLENGTH - 8)
            }
        }
        END {
            open_rid = ""
            for (i = k; i >= 1; i--) if (last[order[i]] == "running") { open_rid = order[i]; break }
            printf "OPEN:%s|%s\n", open_rid, (open_rid == "" ? "" : att[open_rid])
            printf "TERMINAL:%d\n", n + 0
        }
    ' "$file" 2>/dev/null
}
```

### 2. `aitask_gate.sh` — make the count+append atomic, **backend-preserving**

`acquire_gate_lock` is a plain `mkdir` lock (line 97-133) and is **not
reentrant**: a nested acquire spins 20×0.3s and then `die`s. So `begin-procedure`
cannot hold the lock and call `cmd_append`. Extract `cmd_append`'s post-lock body
into a helper that assumes the lock is held:

```bash
# Assumes the caller holds the gate lock for this task. Never locks, never unlocks.
_gate_append_locked() {   # <file> <gate> <status> [k=v ...]
    local file="$1" gate="$2" status="$3"; shift 3
    # The documented AIT_GATES_BACKEND escape hatch lives HERE, not in cmd_append,
    # so every entry point — cmd_append AND cmd_begin_procedure — reaches it.
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python append "$file" "$gate" "$status" "$@" \
            || die "python gate_ledger append failed"
        return 0
    fi
    ... # existing bash body: k=v parsing → run-id default → attempt → marker/body
        # → section → tmp+`mv` → echo
}
```

**This is the correction to the previous draft**, which put the backend branch
only in `cmd_append` and so would have made `begin-procedure`'s `running` block
bash-only under `AIT_GATES_BACKEND=python` — leaving a "python end-to-end" test
that exercised Python for the closer alone. Hoisting the branch into the shared
helper also **removes an existing duplication**: the `--only-if-running` guard is
currently written twice (lines 197-200 in the python branch, 235-238 in the bash
one).

`cmd_append` becomes: resolve file → validate → `acquire_gate_lock` + trap →
`--only-if-running` guard (**once**) → `_gate_append_locked` → release. Behavior
byte-identical on both backends; `tests/test_gate_lock_characterization.sh` (4/2/2
concurrent auto appends asserting each `attempt=N` appears exactly once) is the
guard that the append stays inside the lock.

`_gate_run_state` gets the same treatment so `begin-procedure`'s *read* honors the
backend too — under `AIT_GATES_BACKEND=python` it delegates to a new
`gate_ledger.py run-state <file> <gate>` verb emitting the identical two lines,
falling back to the awk scan otherwise. Without this, selecting the Python backend
would still route the live-run detection and the attempt count through awk, and
the escape hatch would be only half real.

Inside `_gate_append_locked`, replace the attempt block (lines 243-256) with:

```bash
    # attempt: explicit wins; else auto for any TERMINAL status = terminal runs
    # + 1 (t1262). `running`/`pending` get no auto number — begin-procedure
    # supplies the running block's explicitly.
    if [[ -z "$f_attempt" ]] && is_terminal_status "$status"; then
        f_attempt="$(( $(_gate_run_state "$file" "$gate" | sed -n 's/^TERMINAL://p') + 1 ))"
    fi
```

### 3. `aitask_gate.sh` — `cmd_begin_procedure` gets the invariant

Replace lines 1034-1053:

```bash
    local key="${task_id//\//_}"
    acquire_gate_lock "$key"
    # shellcheck disable=SC2064
    trap 'release_gate_lock' EXIT

    local state open_field rid attempt terminal
    state="$(_gate_run_state "$file" "$gate")"
    open_field="$(printf '%s\n' "$state" | sed -n 's/^OPEN://p')"
    terminal="$(printf '%s\n' "$state" | sed -n 's/^TERMINAL://p')"

    if [[ -n "${open_field%%|*}" ]]; then
        # A gate has at most ONE live run. A second begin-procedure (crash/resume
        # re-dispatch, or a concurrent launch) ADOPTS it rather than opening a
        # duplicate: same run id, same attempt, nothing appended. The caller's
        # closing `append --only-if-running <rid>` then closes the run that is
        # actually open. Notice goes to stderr so stdout's two-line contract is
        # byte-identical. (t1262)
        rid="${open_field%%|*}"
        attempt="${open_field#*|}"
        [[ -z "$attempt" ]] && attempt="$((terminal + 1))"
        warn "gate:${gate} already has a live run (${rid}) — adopting it instead of opening a second"
    else
        attempt="$((terminal + 1))"
        # Same shape as gate_orchestrator._run_machine_gate's run id: a bare
        # second-resolution timestamp collides when two runs start in the same
        # second (observed).
        rid="$(date -u +%Y-%m-%dT%H:%M:%SZ)-${gate}-a${attempt}"
        _gate_append_locked "$file" "$gate" running run="$rid" attempt="$attempt" type=machine >/dev/null
    fi

    release_gate_lock
    trap - EXIT
    printf 'RUN_ID:%s\nATTEMPT:%s\n' "$rid" "$attempt"
```

The run id is opaque to every consumer — gate skills pass it back verbatim,
`--only-if-running` and `_current_run_status` compare strings — so the shape
change is safe and makes the double-begin tests deterministic without sleeps.

### 4. `lib/gate_ledger.py` — same rules, named once

After `SATISFIED_STATUSES` (line 66):

```python
# Statuses that mean a run reached a VERDICT. Distinct from SATISFIED_STATUSES
# ({pass, skip}), which asks whether a gate is *done* — this asks whether an
# attempt *ended*. Mirrors TERMINAL_STATUSES in aitask_gate.sh.
TERMINAL_STATUSES = frozenset({"pass", "fail", "skip", "error"})
```

After `parse_gate_runs` (line 245), the rule, named — plus `live_run`, the
python twin of the bash live-run scan:

```python
def live_run(text: str, gate: str) -> tuple[str, str] | None:
    """``(run_id, attempt)`` of ``gate``'s open run, or ``None``.

    A run is LIVE when its latest marker is ``running``; any terminal marker with
    the same run id closes it. A gate has at most one live run (t1262).
    """
```

and a `run-state <file> <gate>` CLI verb (same shape as `recorded-pass`,
line 1745-1749) printing `OPEN:<run-id>|<attempt>` and `TERMINAL:<n>` — the two
lines bash's `_gate_run_state` emits, so the backends are substitutable.


```python
def next_attempt(text: str, gate: str) -> int:
    """Attempt ordinal for a NEW run of ``gate`` = terminal runs so far + 1.

    A completed attempt is ONE terminal marker, so the ``running`` block and the
    terminal block closing it share a number; counting every marker made the
    counter advance by 2 per attempt (t1262).

    Deliberately NOT ``gate_orchestrator._attempts_used() + 1``: that counts only
    ``fail``/``error`` because it answers a different question — how much RETRY
    BUDGET is spent. The two coincide on the common path and are allowed to
    diverge (e.g. a re-recorded human gate advances the ordinal without spending
    budget). A malformed-verifier correction
    (``gate_orchestrator.reconcile_terminal``) writes a second terminal marker for
    one dispatch and counts here as its own run — the budget charges it the same
    way. Mirrored in bash by ``aitask_gate.sh``'s ``_gate_run_state``.
    """
    return 1 + sum(1 for r in parse_gate_run_blocks(text)
                   if r.name == gate and r.status in TERMINAL_STATUSES)
```

`build_block` (lines 314-324): docstring `(existing runs for this gate) + 1` →
`(terminal runs for this gate) + 1`, guard widened to the terminal set, body to
`attempt = str(next_attempt(text, gate))`.

`gate_orchestrator.py` gets **no behavior change** — only a one-line comment at
line 347 naming the ordinal/budget split, and the same sentence appended to
`_attempts_used`'s docstring. Lines 184/199 are untouched, so the retry budget is
provably identical.

### 5. Tests

**`tests/test_gate_procedure_docs.sh`**

- *Multi-cycle* (the assertion the task asks for): three `begin-procedure` →
  `append --only-if-running "$rid" … fail attempt="$att"` cycles asserting
  ATTEMPT `1, 2, 3`, plus `grep -c 'attempt=1'` == 2 (running + closer share the
  number).
- *Sequential double-begin* (concern 1): two `begin-procedure` calls with no
  terminal between them must print the **same** `RUN_ID` **and** `ATTEMPT`, and
  the file must hold exactly **one** `status=running` marker. Then close it and
  assert the next begin reports `ATTEMPT:2` with a **different** run id.
- *Concurrent double-begin*: two `begin-procedure` backgrounded and `wait`ed —
  still exactly one `running` marker, both stdouts naming the same run id.

**`tests/test_gate_ledger.sh`**

```bash
echo "--- append: running/pending do not consume an attempt (t1262) ---"
make_task 12
"$GATE" append 12 lint running run=r1 attempt=1 type=machine >/dev/null
out=$("$GATE" append 12 lint pass run=r1)                    # SAME run id, no attempt=
assert_contains "terminal closing run r1 reuses attempt 1" "attempt=1" "$out"
assert_contains "terminal closing run r1 keeps its run id"  "run=r1"    "$out"
out=$("$GATE" append 12 lint fail run=r2)
assert_contains "next attempt after one terminal = 2" "attempt=2" "$out"
"$GATE" append 12 lint pending run=r3 type=human >/dev/null
assert_not_contains "pending still has no attempt" "attempt=" \
    "$("$GATE" append 12 lint pending run=r3b type=human)"
out=$("$GATE" append 12 lint skip run=r4)
assert_contains "skip is numbered too (t1262 (b))" "attempt=3" "$out"
out=$("$GATE" append 12 lint error run=r5)
assert_contains "error is numbered too (t1262 (b))" "attempt=4" "$out"
```

Line 2-3 is the concern-5 case: the terminal append **reuses `run=r1` and omits
only `attempt=`**, so it proves a terminal block closes the live run *and*
inherits its number — not merely that markers are counted. Under the current
code it reports `attempt=2`.

- *Correction-marker case* (concern 2): replay `reconcile_terminal`'s malformed
  path — `running run=c1 attempt=1`, verifier's `fail run=c1 attempt=1`, engine's
  `error run=<fresh> attempt=1` — then assert the next auto attempt is `3` and
  that this equals `_attempts_used + 1` computed from the same file via
  `gate_orchestrator`, pinning the documented "a correction is its own run"
  decision against both implementations.
- *Parity* (lines 118-142): replay the `running`-then-auto-terminal sequence with
  pinned `run=` values through both backends and `assert_eq` the two
  `## Gate Runs` sections. `_gate_append_locked` delegates the whole append to
  `gate_ledger.py` before the bash auto path, so this genuinely exercises
  `build_block`. This is the drift guard — behavioral, not a source-scraping
  regex (there is no precedent for the latter here; `VALID_STATUSES` is
  duplicated across the two files with nothing guarding it).
- *Full begin-to-close backend parity*: run the **entire** procedure lifecycle —
  `begin-procedure` → repeat `begin-procedure` (adopt) → `append
  --only-if-running` → second `begin-procedure` — twice on twin fixtures, once
  with `AIT_GATES_BACKEND=python` set for **every** call. This is the test the
  previous draft could not have delivered, since its `running` block would have
  been bash-only.

  **The comparison must not be byte-for-byte on raw output.** `begin-procedure`
  generates its run id from `date -u +…%SZ`, so two fixture runs that straddle a
  second boundary differ in a field that carries no behavioral meaning — the test
  would pass or fail on timing. Split the assertions:

  - **Across fixtures** — normalize the volatile timestamp only, then `assert_eq`
    the two complete `## Gate Runs` sections and the two `RUN_ID:`/`ATTEMPT:`
    transcripts:
    ```bash
    norm() { sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z/<TS>/g' "$1"; }
    ```
    Everything that encodes behavior survives normalization — statuses, attempt
    numbers, body lines, and the `-<gate>-a<N>` run-id suffix (so the attempt
    embedded in each run id is still compared). `-E` is portable across BSD and
    GNU sed.
  - **Within each fixture** — assert the run-id-exact invariants that normalization
    would mask: the adopting `begin-procedure` prints the *same* `RUN_ID` the first
    one did, the closing `append --only-if-running "$rid"` targets that id, and
    exactly one `status=running` marker exists.

  No production time-injection hook is needed. The `-a<attempt>` suffix added in
  §3 is what makes the *within*-fixture ids deterministic: run 1 is
  `<TS>-<gate>-a1` and run 2 is `<TS>-<gate>-a2`, distinct even when both land in
  the same second — which the bare-timestamp id demonstrably is not.

**`tests/test_gate_orchestrator_registry.py`** — add `_check_next_attempt` to the
`CHECKS` tuple (line 200): `[]`→1, `[fail]`→2, `[running, fail]`→2, `[pass]`→2,
and assert `go._attempts_used([pass]) == 0` in the same check, pinning the
deliberate ordinal/budget split.

**No existing test flips.** Every current `attempt` assertion passes `attempt=`
explicitly or builds `pass`-only / `fail`-then-`pass` histories where old and new
rules agree; `test_gate_ledger.sh:89` asserts `pending` has no attempt and
`pending` stays non-terminal. The only behavior change reaching an existing test
is that `test_gate_procedure_docs.sh:88`'s bare `skip` now carries `attempt=1`,
which nothing asserts on. No golden references an attempt number, so **do not**
edit `.claude/skills/task-workflow/SKILL.md` (it never states the rule, and
editing it would force regeneration of six `tests/golden/procs/task-workflow/*.md`).

### 6. Docs

- `aidocs/gates/aitask-gate-framework.md:327` — replace "the (attempt) counter
  increments per append" with: the counter is the gate's **run ordinal**,
  incrementing once per terminal run, so a `running` block and its closer share
  one number; the retry **budget** is spent only by `fail`/`error`.
- Same file, re-entry contract — add the single-live-run invariant: a gate has at
  most one live run, and a repeat `begin-procedure` adopts it.
- `aitask_gate.sh` help: line ~1070 "attempt auto-increments for pass/fail" →
  "attempt defaults to (terminal runs for this gate) + 1 for any terminal
  status"; line ~1167 — note `ATTEMPT:<n>` is the run ordinal, must be passed
  back on the closing append, and that a repeat call adopts a live run.
- `aidocs/gates/stats-multistage-completion.md:146-148` — the deferred per-gate
  metric currently specifies "average `attempt=` (retry depth)". That is
  **wrong under these rules and would have been wrong under the previous draft
  too**: `attempt` is a **run ordinal** that also advances on `skip`, on `error`,
  and on a malformed-verifier correction, so averaging it does not measure
  retries. Respecify it: retry depth is the **count of `fail`/`error` runs per
  gate** (the `_attempts_used` notion); `attempt=` is the run ordinal and is
  useful for ordering runs within a gate, not as a retry statistic.

## Verification

Every command below captures a real exit status — a piped suite reports the
pipe's status, not the suite's (CLAUDE.md, "Piping discards the status").

1. **Prove each new test discriminates.** Land the test changes *first* and run
   them against unfixed source; each must exit **1**, and — per one-mutation-at-a-time
   discipline — re-run after restoring each source hunk individually so no test
   is passing for the wrong reason:
   ```bash
   bash tests/test_gate_procedure_docs.sh; echo "rc=$?"   # expect 1: ATTEMPT 1,3,5
   bash tests/test_gate_ledger.sh;        echo "rc=$?"    # expect 1: attempt=2 on the r1 closer
   ```
2. Apply the source fix; both must exit **0** with `Failed: 0`.
3. Regression sweep with a real aggregate status:
   ```bash
   rc=0
   for t in test_gate_ledger test_gate_procedure_docs test_gate_lock_characterization \
            test_gate_orchestrator test_gate_record test_gate_no_double_record \
            test_gate_recorded_pass test_gate_reentry test_gate_guarded_archival \
            test_gate_verifiers test_dependency_unblock; do
       if bash "tests/$t.sh" >"/tmp/$t.log" 2>&1; then echo "PASS $t"; else echo "FAIL $t"; rc=1; fi
   done
   echo "sweep rc=$rc"      # MUST be 0
   ```
4. Python suite + lint, statuses captured not piped:
   ```bash
   bash tests/run_all_python_tests.sh >/tmp/py.log 2>&1; py_rc=$?
   tail -3 /tmp/py.log; echo "python suite rc=$py_rc"     # MUST be 0
   shellcheck .aitask-scripts/aitask_gate.sh;  echo "shellcheck rc=$?"
   ```
5. **Live end-to-end** on a throwaway fixture, reproducing the original
   observation and the lifecycle cases: three `begin-procedure`→`fail` cycles
   print ATTEMPT 1, 2, 3 (not 1, 3, 5); a repeat `begin-procedure` mid-run
   re-prints the same run id and attempt and appends nothing.
6. **Backend substitutability**, exported for the whole lifecycle rather than the
   closer alone — replay step 5 with `AIT_GATES_BACKEND=python` exported for
   **every** call (including `begin-procedure`) and diff the resulting ledgers
   with the generated timestamp masked, so the check tests behavior rather than
   whether the two runs shared a wall-clock second:
   ```bash
   norm() { sed -n '/## Gate Runs/,$p' "$1" \
            | sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z/<TS>/g'; }
   diff <(norm fx_bash/aitasks/t10_x.md) <(norm fx_py/aitasks/t10_x.md); echo "parity rc=$?"
   ```
   Must be `0`. Run it twice back-to-back, at least once deliberately straddling a
   second boundary, to confirm the check is timing-independent. Then sanity-check
   that Python was genuinely exercised on the running block — point
   `resolve_python` at a non-existent interpreter and confirm `begin-procedure`
   fails loudly rather than silently falling back to awk.

## Risk

### Code-health risk: medium
- Extracting `cmd_append`'s post-lock body into `_gate_append_locked` restructures
  the ledger's single write path — including hoisting the `AIT_GATES_BACKEND`
  branch and de-duplicating the `--only-if-running` guard — and the concurrency
  characterization test depends on that path; a mistake could move the append
  outside the lock or silently strand the Python backend · severity: medium · →
  mitigation: inline — `tests/test_gate_lock_characterization.sh` runs unchanged
  in the §Verification step-3 sweep and fails loudly on lost updates or duplicate
  attempt numbers, and §Verification step 6 diffs full begin-to-close ledgers
  across both backends with a probe that Python is genuinely on the running-block
  path. The extraction is otherwise pure code motion with no logic change.
- `begin-procedure`'s run-id shape changes and a repeat call now appends nothing,
  altering an existing command's observable behavior · severity: low · →
  mitigation: inline — the run id is opaque to every consumer (skills echo it
  back; `--only-if-running` and `_current_run_status` string-compare), and the
  new sequential/concurrent double-begin tests pin the adopt semantics.
- Bash and Python must carry parallel implementations of one rule (the bash path
  exists so the ledger works without Python) · severity: low · → mitigation:
  inline — the behavioral parity case in §5 pins the two backends' computed
  attempt numbers, catching drift in the rule rather than just the constant.

### Goal-achievement risk: low
- The task left the counting rule open; a rule that satisfies the 1-2-3
  assertion can still be wrong for the lifecycle cases (as the naive
  terminal-count was for double-begin) · severity: low · → mitigation: inline —
  each of the four rules in §Context is stated at the source and has a dedicated
  regression test, and each new test is proven to fail before the fix.
