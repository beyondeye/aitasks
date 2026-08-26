---
Task: t1621_gate_dispatch_errexit_capture.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1621 — Gate-dispatch exit-status capture that survives `set -e`

## Context

`ait gates run` is dispatched from two skill procedures with this shape:

```bash
gates_out="$(./ait gates run <task_id> 2>&1)"; gates_rc=$?
```

Those are **two separate simple commands**. The assignment inherits the command
substitution's exit status, so under `set -euo pipefail` errexit fires on the
assignment and the shell exits *before* `gates_rc=$?` runs. The branch written to
diagnose a nonzero `gates_rc` is therefore unreachable in a strict shell — the
session dies with a bare exit code instead of reporting the infrastructure
failure.

Verified empirically in this session:

```
$ bash -c 'set -euo pipefail; out="$(sh -c "exit 2")"; rc=$?; echo REACHED'; echo $?
2          # "REACHED" never printed
```

t1610 hit the same class in `aitask_run_project_command.sh`, where exit 1/2 are
*ordinary verdicts*, and fixed it there:
`.claude/skills/task-workflow/build-verification.md` documents the working form
and `tests/test_run_project_command.sh` (`flow(negative control)`) pins that the
rejected form really dies. It deliberately did not widen scope to these sites.
This task closes them and sweeps the rest of the skill surface.

## Sweep result (done — recorded here)

Grepped every **authoring-source** skill file (`.claude/skills/*/`,
`.agents/skills/*/`, `.opencode/skills|commands/*/`, excluding rendered `*-`
dirs) for `$?`. Five files, six hits, classified:

| Site | Shape | Classification |
|---|---|---|
| `.claude/skills/task-workflow/SKILL.md:806` | `x="$(…)"; rc=$?` | **BUG — fix.** Named in the task. |
| `.claude/skills/aitask-pickrem/SKILL.md.j2:368` | `x="$(…)"; rc=$?` | **BUG — fix.** Named in the task. |
| `.claude/skills/aitask-trail/SKILL.md.j2:467-468` | `grep -q …` then `case $? in` | **BUG — fix.** Exit 1 (no match) is the *expected, common* outcome and the `case` has an explicit `1)` arm, but errexit kills the loop before it. Verified: the loop dies on the first non-matching file. |
| `.claude/skills/task-workflow/SKILL.md:479` | `wt_rc=0` + `x="$(…)" \|\| wt_rc=$?` | **SAFE.** Errexit is suspended for the left operand of `\|\|`, and `wt_rc` is pre-initialised so the success path is defined. Correct form — leave alone. |
| `.claude/skills/task-workflow/task-abort.md:72` | same `\|\| wt_rc=$?` form | **SAFE.** Same reasoning. |
| `.claude/skills/aitask-trail/SKILL.md.j2:464` | `{ grep -rl … \|\| [ "$?" = 1 ]; }` | **SAFE.** `grep` is the left operand of `\|\|`. |
| `.claude/skills/task-workflow/build-verification.md:48` | the documented `if/else` form | **SAFE** — this is the canonical reference. |

No abort-worthy-only captures remain: every surviving `$?` site is either fixed
or already in a form errexit cannot kill. `.claude/skills/aitask-run-gates/`
invokes the orchestrator without capturing status at all, so it is not a site.

## Changes

### 1. Fix the two gate-dispatch sites

`.claude/skills/task-workflow/SKILL.md` (Step 9) and
`.claude/skills/aitask-pickrem/SKILL.md.j2` (Step 9.5) — replace the one-liner
with the form `build-verification.md` already documents and tests:

```bash
if gates_out="$(./ait gates run <task_id> 2>&1)"; then
  gates_rc=0
else
  gates_rc=$?
fi
```

Add a single-sentence pointer at each site ("the capture form that survives
`set -e` — see `build-verification.md`") rather than restating the rationale:
the explanation stays canonical in one file. Both files already reference
`build-verification.md`, so `tests/test_run_project_command.sh` Test 6 stays green.

### 2. Fix the `aitask-trail` incoming-`verifies` sweep

`.claude/skills/aitask-trail/SKILL.md.j2:464-475` — capture grep's status into a
variable before the `case`, preserving all three documented load-bearing
properties:

```bash
      { grep -rl --include='t*.md' '^verifies:' aitasks || [ "$?" = 1 ]; } |
        { rc=0
          while IFS= read -r f; do
            grep_rc=0
            grep -q -- '<member bare id>' "$f" || grep_rc=$?
            case "$grep_rc" in
              0) printf '%s\n' "$f" ;;                          # candidate
              1) ;;                                # no match: expected, ok
              *) printf 'sweep: cannot read %s\n' "$f" >&2; rc=2 ;;
            esac
          done
          exit "$rc"; }
```

Add a fourth bullet to the "load-bearing properties, do not simplify them back"
list naming the errexit hazard, so the next reader does not collapse it.

Verified in this session that the current form dies on the first non-matching
file and the replacement emits the candidate, reports the unreadable file, and
exits 2.

### 3. New test — `tests/test_skill_errexit_capture.sh`

Self-contained bash test, `assert_eq`/`assert_contains` from `tests/lib/asserts.sh`,
no subshell test bodies (so no `assert_counters_init` needed — mirrors
`tests/test_run_project_command.sh`).

**Test 1 — the rendered gate-dispatch snippet survives a strict shell.**
For each of `task-workflow` SKILL.md × {default, fast, remote} and
`aitask-pickrem` SKILL.md.j2 × remote:
1. Render with `.aitask-scripts/lib/skill_template.py` (skip cleanly if
   `minijinja` is absent, as `tests/test_skill_render_task_workflow.sh` does).
2. Extract the fenced ```bash block whose body contains `ait gates run`,
   dedenting by the fence's own indent (the blocks are indented 2 spaces in
   `task-workflow`, 0 in `pickrem`) — prototype already validated against both.
3. **Extractor positive control:** assert the extracted block is non-empty and
   contains `ait gates run`. Without this the whole test can pass vacuously on
   an extraction miss.
4. Build a fixture dir with a stub `./ait` that writes a distinctive diagnostic
   to **stderr** (`ait: fatal: gate registry unreadable`) and `exit 2`;
   substitute `<task_id>` → `42` (unsubstituted it is a shell *redirection*, not
   an argument).
5. Run `set -euo pipefail` + block + `echo "RC=$gates_rc"` +
   `echo "OUT<<$gates_out>>"` + `echo REACHED_END`. Assert:
   - `REACHED_END` is reached;
   - `RC=2` — surviving is not enough, the captured status must be the
     dispatch's real status;
   - `OUT<<…>>` contains the stub's stderr diagnostic — i.e. `gates_out`
     actually carries the payload the nonzero branch tells the agent to
     diagnose with. This is what makes the `2>&1` load-bearing rather than
     incidental.
6. Second stub, `exit 0` with normal output: assert `RC=0` and `REACHED_END`.
   Under `set -u` an `if`-form that forgot the `gates_rc=0` branch would abort
   on the first read of `$gates_rc`; this row pins that it does not.

**Test 1b — branch wiring (addresses the "survives but is no longer wired"
gap).** Purely running the block cannot see a rename or a deleted branch in the
surrounding prose. For each rendered file, from the extracted block parse the
identifiers it **binds** (`gates_out`, `gates_rc` — handling both `if var=…` and
bare `var=…` forms), then assert against the text **after** the block:
- every bound identifier is referenced at least once after the block (catches a
  rename in the snippet that never propagated, or an orphaned binding);
- a branch keyed on the rc identifier together with the word `nonzero` exists
  (catches the diagnostic branch being dropped);
- **file-specific diagnosis pin** — the two paths have deliberately different
  contracts, so one shared pin would be wrong:
  - `task-workflow`: the `gates_rc`-nonzero bullet names `gates_out` and says
    `diagnose` (its contract is "STOP and diagnose using `gates_out`");
  - `aitask-pickrem`: the `gates_rc`-nonzero bullet routes to the
    `Abort Procedure` (its contract is abort, not inline diagnosis), and
    `gates_out` is consumed by the following branch.
  Both pins verified present in the current rendered output.

**Test 2 — negative controls.** Same fixture, run each rejected shape and assert
`REACHED_END` is *absent*. Two rows, because they are distinct spellings of the
same defect:
- the one-liner `gates_out="$(…)"; gates_rc=$?`;
- the **newline-separated** `gates_out="$(…)"` / `gates_rc=$?`.
Verified in this session: the newline form dies identically (exit 2, no
`REACHED_END`).

**Test 3 — the trail sweep loop.** Run the fixed loop shape under
`set -euo pipefail` over a matching file, a non-matching file and a missing
file; assert the candidate is printed, the read failure reaches stderr, the loop
reaches its end, and the exit status is 2. Negative control: the current
`grep -q …` + `case $? in` shape dies before the loop end.

**Test 4 — surface-wide drift guard (structural, not a one-line regex).**
A regex for the one-line spelling is not enough: the newline-separated form
recreates the identical defect and would read clean. Instead scan the fenced
```bash blocks of every authoring-source skill file (`.claude/skills/*/`,
`.agents/skills/*/`, `.opencode/skills|commands/*/`, excluding rendered `*-`
dirs) with a small awk pass that classifies **every** `$?` read by position:
- SAFE — a `||` appears on the same line *before* the `$?` (right operand of
  `||`, where errexit is suspended);
- SAFE — the line is exactly `<name>=$?` and the previous effective (non-blank,
  non-comment) line is `else` (the documented `if`/`else` form);
- otherwise **FLAG**.

Restricting to fenced blocks keeps `build-verification.md`'s prose warning
(which quotes the bad shape in backticks) from being a false positive.

Controls — the rule must be shown to discriminate, in both directions:
- positive: flags the one-line shape, the newline-separated shape, and a bare
  `case $?` after a simple command;
- negative: does **not** flag `x="$(…)" || rc=$?`, `{ … || [ "$?" = 1 ]; }`, or
  the `if`/`else` form.

Prototyped against the **current, unfixed** tree: it flags exactly the three
sites classified as bugs above (`task-workflow/SKILL.md:806`,
`aitask-pickrem/SKILL.md.j2:368`, `aitask-trail/SKILL.md.j2:468`) and none of
the four safe sites — so the guard is proven discriminating on
production-reachable cases before the fix, and must read clean after it.

### 4. Regenerate goldens and tracked pre-renders (same commit)

Goldens:
- `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
- `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md`
- `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`

using the loops documented in
`aidocs/framework/skill_authoring_conventions.md` ("Regenerate goldens after any
`.md.j2` or closure edit") and `tests/test_skill_render_task_workflow.sh`.

Tracked pre-rendered remote closures (gitignore has `!` exceptions for these —
9 dirs across claude/codex/opencode; `task-workflow-remote-*` and
`aitask-pickrem-remote-*` are the affected ones):

```bash
./.aitask-scripts/aitask_skill_rerender.sh remote
```

`aitask-pickweb` carries no gate-dispatch capture — confirmed unaffected.

## Verification

```bash
bash tests/test_skill_errexit_capture.sh          # new
bash tests/test_skill_render_task_workflow.sh     # goldens (procs)
bash tests/test_skill_render_aitask_pickrem.sh
bash tests/test_skill_render_aitask_trail.sh
bash tests/test_trail_skill_contract.sh
bash tests/test_skill_parity_runtime_vs_rendered.sh   # tracked pre-renders
bash tests/test_run_project_command.sh            # t1610 Test 6 canonical-place
./.aitask-scripts/aitask_skill_verify.sh
shellcheck -x tests/test_skill_errexit_capture.sh
```

`shellcheck` needs `-x` here: without it the two `source`/`.` lines raise SC1091
(info) and shellcheck exits 1 even with nothing wrong. `-x` follows the sourced
files and resolves them. The remaining SC2016 hits are annotated at their sites
(`# shellcheck disable=SC2016`) — each is verbatim shell or awk *source text*
handed to a driver, where single quotes are the point, not an oversight.

Review the golden diffs rather than rubber-stamping them: the only expected
changes are the three edited snippets.

## Risk

### Code-health risk: low
- None identified. The edits are three localized snippet replacements in
  agent-facing procedure markdown; no framework code path changes behavior. The
  one mechanical hazard — a missed golden or pre-render — fails loudly in
  `test_skill_render_*` / `test_skill_parity_runtime_vs_rendered.sh` rather than
  shipping silently, and both are in the verification list above.

### Goal-achievement risk: low
- A snippet-extraction test can pass **vacuously** if the extractor finds
  nothing · severity: low · → mitigation: discharged in-plan by the Test 1
  step-3 extractor positive control (non-empty + contains `ait gates run`).
- A drift guard can be **too narrow to ever match**, reporting clean while an
  equivalent spelling reintroduces the defect · severity: medium · → mitigation:
  discharged in-plan by the Test 4 structural scanner (position-based, not a
  one-line regex) plus its two-directional controls, prototyped against the
  unfixed tree.
- The snippet can survive `set -e` while the surrounding branch is **no longer
  wired to it** (renamed variable, dropped diagnostic branch), so users again
  get a bare failure · severity: medium · → mitigation: discharged in-plan by
  Test 1b (bound-identifier consumption + per-file diagnosis pins) and Test 1
  step 5's `gates_out`-payload assertion.

**`risk_mitigations_planned = false`** — every bullet is discharged by a required
step of this plan, not by additional before/after work, so there is nothing
further for the user to choose a disposition for.

## Step 9 (Post-Implementation)

Standard: commit code + plan, run the declared `risk_evaluated` gate via
`./ait gates run 1621`, then archive task and plan.

## Final Implementation Notes

- **Actual work done:** Exactly the four planned changes. (1) Both named
  gate-dispatch sites now use the `if`/`else` capture form, each with a
  one-sentence pointer to `build-verification.md` rather than a restated
  rationale. (2) The `aitask-trail` incoming-`verifies` sweep captures grep's
  status with `|| grep_rc=$?` and switches on `"$grep_rc"`; a fourth
  load-bearing-property bullet documents the errexit hazard. (3) New
  `tests/test_skill_errexit_capture.sh` — 65 assertions across the five layers
  the plan specified. (4) 7 goldens regenerated and 6 tracked `-remote-`
  pre-rendered files rerendered.

- **Deviations from plan:** Two, both additive.
  - The trail prose said "Three exit-status properties" and the new bullet made
    it four; the count was corrected in the same edit. A stale count in a
    "do not simplify these back" list is exactly the kind of thing that gets a
    property dropped.
  - The plan's verification line `shellcheck tests/...` exits 1 on SC1091 (info,
    from the two `source` lines) even when nothing is wrong. Contract changed to
    `shellcheck -x`, which follows the sourced files; the 7 SC2016 hits are
    annotated at their sites with a justification (each is verbatim shell/awk
    *source text* handed to a driver, where the single quotes are the point).
    `shellcheck -x` now exits 0.

- **Issues encountered:**
  - `aitask_skill_rerender.sh remote` reports the `task-workflow-remote-` dirs
    as "orphaned" (task-workflow authors from `SKILL.md`, not `SKILL.md.j2`) and
    skips them directly. They are still refreshed, but only transitively, via
    the closure walk of `aitask-pickrem` / `aitask-pickweb`. Verified all three
    agent copies actually changed before committing rather than trusting the
    driver's own summary line.
  - `tests/test_skill_render_aitask_pickrem.sh` Test 6 compares the pre-renders
    against `git show HEAD:`, so it failed until the pre-renders were committed.
    Re-run after the code commit: 67/67.
  - `tests/test_skill_render_task_workflow.sh` currently reports 197/200 — the
    three golden diffs are **entirely** the concurrent session's uncommitted
    `--link-worktree` block, whose owner regenerates those goldens with their
    change. This commit is self-consistent on its own: rendering
    `git show HEAD:.claude/skills/task-workflow/SKILL.md` reproduces all three
    committed goldens byte-for-byte.

- **Key decisions:**
  - **The drift guard is structural, not a regex.** A regex for the one-line
    spelling reports clean on the newline-separated form, which is the identical
    defect (verified: it also dies with no `REACHED_END`). The guard instead
    classifies every `$?` *read* inside fenced bash blocks by position — safe
    only as the right operand of `||`, or as a lone `x=$?` directly under
    `else`. Restricting to fenced blocks is what keeps `build-verification.md`'s
    prose warning (which quotes the bad shape in backticks) from being a false
    positive. Prototyped against the *unfixed* tree: it flagged exactly the three
    sites classified as bugs and none of the four safe ones.
  - **The diagnosis pins are per-file, because the two paths differ on purpose.**
    `task-workflow` (attended) must "STOP and diagnose using `gates_out`";
    `aitask-pickrem` (headless) routes to the Abort Procedure and consumes
    `gates_out` in the next branch. One shared assertion would have been wrong
    for one of them.
  - **Committed only the enumerated paths.** A concurrent session was editing
    `.aitask-scripts/aitask_init_data.sh`, `aitask_setup.sh`,
    `.aitask-scripts/lib/data_symlinks.sh` (untracked), `tests/lib/test_scaffold.sh`
    and `.gitignore` during this task. None are t1621's; the commit uses
    `git commit -o -- <paths>` so they could not be absorbed. They are left
    untouched for their owner.

    **Path-scoping is not sufficient on its own.** That same session also added a
    `--link-worktree` block to `.claude/skills/task-workflow/SKILL.md` — a file
    t1621 *does* own — between this task's last `git diff --stat` and its commit,
    so `-o --` committed the file's then-current content and absorbed their hunk.
    It was split back out with `git commit --amend -o -- <that one file>` and
    restored to the working tree byte-identically (verified: the remaining
    working-tree delta for that file is their block, all additions). The lesson:
    with a concurrent session running, re-read the diff of every file you are
    about to commit *at commit time*, not just the path list.

- **Tests can fail — proven by mutation, not asserted:**
  - reverting the fix → 13 failures, including the drift guard;
  - renaming `gates_out` inside the block only → the Test 1b wiring assertion
    fires on the orphaned binding (this is the "survives but is no longer wired"
    case the runtime rows alone would not have pinned);
  - rewriting to the newline-separated form → the guard flags it.
  Each probe restored the file byte-identically before the next.

- **Upstream defects identified:** None.
