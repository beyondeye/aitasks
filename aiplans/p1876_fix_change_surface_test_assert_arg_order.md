---
Task: t1876_fix_change_surface_test_assert_arg_order.md
Base branch: main
Output branch: main
---

# t1876 — Fix haystack-first assert calls in test_change_surface.sh

## Context

`tests/lib/asserts.sh:179-197` defines `assert_contains desc needle haystack`
and `assert_not_contains desc needle haystack` (`printf '%s' "$haystack" | grep -qF -- "$needle"`).
Most calls in `tests/test_change_surface.sh` pass `desc "$out" "LITERAL"` — haystack
first. `grep -F` then treats each line of the multi-line output as an OR'd
pattern and searches the short literal for any of them. Positive asserts pass
by accident (one output line equals the literal); the negative controls
(`assert_not_contains ... "$out1" "TASK:b.md"`) only fail if some output line is
a substring of the literal, so they barely test anything. The t1873 additions
at the end of the file already use the correct order.

The scan across `tests/*.sh` (files that use the shared helper — the 3 files
that define their own `assert_contains` are excluded; continuation lines
joined) found exactly one more bad call:
`tests/test_shadow_capture.sh:243-244` passes
`"$(… grep -qE '^[0-9]+$' && echo NUMERIC)" "NUMERIC"`. With a non-numeric
stamp the command substitution yields `""` as the *needle*, and
`grep -qF ""` matches everything — so that assertion **can never fail**.

## Implementation

### 1. `tests/test_change_surface.sh` — swap to (desc, needle, haystack)

Swap arguments 2 and 3 on every haystack-first call (41 calls). This covers
single-line and `\`-continued calls, including the ones whose haystack is a
command substitution:

- sections 1–8 and the pick_own positive control (`"$out1" "TASK:a.md"` →
  `"TASK:a.md" "$out1"`, etc.; ~37 calls)
- line 164 `"$(cs "$fx" list 1)" "COMMITTED:a.md"`
- line 183 `"$(cs "$fx_clean" list 9)" "COMMITTED:q.md"`
- lines 372 / 374 `"$(cs "$fx9" list 10)" "TASK:k.md"` / `"UNKNOWN:k.md"`

For a continued call, keep the line break and put the needle on the
continuation line before the haystack:
`assert_not_contains "NEG: …" \` / `    "TASK:sub/foreign.md" "$out1"`.
Leave lines 395-399 as they are; they are already correct.

Also drop the parenthetical "(Argument order below is the helper's own: desc,
needle, haystack.)" at lines 387-388. Once the whole file uses one order,
that note wrongly suggests the calls above it use a different one.

Do the edits by hand, or with a small script whose output I read before running
it. Then re-run the scanning regex to confirm that zero haystack-first calls
remain.

### 2. `tests/test_shadow_capture.sh:243-244` — same swap

`assert_contains "…numeric analyzed-at" "NUMERIC" "$(printf … && echo NUMERIC)"`.
With the needle fixed to "NUMERIC", an empty or non-numeric stamp now fails
the assertion.

## Verification

1. `bash tests/test_change_surface.sh`: all pass. If an assert now fails, the
   bug it reports was hidden until now. Investigate it and report it; do not
   swap the arguments back.
2. **Mutation check (red proof for the negative controls).** Everything lives
   in the scratchpad; nothing in the repo tree changes.

   **Mutant helper: an instrumented COPY of the real helper, not a wrapper.**
   The drift guard (section 8) greps `$CS` for the literal `^EXCLUDES=` line,
   and a delegating wrapper has none. It would read an empty exclude set and
   fail in every run, which would hide the result we are measuring. So:
   - `mkdir <scratch>/mut && ln -s <repo>/.aitask-scripts/lib <scratch>/mut/lib`
     (the helper sources `$SCRIPT_DIR/lib/{terminal_compat,task_utils,atomic_write}.sh`)
   - copy `.aitask-scripts/aitask_change_surface.sh` to `<scratch>/mut/`, and
     rewrite only the `list)` arm of `main()`. Two env knobs pass through the
     `cs` subshell. When `$1` equals `$MUT_TASK`, the arm prints `$MUT_LEAD`
     (if set) *before* `cmd_list`'s output and `$MUT_LINE` (if set) *after* it.
     It uses `if`, not `&&`, so the exit status stays clean. The
     `EXCLUDES=` line stays byte-identical, and section 9's `cp "$CS"` only
     ever reaches `capture`, so neither the drift guard nor the pick_own
     comparison is disturbed.
   - Build test copies with `sed`: pin `SCRIPT_DIR=` to `<repo>/tests`, and
     point `CS=` at the mutant. Make one copy from the fixed working file and
     one from `git show HEAD:tests/test_change_surface.sh`, the pre-fix
     version.

   **Three mutants, each with its expected result (checked by reasoning
   through the grep semantics):**

   Each mutant injects a *genuinely forbidden* classification, or a harmless
   formatting change. None injects a different file whose name happens to
   contain the needle: that would make a false failure of the substring
   needle the pass criterion.

   | mutant | fixed file | pre-fix file |
   |---|---|---|
   | M1: `MUT_TASK=1 MUT_LINE=TASK:b.md` (the concurrent edit wrongly attributed to t1) | `list 1 NEG: concurrent edit must NOT be attributed` **FAILS** (the red proof the task requires) | also fails: the injected line joins the pattern list and matches the `TASK:b.md` haystack, so M1 does **not** tell the two versions apart |
   | M2: `MUT_TASK=5 MUT_LINE=TASK:f.md` (no-plan fixture yields a TASK:, which is forbidden) | `NEG: no plan must never yield TASK` **FAILS**, for the right reason | the same assert **passes**: no line of `out5` (`BASELINE:missing`, `PLANSCOPE:missing`, `UNKNOWN:f.md`, `TASK:f.md`) is a substring of the haystack `TASK:`. This shows the old negative control was vacuous |
   | M3: `MUT_TASK=1 MUT_LEAD=''` printed as an empty leading line (a leading newline survives `$(…)`) | all asserts **pass** (no attribution changed) | the `out1` NEG asserts (`list 1 NEG…`, `NEG: directory token…`) **fail for the wrong reason**: an empty pattern matches everything |

   (M3's knob is "LEAD is set", not "LEAD is non-empty": use `${MUT_LEAD+x}`.)

   Known residual limitation, outside this task's scope: the fixed calls still
   use fixed-string *substring* matching. A NEG needle like `TASK:b.md` would
   therefore also trip on a line `TASK:b.md.orig`. That failure mode is false
   failures (loud), never false passes, so it is acceptable here. Line-exact
   matching would need a different helper. Mention it in Final Notes; do not
   fix it here.

   Pass criterion: every cell matches the table, and apart from the named
   asserts both copies otherwise report 0 failures. That second part shows
   the scaffolding (drift guard, pick_own arms) was not disturbed.
   If any cell disagrees, stop and investigate. Do not adjust the table to fit.
3. `bash tests/test_shadow_capture.sh`: passes, or skips the live-tmux case
   where tmux is unavailable.
4. `shellcheck` is not required: the only files changed are tests.

## Step 9 reference
Post-implementation: commit as `bug: … (t1876)` naming only the two test files,
then archive via Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
