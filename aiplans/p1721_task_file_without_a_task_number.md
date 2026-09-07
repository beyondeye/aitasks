---
Task: t1721_task_file_without_a_task_number.md
Branch: (current branch — profile `fast`, `create_worktree: false`)
Base branch: main
Output branch: main
---

# t1721 — Task file without a task number

## Context

`aitasks/t_refresh_codeagent_suite_default_model_expectations.md` carries no task
number: the `t` prefix is followed directly by the name. `ait ls` lists it (the
parent glob is `t*_*.md`, which matches), but no consumer can derive an id from
it — every consumer mapping a listing row back to a task id either skips it or
produces an empty id, and an empty id passed onward asks about a task that cannot
exist. `aitask_backlog_roadmap.sh` reports it as `UNPARSABLE_TASK_FILE:` and names
it in the published trail's method note, but that is a workaround at **one**
consumer, not a fix.

Two findings from exploration settle the open questions in the task's `## Scope`:

1. **The file's content is obsolete.** Commit `173a51698` ("test: Derive
   code-agent default expectations instead of pinning models (t1318)") already
   fixed all three tests it names, by deriving expectations from the resolver
   instead of pinning model literals. Verified by running them:
   `test_codeagent_work_report.sh` 28/28, `test_codeagent_trail.sh` 27/27,
   `test_shadow_spawn_learner.sh` 22/22. The one surviving `opus4_8` literal
   (`test_shadow_spawn_learner.sh:46`) is the explicit-override test the file
   itself asked to preserve. t1318 was created 21 minutes after this file and is
   archived.
2. **There is no producing code path to fix.** The file was hand-written into
   `aitasks/` as a side-file of commit `9e7f18326` ("ait: Revert t1311 to Ready"),
   never through `ait create` — which is why it has no id. `ait create` always
   claims an id from the atomic counter, so the only producer of an unnumbered
   file is an agent writing one directly. The remedy therefore has to sit at the
   consumer/hygiene level, not at a producer.

It is the **only** violation in the tree: `find -L aitasks -name 't*.md'` returns
900 files, exactly one of which fails `^t[0-9]+(_[0-9]+)?_.*\.md$`. (`aitasks` is
a symlink to `.aitask-data/aitasks`, so every scan must use `find -L`.)

**Outcome:** the unnumbered file is renumbered and archived as superseded, `ait ls`
stops emitting unaddressable rows and says so on stderr, and a repo invariant test
makes the whole class un-reintroducible.

## Ordering and commit sequencing (matters)

The guard lands **before** the disposition, so both new tests can be proven to
fail against the real repo on real data rather than only against a fixture:

- Before disposition, `ait ls -s all 0` emits **380** parent rows including the
  unnumbered one; after the guard it must emit **379** plus one stderr warning.
  `--all-levels` and `--tree` are **527** each and must become **526**.
- Before disposition, `tests/test_task_filename_invariant.sh` must **fail** against
  the live repo, naming the file. After disposition it passes.

Both observations are recorded in the task's Final Implementation Notes.

**That deliberate red window must never reach a commit.** Task/plan data lives on
the separate `aitask-data` branch (`.aitask-data` is its own git worktree — `git
worktree list` confirms), so `./ait git` and plain `git` commit to different
branches and the archive physically cannot share a commit with the code. The
hazard is therefore not a mixed commit but a **knowingly-red test committed to
`main`**. The transaction is:

1. **Working tree only, nothing committed.** Apply the step-1 guard and write both
   test files. Run them. Record the pre-disposition failure output of
   `tests/test_task_filename_invariant.sh` (it names the offending path) and the
   three `listing_parity_check` counts into the task's Final Implementation Notes
   text — these are the observations, captured before they become unobservable.
2. **Disposition commits alone, on the data branch.** Renumber and archive
   (step 4), committed with `./ait git`. Nothing from `main` is staged.
3. **Re-run `tests/test_task_filename_invariant.sh` — it must now be green.**
4. **Only then commit the code.** `git add` the guard, both tests and the two doc
   files and commit to `main`. `main` never carries a red test at any commit.

Consequence to accept deliberately: a checkout of the `main`-side commit against an
**older** `aitask-data` (one that still holds the unnumbered file) will see the
invariant test fail. That is correct behavior — the test is asserting a property of
the task data, and the data at that point genuinely violates it.

## Steps

### 1. Guard `aitask_ls.sh` against unaddressable rows

`.aitask-scripts/aitask_ls.sh`, in `process_task_file()` (~line 712), immediately
after `filename=$(basename "$file_path")` and **before** `parse_task_metadata`:

```bash
    # A listing row whose filename carries no task id cannot be addressed: every
    # consumer that maps a row back to an id either skips it or derives an empty
    # id, and an empty id asks about a task that cannot exist (t1721). Drop it
    # from stdout and say so on stderr — a silent skip would hide a Ready task.
    local id_pattern='^t[0-9]+_'
    [[ "$task_type" == "child" ]] && id_pattern='^t[0-9]+_[0-9]+_'
    if [[ ! "$filename" =~ $id_pattern ]]; then
        warn "task file without a task number, skipped: $file_path"
        return
    fi
```

- `warn()` comes from `lib/terminal_compat.sh` (sourced transitively via
  `lib/task_utils.sh`) and already writes to stderr — the same channel and shape
  as the existing duplicate-id warning at line 313 and the dependency-scan warnings
  at line 355. Reuse it; do not hand-roll an `echo -e "\033[1;33m…"`.
- Placement inside `process_task_file` (rather than tightening the four call-site
  globs) keeps the "the boardcol scan globs a strict superset of what this script
  lists" invariant documented at line 415 intact — the guard only ever *narrows*
  what is listed. It also covers all four modes (`--children`, `--tree`,
  `--all-levels`, default) from one site.
- Row output is redirected into `$output_file` by the callers, so the stderr
  warning still reaches the terminal.

### 2. Fixture test for the guard

New file `tests/test_ls_unnumbered_task_file.sh`, following
`tests/test_ls_display_and_filters.sh` exactly: build a real fixture repo under
`mktemp -d`, run the **real** `$PROJECT_DIR/.aitask-scripts/aitask_ls.sh` against
it, keep test bodies in the main shell (so the in-process `PASS`/`FAIL` counters in
`tests/lib/asserts.sh` are correct — no file-backed opt-in needed).

Fixture: `t10_numbered.md`, `t_no_number_here.md`, `aitasks/t10/t10_1_child.md`,
`aitasks/t10/t10_x_not_a_number.md`, plus `aitasks/metadata/task_types.txt`.

Assertions:
- default mode: stdout contains `t10_numbered.md`, does **not** contain
  `t_no_number_here.md`, and the row count is exactly 1 (a positive count, not
  just "absent" — a broken fixture that lists nothing must not read as a pass);
- stderr contains `task file without a task number` **and** names
  `t_no_number_here.md`;
- `--all-levels`: `t10_1_child.md` is listed, `t10_x_not_a_number.md` is not and
  is named on stderr — this pins the child branch of `id_pattern`, which the
  parent-only case cannot reach;
- `--tree`: same two assertions as default mode (malformed parent absent from
  stdout, named on stderr) plus `t10_1_child.md` still indented under
  `t10_numbered.md`. Tree mode is **not** redundant with default mode: its loop
  derives `task_num` from the filename itself (`grep -oE '^t[0-9]+'`) *before*
  calling `process_task_file`, so an unnumbered parent yields an empty
  `task_num` and a `$TASK_DIR/t` child lookup. The shared guard suppresses the
  row today — confirmed live: `ait ls -s all --tree 0` currently emits the
  unnumbered file as row 527 of 527 — but nothing else pins that, and a future
  change to the tree path could reintroduce the malformed row unseen by the
  other two modes. Asserted here rather than deferred to a follow-up: it is
  three assertions in a file this task is already creating;
- **negative control:** a numbered fixture repo with no violations produces an
  empty stderr in all three modes, proving the warning is not emitted
  unconditionally.

### 3. Repo filename invariant test

New file `tests/test_task_filename_invariant.sh`, shaped like
`tests/test_no_raw_tmux.sh` (repo-invariant guard, `set -uo pipefail`,
`tests/lib/asserts.sh`). The scan is a **function taking a root**, so the same code
runs against both the live repo and a fixture:

```bash
scan_unnumbered() {   # $1 = root dir; prints one offending path per line
    find -L "$1" -type f -name 't*.md' -printf '%p\n' 2>/dev/null |
        while IFS= read -r p; do
            case "$(basename "$p")" in
                t[0-9]*) printf '%s\n' "$p" | grep -qE '/t[0-9]+(_[0-9]+)?_[^/]*\.md$' || printf '%s\n' "$p" ;;
                *) printf '%s\n' "$p" ;;
            esac
        done
}
```

- `find -L` is mandatory: `aitasks` is a symlink, and a plain `find` returns zero
  files. (`aitask_followup_backfill.sh:142` already uses `-L` for the same reason.)
- Scope is the whole of `aitasks/`, **archived included** — an unnumbered file in
  `aitasks/archived/` is equally unaddressable. `old.tar.zst` bundles are not `.md`
  and are not matched.

Two assertions:
1. **Live repo:** `scan_unnumbered "$PROJECT_DIR/aitasks"` returns zero lines; on
   failure print every offending path.
2. **Fixture negative control:** a `mktemp -d` tree holding one conforming and one
   non-conforming file returns exactly 1 line, and it is the non-conforming path.
   This is what keeps assertion 1 from being a tautology once the repo is clean.

### 4. Disposition — renumber, then archive as superseded

**Entry condition — read carefully, it is not "steps 1–3 all green".** Proceed only
when both of these hold:

- `tests/test_ls_unnumbered_task_file.sh` and the three existing regression suites
  are **green**, and the three `listing_parity_check` counts have been observed;
- `tests/test_task_filename_invariant.sh` is **red**, its live-repo assertion naming
  `aitasks/t_refresh_codeagent_suite_default_model_expectations.md` and its fixture
  negative-control assertion passing, and that output has been **captured verbatim**.

That red is the required state, not a blocker: it is the negative control on real
data, and it becomes unobservable the moment this step runs. A green invariant test
*before* this step means the scan is not seeing the file — stop and fix the scan
(most likely a missing `find -L`) rather than proceeding.

After this step the invariant test must turn **green** (Verification step 4). Only
then is the code committed to `main`.

```bash
new_id=$(./.aitask-scripts/aitask_claim_id.sh --claim)     # counter currently peeks 1727
./ait git mv aitasks/t_refresh_codeagent_suite_default_model_expectations.md \
             "aitasks/t${new_id}_refresh_codeagent_suite_default_model_expectations.md"
```

Then, in the renamed file: keep `anchor: 1162`, `boardidx`, and the existing body
unchanged, and append a `## Resolution` section recording that the work was
completed by **t1318** in commit `173a51698`, that the three named suites were
re-run green on 2026-09-07, and that `test_shadow_spawn_learner.sh:46`'s remaining
`opus4_8` is the deliberate explicit-override case. Commit with `./ait git`.

Archive:

```bash
./.aitask-scripts/aitask_archive.sh --dry-run --superseded "$new_id"
./.aitask-scripts/aitask_archive.sh --superseded --ignore-gates "$new_id"
```

`--ignore-gates` is required and is the sanctioned escape hatch: the file declares
`gates: [risk_evaluated]`, no gate was ever run against it, so `gate_guard()` will
emit `GATE_PENDING:risk_evaluated` + `GATE_BLOCKED` and exit 2 without it. Run the
`--dry-run` first and confirm that is the only blocker before overriding. The
script sets `status: Done`, adds `archived_reason: superseded`, and commits; there
is no plan file to move.

### 5. Documentation

- `website/content/docs/commands/task-management.md` — a short bolded paragraph in
  the **`ait ls`** section (after "**View modes:**", before "**Metadata format:**"),
  matching the existing "**Board column.**" / "**Follow-up kind**" prose shape:
  a task file whose name carries no id is skipped, with a warning on stderr naming
  the path, because a listing row that cannot be addressed is worse than a missing
  one. It goes here, **not** in the `ait create` Key features list next to the
  duplicate-ID bullet: that list is about ID assignment at creation time, and
  filing `ait ls` behavior under `ait create` both hides it from anyone reading the
  `ait ls` reference and implies it is creation behavior.
- `website/content/docs/development/task-format.md` — one sentence after the
  naming-convention sentence (line 11): the convention is load-bearing, not
  cosmetic; a file that does not match it is skipped by `ait ls`.

Then, per `CLAUDE.md`: `cd website && python3 check_links.py --build`.

## Verification

Run in this order — steps 1–3 happen with **nothing committed** (see Commit
sequencing above).

```bash
# 1. Guard, observed on real data BEFORE the disposition (listing_parity_check)
./.aitask-scripts/aitask_ls.sh -s all 0 2>/dev/null | wc -l                # expect 379 (was 380)
./.aitask-scripts/aitask_ls.sh -s all --all-levels 0 2>/dev/null | wc -l   # expect 526 (was 527)
./.aitask-scripts/aitask_ls.sh -s all --tree 0 2>/dev/null | wc -l         # expect 526 (was 527)
./.aitask-scripts/aitask_ls.sh -s all 0 2>&1 >/dev/null | grep t_refresh   # expect the warning
# and confirm the lost row IS the unnumbered file, not some other task:
./.aitask-scripts/aitask_ls.sh -s all 0 2>/dev/null | grep -c t_refresh    # expect 0

# 2. New tests
bash tests/test_ls_unnumbered_task_file.sh          # expect all pass
bash tests/test_task_filename_invariant.sh          # expect FAIL — capture the output verbatim

# 3. Regression: the ls suites that already exist
bash tests/test_ls_display_and_filters.sh
bash tests/test_ls_boardcol_filter.sh
bash tests/test_task_levels.sh

# 4. Disposition (archive_dry_run first), committed on the data branch alone
bash tests/test_task_filename_invariant.sh          # expect PASS now
find -L aitasks -name 't*.md' -printf '%f\n' | grep -cvE '^t[0-9]+(_[0-9]+)?_.*\.md$'   # expect 0

# 5. Lint, then commit the code to main
shellcheck .aitask-scripts/aitask_ls.sh
shellcheck tests/test_ls_unnumbered_task_file.sh tests/test_task_filename_invariant.sh

# 6. Docs
cd website && python3 check_links.py --build
```

**Forced-failure control for the ls guard** (prove it discriminates): temporarily
change `id_pattern` to `^t` in a scratch copy of the fixture run and confirm
`tests/test_ls_unnumbered_task_file.sh` goes red on the "does not contain" and
stderr assertions. Restore by reverting only that edit — never `git checkout`.

## Risk

### Code-health risk: low

- The guard sits in `aitask_ls.sh`, which the board, `aitask-pick`, the minimonitor
  picker and the roadmap all consume; an over-broad `id_pattern` would silently
  hide legitimate tasks — a much worse failure than the one being fixed ·
  severity: medium · → mitigation: inline post-phase `listing_parity_check`
  (verification step 1 pins the live-repo row counts at exactly one row lost, in
  all three of parents-only, `--all-levels` and `--tree`, and the fixture test
  asserts a positive hit count for the conforming task in each mode rather than
  only asserting absence).
- `--ignore-gates` on the archive is a real bypass of the t635_4 gate guard ·
  severity: low · → mitigation: inline pre-phase `archive_dry_run` (step 4 runs
  `--dry-run` first and confirms `GATE_PENDING:risk_evaluated` is the *only*
  blocker before the override; the gate was never run, so nothing is being
  papered over).

### Goal-achievement risk: low

- The `ait ls` guard protects one consumer; `aitask_claim_id.sh`,
  `aitask_attach.sh`, `aitask_artifact.sh` and `aitask_find_by_file.sh` all still
  glob `t*.md` loosely. **What this does not buy:** unnumbered files are not made
  impossible at every consumer — the repo invariant test is what covers that class,
  and it covers it at test time, not at runtime, and only for this repo · severity:
  low · → mitigation: none — accepted, and stated explicitly in the doc wording so
  the claim matches the behavior.

### Planned mitigations
- timing: pre-phase | name: archive_dry_run | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: `--ignore-gates` bypasses the t635_4 gate guard | desc: dry-run the archive first and confirm `GATE_PENDING:risk_evaluated` is the only blocker before overriding
- timing: post-phase | name: listing_parity_check | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: an over-broad `id_pattern` silently hides legitimate tasks | desc: pin the live-repo `ait ls` row counts at exactly one row lost in all three of parents-only, `--all-levels` and `--tree`, and confirm the lost row is the unnumbered file

**Reassessment after inlining:** both mitigations add verification only — no new
code paths, no new files beyond the two already planned. Levels are unchanged:
code-health **low**, goal-achievement **low**.

### Pre-phase (risk mitigations)

- **archive_dry_run** — before the `--superseded --ignore-gates` archive in step 4,
  run `aitask_archive.sh --dry-run --superseded "$new_id"` and confirm
  `GATE_PENDING:risk_evaluated` is the only reported blocker.

### Post-phase (risk mitigations)

- **listing_parity_check** — after step 1 and **before** the disposition, run all
  three live-repo row counts from Verification step 1 (parents-only 380→379,
  `--all-levels` 527→526, `--tree` 527→526) and confirm exactly one row disappears
  in each mode, and that the disappeared row is the unnumbered file (not some other
  task). Record the numbers in the Final Implementation Notes — after the
  disposition they are no longer observable.

## Step 9 (Post-Implementation)

Standard: commit on the current branch (`fast` profile, no worktree, no merge),
following the four-step transaction in **Ordering and commit sequencing** above.
Record Final Implementation Notes in `aitasks/t1721_*.md` including the three
`listing_parity_check` before/after counts and the verbatim pre-disposition failure
output of `tests/test_task_filename_invariant.sh`, then archive t1721 (`gates:
[risk_evaluated]` must be `pass` first).
