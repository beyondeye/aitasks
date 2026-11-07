---
Task: t2215_fix_cd_guard_lint_hit_and_assert_contains_sigpipe.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2215 — Fix the cd-guard lint hits and the assert_contains SIGPIPE false result

## Context

Two upstream defects were found during t2175_6:

1. **`tests/lib/asserts.sh` contains helpers.** All six helpers (`assert_contains`,
   `assert_not_contains`, `_ci`, `_re` and their `not_` forms, lines 179-238) run
   `printf '%s' "$haystack" | grep -q… -- "$needle"`. If the caller has `set -o pipefail` and
   the haystack is bigger than the pipe buffer, `grep -q` exits on the first match, `printf`
   is killed by SIGPIPE, and the pipeline fails. The result: a needle that **is** present is
   reported missing, and `assert_not_contains` **falsely passes**. I reproduced it: with a
   2 MB haystack it gave the wrong result 20 times out of 20.
   `tests/test_sitrep_corpus.sh` carries local here-string overrides as a workaround.
2. **`tests/test_cd_guard_lint.sh` fails on the committed tree.** It now reports 5 hits,
   not just the one the task names:
   - `tests/test_codeagent.sh:372` — `unconfined-andchain` (t2175_4, the one named in the task)
   - `tests/test_file_references.sh:372` — `unconfined-andchain` (a `;` inside `$(cd … && a; b)`), from t2209
   - `tests/test_premise_baseline_field.sh:24` and `tests/test_premise_baseline_seeding.sh:32`
     — an `unguarded` `cd /` and no `enter_scratch_cwd` call (t1663_2/3; now committed,
     so this is the "check whether it has since been fixed" item: it has not)
   - `tests/test_label_yaml_words.sh` — no `enter_scratch_cwd` call (first cd at line 138), from t2214

   All five files are committed and clean against HEAD. The tasks that added them (t2175_4,
   t2209, t1663_2, t1663_3, t2214) are all archived. The lint is one shared gate, so this
   task fixes every hit and gets it back to green.

Base branch: main · Output branch: main · current-branch mode (profile fast).

## Approach for asserts.sh: process substitution, not a here-string

The task suggests a here-string, but a here-string is **not byte-exact**: bash adds a newline.
I measured the difference against the current pipe:

| case | old pipe | `<<<` here-string | `< <(printf …)` |
|---|---|---|---|
| 2 MB haystack, needle on line 1, pipefail | false result 20/20 | 0/20 | 0/20 |
| empty haystack, empty needle (`-F`) | rc 1 | **rc 0** | rc 1 |
| haystack `abc\n`, pattern `^$` (`-E`) | rc 1 | **rc 0** | rc 1 |

`asserts.sh` is shared by 376 test files, so the fix must not change any result except the
SIGPIPE one. Each helper's condition becomes:

```bash
grep -qF -- "$needle" < <(printf '%s' "$haystack" 2>/dev/null)
```

grep reads exactly the old bytes. The writer's exit status is no longer part of a pipeline,
so pipefail cannot see it. `2>/dev/null` covers an environment where SIGPIPE is ignored: there
printf gets EPIPE and would print "write error" instead of dying quietly. The flags of each
helper (`-qF`, `-qiF`, `-qE`) stay as they are. One comment block above the helpers gives the
reason (pipefail + early-exiting grep; byte-exact, unlike `<<<`), with t2215 as the reference.

## Steps

### Pre-phase (risk mitigations)

1. [byte_exact_pins] Before editing `asserts.sh`, write `tests/test_asserts_pipefail.sh`
   (see Step 3 for what it contains). Run it against the **unmodified** helpers. It must fail
   in the 6 pipefail cases and pass the two byte-exactness pins plus the no-pipefail sanity
   case. Its pre-fix control must show the wrong result. This locks in the measured old
   behaviour first. The helper change in Step 1 must then turn the 6 cases green without
   touching a pin.

### Main steps

1. **`tests/lib/asserts.sh`** — rewrite the condition of the six helpers as above. Add the
   comment to the existing "substring / pattern containment" header block.
2. **`tests/test_sitrep_corpus.sh`**
   - Delete the local `assert_contains` / `assert_not_contains` overrides and their comment
     (lines 48-69). The shared helpers are now pipefail-safe.
   - Lines 584-585: the comment "Counted, not assert_contains … SIGPIPE" will no longer be
     true. Keep the `assert_eq … grep -c` check, which is stronger because it requires both
     lines, and reword the comment to say only that: "Counted: both pre-fix lines must be
     present."
3. **New `tests/test_asserts_pipefail.sh`**, built the same way as `test_asserts_counters.sh`
   (each scenario runs in a child `bash` that sources the real `asserts.sh` and prints
   `PASS=/FAIL=`; the parent checks those numbers):
   - Under `set -o pipefail` with a 2 MB haystack and the needle on line 1, for each of the
     6 helpers: the positive form records PASS, and the negative form records FAIL
     (needle present).
   - **Pre-fix control:** an inline copy of the old `printf | grep -qF` body, run on the same
     fixture, must give the wrong result at least once in 5 tries. This proves the fixture
     really triggers SIGPIPE.
   - **Byte-exactness pins:** `assert_contains "" ""` still records FAIL;
     `assert_contains_re '^$'` on `$'abc\n'` still records FAIL. A here-string would fail
     both checks.
   - A sanity case without pipefail (a small haystack, needle present and needle absent).
   - **Matching-mode cases that tell the three modes apart**, small haystacks, each checked
     against both the positive and the negative form:
     - case: haystack `Hello WORLD`, needle `world` → `assert_contains_ci` PASS,
       `assert_not_contains_ci` FAIL. The same needle with `assert_contains` FAIL and
       `assert_not_contains` PASS, because fixed-string matching is case-sensitive.
     - regex: haystack `abc123`, pattern `c[0-9]+` (that text does not appear literally) →
       `assert_contains_re` PASS, `assert_not_contains_re` FAIL. The same text with
       `assert_contains` FAIL and `assert_not_contains` PASS, because it is matched literally.
     - fixed-string metacharacter: haystack `abc`, needle `a.c` → `assert_contains` FAIL and
       `assert_contains_ci` FAIL (`-F` must not treat `.` as a regex).
   - The child scripts source `${AIT_ASSERTS_LIB:-$PROJECT_DIR/tests/lib/asserts.sh}`, so a
     mutant copy can be passed in for the red proofs.
   - The file runs nothing in subshells at top level, so it needs no file-backed counters.
     It does not `cd`, so the cd-guard rule does not apply.
4. **`tests/test_codeagent.sh:372`** → `output=$( (cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string "$agent" --dry-run invoke sitrep) 2>&1 || true)`.
   The `2>&1` stays outside the subshell, so a `cd` error is still captured. The `|| true`
   keeps `set -e` from aborting.
5. **`tests/test_file_references.sh:372-374`** → split it into two lines:
   `(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_update.sh --batch "$n16" --status Ready >/dev/null 2>&1) || true`
   then `find16="$(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_find_by_file.sh "a,b.py" 2>&1)"`.
   The `|| true` keeps the old `;` behaviour, where a failed update does not stop the
   find. I checked these forms with `cd_guard_scan.py --check` and it accepts them.
6. **`tests/test_premise_baseline_field.sh` / `tests/test_premise_baseline_seeding.sh`** —
   replace `cd /` (and its "Start from an empty read-only dir" comment) with
   `. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"` + `enter_scratch_cwd`. That is the
   sanctioned way to do the same thing. Every later `cd` in both files is already guarded or
   confined.
7. **`tests/test_label_yaml_words.sh`** — add the same two lines right after `PROJECT_DIR=`
   (line 29), before anything else is sourced.

### Post-phase (risk mitigations)

1. [pipefail_caller_sweep] Once Steps 1-7 are in place, and **before committing**:
   - **Selection:** `grep -lE pipefail tests/*.sh | xargs grep -lE '\bassert_(not_)?contains(_ci|_re)?\b'`
     (141 files when measured). Save the list in the scratchpad.
   - **New-side run:** run each file from this tree with `xargs -P4`, in the background,
     writing one log plus its exit status per file to the scratchpad.
   - **Three buckets, sorted by evidence and never by guessing:**
     - **executed-pass:** exit 0 and no SKIP or refusal line.
     - **refused/skipped:** the run ended before its assertions ran, for example
       `require_clean_ait_server` refusing because `$TMUX` is set
       (`tests/lib/tmux_isolation.sh:161`, which is the case in this session for
       `tests/test_freeze_engine_live.sh` and others), a `SKIP:` exit, or a missing tool.
       These are recorded by name as **unexecuted coverage**, never counted as passing. I will
       not override the refusals (no `AIT_LIVE_TMUX_TEST_FORCE`), because they protect the
       user's live tmux server.
     - **failed:** everything else, including runs that abort without printing a `FAIL:`.
   - **Baseline differential, for failed files only:** build a baseline that differs from
     this tree **only in `tests/lib/asserts.sh`**:
     `git worktree add --detach <scratchpad>/t2215_base HEAD`, then
     `git diff HEAD -- . ':!tests/lib/asserts.sh' | git -C <base> apply` so the uncommitted
     changes from this task and other sessions are carried over too. Copy any untracked file
     a failing test needs. Then run `./.aitask-scripts/aitask_init_data.sh --link-worktree <base>`.
     The baseline's `asserts.sh` is HEAD's, so it keeps the original pipe behaviour.
     **Instrument it in the scratch baseline only:** in each of the six helpers, after the
     original pipeline decides "no match", also run the byte-exact check
     (`grep -q… < <(printf …)`). If the two disagree, append
     `MASKED:<helper>|<desc>|<sha256 of haystack>` to a scratchpad log. The instrumentation
     never changes the helper's verdict, so the baseline keeps the original behaviour while
     recording each place where the pipe hid a real match.
   - **Re-run each failed file one at a time on both sides**, with the same env and no
     parallel load. For each side, capture: the exit status; the `Results:` line (TOTAL /
     passed / failed); the **set of failing assertion descriptions** (the `desc` from each
     `FAIL: <desc> (…` line, keyed on the description because the haystack can hold temp
     paths that differ between runs); and the last 20 output lines (where the run stopped).
   - **Attribution, per assertion, not per file:**
     - **Pre-existing:** the file fails on both sides and the comparison is **identical**:
       same set of failing descriptions, same exit status, and the same TOTAL / stopping
       point. Only then is it listed as pre-existing and left alone.
     - Any **difference** (an extra failing description on the new side, a different TOTAL,
       a different exit status or abort point, or a new-side abort that prints no `FAIL:`)
       means each differing item is handled separately under the next two rules. A file
       failing on both sides is not dismissed because of that.
     - **Exposed old false pass**, only when all three hold for the new-side assertion:
       (a) it is a **negative** form (`assert_not_contains*`), because the old pipe could only
       hide a match, so a newly failing *positive* assertion can never be explained this way;
       (b) the haystack really contains the needle (the new helper's byte-exact verdict);
       (c) the baseline's `MASKED:` log has the same helper + description (and, when the
       fixture is deterministic, the same haystack hash), which proves the original pipeline
       hid that match. Send a note to the owning task, or create a follow-up when the owner
       is archived. Never weaken the assertion.
     - **Unresolved possible regression:** every other difference. That includes a newly
       failing positive assertion, a negative one with no matching `MASKED:` record, an extra
       or changed abort, and a different TOTAL. **Stop: no commit** until it is explained
       with evidence, either by fixing this change or by showing it is environmental through
       a repeated alone run that gives the same difference on the baseline.
     - **Load flake:** passes on both sides when run alone. List it as a `-P4` flake, along
       with what it failed with under load.
   - Remove the baseline worktree afterwards (`git worktree remove <base>`).
   - Record the per-bucket counts, the refused/skipped files by name, and how each failure
     was attributed in the plan's Final Implementation Notes.

## Verification

1. `bash tests/test_cd_guard_lint.sh` → 0 failed.
2. `bash tests/test_asserts_pipefail.sh` passes. Red proofs use scratch copies of
   `asserts.sh` passed through `AIT_ASSERTS_LIB=<copy>`, and each mutant must turn red only
   the cases that target it:
   - old pipe body → the 6 pipefail cases fail; the pins and mode cases still pass.
   - here-string body → the two byte-exactness pins fail.
   - `-qiF` changed to `-qF` in both `_ci` helpers → the case-mode cases fail.
   - `-qE` changed to `-qF` in both `_re` helpers → the regex-mode cases fail.
   - `-qF` changed to `-qE` in the plain helpers → the `a.c` metacharacter case fails.
3. Run every edited test file: `test_asserts_counters.sh`, `test_sitrep_corpus.sh`,
   `test_codeagent.sh`, `test_file_references.sh`, `test_premise_baseline_field.sh`,
   `test_premise_baseline_seeding.sh`, `test_label_yaml_words.sh`.
4. `shellcheck` on the edited test files (as clean as before).
5. The post-phase `pipefail_caller_sweep` result is recorded.

## Step 9

Post-implementation: commit the code with `bug: … (t2215)`, commit the plan through
`aitask_task_commit.sh`, then archive per task-workflow Step 9 (the `risk_evaluated` gate must
pass first).

## Risk

### Code-health risk: low
- The shared `asserts.sh` is sourced by 376 test files, so a change in what the contains
  helpers return would spread silently · severity: low (residual — addressed by inline
  pre-phase byte_exact_pins) · → mitigation: inline pre-phase byte_exact_pins

### Goal-achievement risk: low
- Fixing the helpers can expose `assert_not_contains*` checks that were falsely passing
  under pipefail, so some files may turn red after landing · severity: low (residual —
  addressed by inline post-phase pipefail_caller_sweep) · → mitigation: inline post-phase
  pipefail_caller_sweep

### Planned mitigations
- timing: pre-phase | name: byte_exact_pins | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health (shared-helper semantic drift) | desc: write the pipefail/byte-exactness test first and prove it against the unmodified helpers
- timing: post-phase | name: pipefail_caller_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (exposed false passes) | desc: run the 141 pipefail callers of the shared contains helpers in three buckets (pass / refused-skipped / failed), attribute each failure per assertion (failing-description sets, exit status, TOTAL, abort point) by re-running it alone against a baseline that differs only in asserts.sh and whose helper logs MASKED matches, route only confirmed exposed false passes to their owner, and stop on any unresolved difference
