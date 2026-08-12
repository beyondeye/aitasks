---
Task: t1485_fix_unreachable_no_plan_branch_and_lock_test_isolation.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
---

# Plan — t1485: Retire the dead NO_PLAN branch and isolate the gate-lock test

## Context

Two independent, pre-existing defects, both surfaced by t1207's enforcement fix.

**Defect 1 — a fallback whose trigger no longer exists.**
`aitask_brainstorm_archive.sh:74` catches a finalize failure and greps its output
for `has no plan_file`. Commit `d59f28bbd` (t441) added that guard *and*
`tests/test_brainstorm_cli.sh` Test 11 together, back when
`finalize_session` raised `ValueError(f"HEAD node '{head}' has no plan_file.")`.
Commit `bd2e5dbe2` (t891_4) then rewrote `finalize_session` to export the HEAD
node's **proposal** and deleted that error — after `41bf99bab` (t891_3) removed
the brainstorm plan data model entirely. t891_4 touched neither the shell script
nor this test, so from that moment the branch became unreachable and Test 11
went red.

Today the string appears in exactly one place in the repo: the grep that looks
for it. `finalize_session` can raise only `ValueError("No HEAD node set — cannot
finalize.")`, the unsynced-module `ValueError`, or an incidental
`FileNotFoundError` from `read_proposal` — none of which mention `plan_file`.
`NO_PLAN` has **zero consumers** repo-wide and is absent from the script's own
documented output contract (its header lists only `PLAN:<path>` and
`ARCHIVED:<task_num>`). And `create_node` always writes
`br_proposals/<id>.md`, while `init_session` seeds `n000_init` as HEAD with a
proposal — so a freshly initialized session finalizes *successfully*. Test 11's
sibling assertion (`ARCHIVED:999`) already passes; only the `NO_PLAN` one fails.

**Decision (user-confirmed): retire the `NO_PLAN` concept.** The proposal model
replaced the plan model deliberately; reintroducing a "no plan" error would
resurrect a concept two tasks removed on purpose. The assertion is not deleted —
it is retargeted to the behaviour that is actually true and currently untested.

**Defect 2 — a characterization test that cannot run beside itself.**
`acquire_gate_lock` (`.aitask-scripts/aitask_gate.sh:120-156`) builds
`/tmp/aitask_gate_lock_${key}` from the raw task-id argument. There is **no**
env seam for that base path anywhere in the repo, so the task id is the only
isolation lever a test has. `tests/test_gate_lock_characterization.sh` uses
eight fixed ids (`987651`–`987658`), so two concurrent runs pre-hold, backdate,
`rmdir` and assert on the *same* `/tmp` directories — each reading the other's
lock as the "foreign" lock the tests characterize. Evidence in the task: 4/4
concurrent runs fail, 8/8 sequential runs pass. Its own header comment names the
gap: distinctive ids keep the suite out of *other suites'* key space, but give
zero isolation from another instance of itself. The fixture repo is already
`mktemp -d`-scoped, so `/tmp/aitask_gate_lock_*` is the only colliding state.

**Decision (user-confirmed): per-run id namespace, test-only.** No production
change — `$$` is unique among live processes, which is exactly the collision
window.

## Implementation

### Pre-phase (risk mitigations)

**`concurrent_negative_control`** — runs **before any edit**, so the post-fix
result is a proven flip rather than an assumed one. From the repo root:

```bash
# (a) Clean sequential baseline — proves the /tmp key space is not already dirty.
bash tests/test_gate_lock_characterization.sh > /tmp/negctrl_base.log 2>&1
echo "baseline rc=$?"; tail -2 /tmp/negctrl_base.log

# (b) The collision itself.
bash tests/test_gate_lock_characterization.sh > /tmp/negctrl_a.log 2>&1 &
bash tests/test_gate_lock_characterization.sh > /tmp/negctrl_b.log 2>&1 &
wait
grep -h '^Results:' /tmp/negctrl_a.log /tmp/negctrl_b.log

# (c) The failure must carry a lock-identity signature, not just a nonzero tally.
grep -hE 'FAIL.*(die leaves the foreign lock dir intact|2 contenders through a stale lock|lock dir released after normal exits|no lock dir left behind after contention|4 concurrent same-spelling appends)' \
    /tmp/negctrl_a.log /tmp/negctrl_b.log
```

Gating rules — **all three must hold** before Part C is touched:

- **(a) must be green** (`rc=0`, `All tests PASSED`). The suite's EXIT trap
  clears its lock dirs, so a passing sequential run establishes that no
  `/tmp/aitask_gate_lock_98765*` is leaked at that instant. Without this
  baseline, a directory left behind by a SIGKILLed earlier run produces exactly
  the same failures as a live peer and the negative control proves nothing.
  If (a) fails, the environment — not the concurrency — is the cause:
  `ls -d /tmp/aitask_gate_lock_98765* 2>/dev/null`, confirm no other agent on
  this box is running the suite, clear the leak, and re-run (a).
- **(b) must show failures** in at least one run (the task records 4/4).
- **(c) must be non-empty.** A nonzero `Results:` line alone is not proof — it
  is also what a leaked dir, a missing python (`SKIP:` paths), or an unrelated
  breakage produces. The recorded failure must name one of the lock-ownership
  assertions above, i.e. a lock this run created being absent, or a ledger block
  lost to a peer.

Record the baseline line, both `Results:` lines, and the matched signature lines
verbatim in the Final Implementation Notes. If (b) or (c) does not hold after a
green (a), the collision did not reproduce here and the rest of Part C is
unverifiable as written — stop and re-derive rather than "fixing" an
unreproduced defect.

### Part A — `.aitask-scripts/aitask_brainstorm_archive.sh`

1. **Replace the finalize guard** (lines 71-86). Drop the dead branch so any
   finalize failure plainly dies, and extract the `PLAN:` line robustly — the
   capture merges stderr (`2>&1`), so a whole-string prefix strip
   (`${finalize_output#PLAN:}`) is wrong the moment a warning precedes it:

   ```bash
   # --- Finalize: export HEAD proposal to aiplans/ ---
   info "Finalizing brainstorm session for task $TASK_NUM..."
   finalize_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" finalize --task-num "$TASK_NUM" 2>&1) || {
       die "Failed to finalize session: $finalize_output"
   }

   # Surface the exported proposal path (PLAN:<path>) emitted by the CLI. The
   # capture merges stderr, so match the line rather than prefix-stripping the
   # whole string.
   plan_line=$(printf '%s\n' "$finalize_output" | grep '^PLAN:' || true)
   if [[ -n "$plan_line" ]]; then
       echo "$plan_line"
   fi
   ```

2. **Correct the stale header prose** left behind by t891_4 (lines 6, 10, 35,
   42): "Copies HEAD node's plan to aiplans/" → "Exports HEAD node's proposal
   to aiplans/", and the `PLAN:<path>` output description likewise. The output
   token `PLAN:` itself is the contract and does **not** change.

### Part B — `tests/test_brainstorm_cli.sh` Test 11 (lines 300-311)

Retarget the test to the real, currently-untested contract: a freshly
initialized session has `HEAD=n000_init` with a seeded proposal, so archive
exports it and reports both lines. This *strengthens* the test (it now asserts
the exported file exists on disk); it does not drop coverage.

```bash
# --- Test 11: brainstorm archive exports the HEAD proposal ---
echo "Test 11: brainstorm archive exports HEAD proposal and archives"
TMPDIR_T11="$(setup_test_repo)"
(
    cd "$TMPDIR_T11"
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    # init seeds HEAD=n000_init with a proposal, so finalize succeeds. There is
    # no "HEAD has no plan" state: t891_3/t891_4 replaced the plan data model
    # with proposals, which create_node always writes (t1485).
    output=$(bash .aitask-scripts/aitask_brainstorm_archive.sh 999 2>&1)
    assert_contains "archive emits the exported proposal path" "PLAN:" "$output"
    plan_path=$(printf '%s\n' "$output" | sed -n 's/^PLAN://p' | head -n1)
    assert_contains "exported file is named for the HEAD node" \
        "p999_n000_init.md" "$plan_path"
    assert_file_exists "exported proposal exists on disk" "$plan_path"
    assert_contains_ci "archive outputs ARCHIVED" "ARCHIVED:999" "$output"
)
cleanup_test_repo "$TMPDIR_T11"
```

Confirm the printed path at implementation time (it is CWD-relative from
`finalize_session`); the assertions above are written to hold either way.

**Add Test 12 — the failure path.** Test 11 only exercises the success path, so
nothing would catch a regression that lets `archive` and
`aitask_crew_cleanup.sh` run *after* a genuine finalize failure (no HEAD,
corrupt session, unreadable proposal). Part A's `die` is now the only guard;
pin it. Deleting the HEAD proposal makes `read_proposal` raise deterministically
(`brainstorm_dag.py:531-534`), which is the failure shape the removed branch
used to intercept:

```bash
# --- Test 12: archive stops at a finalize failure (no archive, no cleanup) ---
echo "Test 12: brainstorm archive aborts when finalize fails"
TMPDIR_T12="$(setup_test_repo)"
(
    cd "$TMPDIR_T12"
    WT=".aitask-crews/crew-brainstorm-999"
    bash .aitask-scripts/aitask_brainstorm_init.sh 999 >/dev/null 2>&1
    rm -f "$WT/br_proposals/n000_init.md"   # HEAD proposal unreadable
    output=$(bash .aitask-scripts/aitask_brainstorm_archive.sh 999 2>&1); rc=$?
    assert_exit_nonzero_rc "archive exits nonzero when finalize fails" "$rc"
    assert_contains "die names the finalize failure" \
        "Failed to finalize session" "$output"
    assert_not_contains "no ARCHIVED: emitted after a finalize failure" \
        "ARCHIVED:" "$output"
    assert_not_contains "no PLAN: emitted after a finalize failure" \
        "PLAN:" "$output"
    assert_dir_exists "crew worktree not cleaned up after a finalize failure" "$WT"
    assert_not_contains "session not marked archived after a finalize failure" \
        "status: archived" "$(cat "$WT/br_session.yaml")"
)
cleanup_test_repo "$TMPDIR_T12"
```

`WT` mirrors the derivation already used at line 132 of this file. Verify at
implementation time that the pre-fix script also fails this test for the *right*
reason (it dies identically — the removed branch never matched this error
either), so Test 12 is a genuine new pin rather than a restatement of Part A.

### Part C — `tests/test_gate_lock_characterization.sh`

The file already has a `key_for_id()` / `lock_dir_for_id()` indirection for the
t635_30 flip. Keep that seam untouched in meaning; add a second, orthogonal one
for the id namespace.

1. **Single-source the lock path, then add the per-run namespace.** The base
   path is hoisted into one constant so the post-phase guard has a realizable
   invariant to audit (today the literal is spelled out again in
   `lock_dir_for_id`, and adding three more spellings would make it four).
   `lock_dir_for_id` is retained and re-expressed in terms of `raw_lock_dir`, so
   `key_for_id` remains the single knob t635_30 re-points:

   ```bash
   # The one place this file spells the gate lock path. Mirrors the hardcoded
   # construction in acquire_gate_lock (aitask_gate.sh) — there is no env seam
   # for it, which is why the task id is the only isolation lever below.
   GATE_LOCK_BASE='/tmp/aitask_gate_lock_'

   # Tests 2a/2b/3 characterize the key derivation itself, so they name each
   # spelling explicitly rather than routing through key_for_id().
   raw_lock_dir()      { printf '%s%s'    "$GATE_LOCK_BASE" "$1"; }
   basename_lock_dir() { printf '%st%s_x' "$GATE_LOCK_BASE" "$1"; }
   alias_lock_dir()    { printf '%st%s'   "$GATE_LOCK_BASE" "$1"; }

   lock_dir_for_id() { raw_lock_dir "$(key_for_id "$1")"; }

   # Per-run task-id namespace (t1485). With fixed ids, two concurrent runs of
   # THIS file pre-hold, backdate and assert on the same lock dirs and read
   # each other's locks as the "foreign" lock these tests characterize.
   # $$ is this file's own shell pid — unique among live processes, which is
   # exactly the collision window.
   ID_BASE="9$$"
   ID1="${ID_BASE}1"; ID2="${ID_BASE}2"; ID3="${ID_BASE}3"; ID4="${ID_BASE}4"
   ID5="${ID_BASE}5"; ID6="${ID_BASE}6"; ID7="${ID_BASE}7"; ID8="${ID_BASE}8"
   IDS=("$ID1" "$ID2" "$ID3" "$ID4" "$ID5" "$ID6" "$ID7" "$ID8")
   ```

   `key_for_id()` keeps its existing body and its flip-contract comment
   unchanged.

2. **Build `LOCK_DIRS` from the namespace** instead of the 17 literals, all
   three spellings per id:

   ```bash
   LOCK_DIRS=()
   for id in "${IDS[@]}"; do
       LOCK_DIRS+=( "$(raw_lock_dir "$id")" \
                    "$(basename_lock_dir "$id")" \
                    "$(alias_lock_dir "$id")" )
   done
   ```

   Add a pre-flight clear of `LOCK_DIRS` right after the `trap cleanup EXIT`:
   because pids are unique among *live* processes, a dir already present at one
   of our paths can only be a leak from a dead run (SIGKILL before the trap), so
   removing it is safe — and, unlike the old fixed-id version, cannot mask a
   concurrent peer.

3. **Re-key the fixture loop**: `for id in "${IDS[@]}"; do make_task "$id"; done`.

4. **Substitute the ids at every call site**, 1:1 by position
   (`987651`→`$ID1` … `987658`→`$ID8`). This covers the `run_gate` arguments,
   every `"$TMP/aitasks/t<id>_x.md"` path, every `lock_dir_for_id <id>`, the
   `t`-spelled argument in Test 3 (`run_gate append "t${ID2}"`), and the
   exhaustion message asserted in Test 2a
   (`"Failed to acquire gate append lock for ${ID2} after 20 attempts"`).
   Tests 2a/2b/3 additionally swap their inline literal paths for
   `raw_lock_dir "$ID2"` / `basename_lock_dir "$ID2"` / `alias_lock_dir "$ID2"`.

5. **Update the header comment** that encodes the old scheme — the "distinctive
   task ids (987651-987656)" rationale at lines 40-42. Rewrite it to describe
   the per-run namespace, and **do not reintroduce any `98765x` literal or the
   `/tmp/aitask_gate_lock_` string** in prose (both are what the post-phase
   guard checks; refer to `GATE_LOCK_BASE` and `IDS` by name instead). The
   flip-contract note at 62-68 stays accurate — `key_for_id` remains the single
   knob t635_30 re-points; only the id source changed.

Out of scope, to be recorded as upstream defects in the Final Implementation
Notes rather than fixed here: `tests/test_parallel_child_create.sh` has the
identical collision against `aitask_create.sh`'s
`/tmp/aitask_child_lock_100`, and `acquire_gate_lock`'s `/tmp` path is not
repo-scoped, so two aitasks checkouts on one box share a mutex namespace for the
same task id.

### Post-phase (risk mitigations)

**`guard_no_residual_fixture_literals`** — runs after Part C, before the
concurrent re-run. A single missed literal leaves an assertion pointing at a
path no run participates in, where it passes vacuously:

```bash
F=tests/test_gate_lock_characterization.sh

# (1) No fixed fixture id survives, in code or in prose.
grep -nE '98765[0-9]' "$F"                    # must print nothing

# (2) The lock path is spelled exactly once, in the GATE_LOCK_BASE assignment.
grep -n '/tmp/aitask_gate_lock_' "$F"         # must print exactly 1 line
grep -c "^GATE_LOCK_BASE='/tmp/aitask_gate_lock_'\$" "$F"   # must print 1
```

Rule (2) is only realizable because Part C step 1 hoists the literal into
`GATE_LOCK_BASE` and re-expresses `lock_dir_for_id` in terms of `raw_lock_dir`
— every other path is now built from that constant, and step 5 keeps the string
out of the rewritten comments. If (2) reports more than one line, the extra
occurrences must be eliminated, not the rule relaxed.

Then confirm by inspection that every `run_gate` id argument, every
`"$TMP/aitasks/t…_x.md"` path, and every `assert_dir_exists` /
`assert_dir_not_exists` argument is built from an `ID<n>` variable or one of the
four helpers.

## Verification

1. `bash tests/test_gate_lock_characterization.sh` — sequential, expect
   `All tests PASSED`.
2. Re-run the pre-phase's concurrent pair after the change, and once at 4-way
   concurrency — expect `All tests PASSED` from **every** instance, against the
   recorded negative-control failures. Re-run the pre-phase's step (c) signature
   grep over the new logs: it must now match **nothing**.
3. `bash tests/test_brainstorm_cli.sh` — expect `FAIL: 0` and a zero exit
   (it currently reports `PASS: 29 / FAIL: 1 / TOTAL: 30`; the new totals follow
   from Test 11's and Test 12's assertion counts — read them off the run, do not
   pin a number here).
3b. Confirm Test 12 discriminates: with Part A's edit reverted in a scratch copy
   it must still pass (the guard it pins predates this task), and with the `die`
   replaced by a bare `true` it must fail — otherwise it is not testing the
   abort.
4. `shellcheck .aitask-scripts/aitask_brainstorm_archive.sh tests/test_gate_lock_characterization.sh tests/test_brainstorm_cli.sh`
5. Confirm nothing else consumed the removed sentinel:
   `grep -rn 'NO_PLAN\|has no plan_file' . --exclude-dir=.git` returns nothing
   outside the task/plan files.

Step 9 (Post-Implementation) then runs the merge, gates and archival as usual.

## Risk

### Code-health risk: medium
- Mechanically re-keying 8 ids across ~40 call sites in a *characterization*
  file that t635_30 depends on may leave one stale literal, silently pointing an
  assertion at a path no run participates in — the assertion then passes
  vacuously. · severity: medium · → mitigation: inline post-phase
  guard_no_residual_fixture_literals
- Removing the `NO_PLAN` echo changes `ait brainstorm archive`'s stdout surface.
  It is undocumented and unconsumed in-tree, but an out-of-tree wrapper parsing
  it would break silently. · severity: low · → mitigation: none (accepted — the
  script's documented output contract is corrected in Part A step 2)

### Goal-achievement risk: low
- The lock collision manifests only under concurrency, so a sequential green run
  cannot distinguish a real fix from a no-op — and a leaked lock dir from a
  killed earlier run mimics the collision exactly. · severity: medium
  · → mitigation: inline pre-phase concurrent_negative_control
- Retargeting Test 11 to the success path leaves the generic finalize-failure
  `die` — after Part A the only thing between a broken session and
  archive + crew cleanup — unpinned by any test. · severity: medium
  · → mitigation: Test 12 (Part B)

### Planned mitigations
- timing: pre-phase | name: concurrent_negative_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — concurrency-only manifestation | desc: run two concurrent instances of the unmodified lock suite and record the failures before editing, so the post-fix concurrent green is a proven flip
- timing: post-phase | name: guard_no_residual_fixture_literals | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — stale literal after the re-key | desc: assert no fixed fixture id survives and that the lock path literal is spelled exactly once, in the GATE_LOCK_BASE assignment
