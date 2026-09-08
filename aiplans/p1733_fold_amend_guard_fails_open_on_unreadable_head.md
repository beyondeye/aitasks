---
Task: t1733_fold_amend_guard_fails_open_on_unreadable_head.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1733 — `_fold_amend_guard` fails open on an unreadable HEAD

## Context

`_fold_amend_guard` in `.aitask-scripts/aitask_fold_mark.sh` decides whether HEAD
is this fold's own commit before rewriting it with `git commit --amend`. Its
header declares it DEFAULT-DENY with "deliberately no warn-and-proceed bucket",
but its HEAD probe is written as:

```bash
done < <(task_git show --name-only --format='' HEAD 2>/dev/null || true)
```

`|| true` turns two distinct failures into "nothing foreign", so the `foreign`
array stays empty and the guard **returns 0 — authorising a history rewrite of a
commit whose contents were never read**:

1. **A failed probe** (git exits non-zero) hands back an empty list.
2. **A merge commit**, for which `git show --name-only` legitimately prints no
   path list.

**Both confirmed empirically** against the current build (temp-repo probe,
`--commit-mode amend`):

| HEAD shape | pre-fix outcome |
|---|---|
| merge commit | guard **permits**; prints `AMENDED`; **the merge commit's SHA is rewritten** |
| unborn/orphan branch | guard **permits**; the amend then fails on its own, so the run dies with the misleading `fold amend-commit failed` |

The merge case is a live fail-open: a history rewrite that the guard exists to
stop. The unborn case does not rewrite anything (git cannot), but the guard still
approved it and the user is told the wrong reason.

`lib/task_utils.sh::task_git_commit_scoped` already states the rule this must
follow — capture the probe's exit status separately so a failing probe reads as
*unverified*, never as *clean*. t1599_4 closed the identical shape in
`aitask_issue_import.sh` (`:657-666`) but deliberately did not reach across into
`aitask_fold_mark.sh`, which is t1599_2's file.

## Implementation

### 1. `.aitask-scripts/aitask_fold_mark.sh` — fix the probe (`_fold_amend_guard`, ~:916)

Move the `head_short` resolution **above** the probe (it is only used in refusal
messages, and both new refusals need it), then replace the process-substitution
feed with a status-capturing read, mirroring `aitask_issue_import.sh:657-666`:

```bash
    head_short="$(task_git rev-parse --short HEAD 2>/dev/null || echo "HEAD")"

    # Capture the probe's exit status separately, and treat an EMPTY path list as
    # unverified rather than as "nothing foreign". Same rule as
    # task_git_commit_scoped's `git status` handling: a failing probe must never
    # read as clean. `|| true` here was fail-OPEN in both directions -- a failed
    # `git show` handed back an empty list, and an empty list is also exactly what
    # `git show --name-only` prints for a MERGE commit.
    local head_paths="" show_rc=0
    head_paths="$(task_git show --name-only --format='' HEAD 2>/dev/null)" || show_rc=$?
    if (( show_rc != 0 )); then
        _fold_amend_refusal="refusing --commit-mode amend: could not read the path list of HEAD (${head_short}); git exited ${show_rc}. Refusing to amend a commit whose contents are unverified.
Re-run with --commit-mode fresh."
        return 1
    fi
    if [[ -z "${head_paths//[[:space:]]/}" ]]; then
        _fold_amend_refusal="refusing --commit-mode amend: HEAD (${head_short}) reports no paths — an empty or merge commit, whose contents cannot be verified.
Re-run with --commit-mode fresh."
        return 1
    fi

    while IFS= read -r p; do
        ...unchanged body...
    done <<< "$head_paths"
```

Notes:
- `local head_paths="" show_rc=0` is declared on its own line before the capture,
  so `set -euo pipefail` sees the `||` absorb the non-zero status rather than a
  masked `local x=$(...)`.
- Both messages keep the file's existing `refusing --commit-mode amend: …` /
  `Re-run with --commit-mode fresh.` shape, so the caller gets the recovery route.
- The refusal path is unchanged: the Step 6 caller runs `_fold_rollback` and
  `die`s, exactly as for the foreign-path and published-HEAD refusals.
- Update the function's header comment to record that an unreadable or empty HEAD
  now refuses.

**No legitimate fold is newly refused.** A root commit *does* list its paths
(verified), and the only production callers of `--commit-mode amend`
(`aitask-explore`, `aitask-pr-import`, `aitask-contribution-review`) amend a
single-parent task-creation commit they just made.

### 2. `tests/test_fold_mark.sh` — pin both directions

Add a pre-fix mutant installer next to the existing `install_prefix_commit_block`
(which is unusable here — it strips the guard entirely, so it cannot tell the
`|| true` shape apart from no guard at all):

```
install_prefix_amend_probe()   # python3 rewrite of the fixture's copy: replace the
                               # status-capturing block with the `|| true` shape.
                               # Fails loudly if the anchor is missing, and verifies
                               # the mutation landed, so the controls below can never
                               # pass vacuously against an unmutated build.
```

Then three tests plus their controls:

| test | asserts |
|---|---|
| `test_amend_refuses_merge_head` | merge HEAD ⇒ exit 1, message says "no paths", **HEAD SHA unchanged**, fold mutations rolled back (`assert_no_fold_residue`, t20 back to `Ready`) |
| `test_amend_refuses_unreadable_head` | orphan/unborn HEAD ⇒ exit 1, message says "unverified" and points at `--commit-mode fresh`, and is **not** `fold amend-commit failed` |
| `test_amend_refuses_failed_head_probe` | a `PATH` shim that fails only `git show --name-only` (everything else passes through to real git), over an otherwise **clean, amendable** HEAD ⇒ exit 1, refusal says "unverified", **HEAD SHA unchanged** |

| negative control | must observe against the mutant |
|---|---|
| `test_negative_control_merge_head_rewritten` | pre-fix build **rewrites** the merge commit and prints `AMENDED` |
| `test_negative_control_failed_probe_amends` | pre-fix build **amends successfully** under the failing-probe shim |
| `test_negative_control_unborn_head_wrong_reason` | pre-fix build dies with `fold amend-commit failed`, not a guard refusal |

Register all six in the footer under a `# t1733` block.

### Fixture preconditions — asserted, not assumed

Each refusal above is only meaningful if the fixture actually has the shape it
claims. `git show --name-only` printing nothing is the *symptom* the guard keys
on, and several unrelated fixture accidents produce it — so without a
precondition assertion a test could pass through a different empty-or-unreadable
condition and prove nothing about merge commits, and its mutant control could
"observe the defect" with no merge commit involved at all. Add shared helpers and
assert the precondition **before** invoking the fold, in both the test and its
control:

```bash
# Parents of HEAD (2 == a merge commit).
_head_parent_count() {
    local -a f=()
    read -r -a f < <(git rev-list --parents -n1 HEAD)
    echo $(( ${#f[@]} - 1 ))
}
# The non-empty path lines `git show --name-only` prints for HEAD ("" for a merge).
_head_name_only_paths() { git show --name-only --format='' HEAD 2>/dev/null | sed '/^$/d'; }

assert_merge_head_fixture() {   # the documented merge-output shape
    local desc="$1"
    assert_eq "$desc: HEAD is a merge (two parents)" "2" "$(_head_parent_count)"
    assert_eq "$desc: merge HEAD prints no paths" "" "$(_head_name_only_paths)"
}
```

| fixture | precondition asserted before the fold runs |
|---|---|
| merge HEAD (test + control) | `assert_merge_head_fixture` — HEAD has **two parents** *and* `git show --name-only --format='' HEAD` yields no non-empty path |
| orphan/unborn HEAD (test + control) | `git show --name-only --format='' HEAD` exits **non-zero** (the probe genuinely fails), and `git rev-parse HEAD` fails |
| failing-probe shim (test + control) | under the shim `git show --name-only` exits non-zero, **and** without the shim HEAD is a single-parent commit that lists exactly the fold's own paths — i.e. a HEAD the fixed guard would otherwise **permit**, so the refusal can only come from the probe failure |

The third row is what makes `test_amend_refuses_failed_head_probe` a real control
rather than a coincidence: it pins that the *only* difference from a permitted
amend is the failed probe.

**Why the third test exists.** On an orphan branch the amend cannot succeed
anyway, so `test_amend_refuses_unreadable_head` can only discriminate on the
refusal *message*. `test_amend_refuses_failed_head_probe` is the case where the
amend **would** have succeeded — it is the only one that proves a failed probe
does not authorise a rewrite. If the `PATH` shim turns out not to reach
`task_git` (it calls `git` by bare name, so it should), I will say so rather than
drop the coverage silently.

## Verification

```bash
bash tests/test_fold_mark.sh          # whole file, incl. permit tests 7 and 11
shellcheck .aitask-scripts/aitask_fold_mark.sh
```

- All existing tests stay green — in particular the permit direction
  (`test_amend_permits_labels_file_in_head`,
  `test_amend_permits_child_primary_parent_file`, `test_fresh_mode_full_flow`),
  so the tightening does not start refusing legitimate folds.
- Each new control is run **against the mutant** and must report the defect; the
  installer verifies its own substitution landed first, and every fixture asserts
  its precondition before the fold runs (see "Fixture preconditions" above).
- Also run the neighbouring guard suite, which shares the precedent shape:
  `bash tests/test_issue_import_amend_guard.sh`.

## Risk

### Code-health risk: low

- Refusing a merge/empty HEAD is a behavior change: a fold that previously
  "succeeded" (by silently rewriting a merge commit) now hard-fails and rolls
  back. · severity: low · → mitigation: none needed — consistent with the guard's
  three existing refusals, all of which roll back and `die`, and the message
  names `--commit-mode fresh` as the recovery.
- Blast radius is one function in one script plus one test file. · severity: low
  · → mitigation: none needed.

### Goal-achievement risk: medium

- This closes the fail-open probe at the **second** of an unknown number of sites
  in the same class. A sweep found at least two further authorization sites with
  the same `|| true` shape gating a destructive action — `aitask_sync.sh`
  `_rebase_advance` (a failed `diff --diff-filter=U` reads as "no conflicts" and
  proceeds to `rebase --skip`, which **discards a commit**) and
  `aitask_setup.sh:3585-3596` (a failed dirtiness probe reads as clean). Fixing
  only this site leaves the class alive. · severity: medium · → mitigation:
  sweep_failopen_git_probes

### Planned mitigations
- timing: after | name: sweep_failopen_git_probes | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — the fail-open git-probe class survives at other authorization sites | desc: Audit every framework site where a fail-open (or-true suppressed) git probe gates a destructive or authorizing action and apply the capture-the-status-separately rule; known candidates are aitask_sync.sh::_rebase_advance (failed conflict probe reads as no-conflicts, then rebase --skip discards a commit) and aitask_setup.sh:3585-3596 (failed dirtiness probe reads as clean)

## Implementation record

Landed as planned; no deviations from the approved design.

- `.aitask-scripts/aitask_fold_mark.sh` — `_fold_amend_guard`: `head_short`
  resolution moved above the probe; the `|| true` process substitution replaced
  by a status-capturing read plus the two refusals (`show_rc != 0` ⇒
  "unverified", empty path list ⇒ "reports no paths"); loop fed from
  `<<< "$head_paths"`. Function header records that default-deny now extends to
  the probe itself.
- `tests/test_fold_mark.sh` — `install_prefix_amend_probe()` (mutant installer
  that regresses **only** the probe and verifies the substitution landed, while
  asserting the rest of the guard survived), the `PATH`-shim helper, the
  precondition asserts, and 3 tests + 3 negative controls, registered under a
  `# t1733` footer block.

**One rename beyond the plan:** the plan's `_head_parent_count` used a local
array named `f`, which collided with a later `local f=` in the mutant installer
(shellcheck SC2178/SC2128). Renamed to `parts` / `script`.

### Verification results

- `bash tests/test_fold_mark.sh` → **270/270 passed** (was 264 before; +6).
  Permit direction unchanged: `test_amend_permits_labels_file_in_head`,
  `test_amend_permits_child_primary_parent_file`, `test_fresh_mode_full_flow`.
- `bash tests/test_issue_import_amend_guard.sh` → **44/44 passed**.
- All 18 other test files referencing `aitask_fold_mark` → exit 0.
- `shellcheck .aitask-scripts/aitask_fold_mark.sh` → only pre-existing SC1091 /
  SC2012 informational findings; none in the new code.

**Controls discriminate.** Measured against the pre-fix shape in a scratch repo
before the fix, and re-confirmed by the mutant controls:

| fixture | pre-fix | post-fix |
|---|---|---|
| merge HEAD | `AMENDED`; **merge commit SHA rewritten** | refused; SHA intact |
| failed probe (shim) | `AMENDED`; HEAD rewritten | refused; HEAD intact |
| unborn HEAD | permitted, then died `fold amend-commit failed` | refused by the guard as "unverified" |

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan. `_fold_amend_guard` in
  `.aitask-scripts/aitask_fold_mark.sh` now resolves `head_short` before the
  probe, captures `git show --name-only --format='' HEAD` with its exit status
  held separately, and refuses on two distinct conditions — a non-zero probe
  ("contents are unverified") and an empty path list ("reports no paths — an
  empty or merge commit"). The `foreign` loop is fed from the captured string.
  `tests/test_fold_mark.sh` gained `install_prefix_amend_probe()`,
  `install_failing_show_shim()`, the fixture-precondition helpers, three tests
  and three negative controls (264 → 270 assertions).
- **Deviations from plan:** One. The plan's `_head_parent_count` used a local
  array named `f`, colliding with a `local f=` in the mutant installer and
  tripping shellcheck SC2178/SC2128. Renamed to `parts` and `script`
  respectively. No behavioral difference.
- **Issues encountered:** The orphan-branch fixture that `tests/test_issue_import_amend_guard.sh`
  A6a uses does **not** discriminate behaviorally here: on an unborn branch the
  amend cannot succeed anyway, so pre-fix and post-fix both exit 1 and roll back
  — only the message differs. That is why the third test exists: a `PATH` shim
  that fails **only** `git show --name-only`, over a HEAD the guard would
  otherwise permit, is the only fixture where the amend *would* have succeeded,
  and therefore the only one that proves a failed probe does not authorise a
  rewrite. Its control confirms the pre-fix build prints `AMENDED` and rewrites
  HEAD under that shim.
- **Key decisions:**
  - Refusals `die` and roll back rather than falling back to `--commit-mode
    fresh`, matching the guard's three existing refusals; both messages name
    `fresh` as the recovery route.
  - The mutant installer regresses **only the probe** and asserts that
    `_fold_amend_guard` and the foreign-path refusal survive — the existing
    `install_prefix_commit_block` excises the whole guard and so cannot tell a
    fail-open guard from no guard at all.
  - Every fixture asserts its precondition before invoking the fold (merge HEAD:
    two parents *and* an empty path list; unborn: probe fails *and* HEAD does not
    resolve; shim: probe fails *and* the unshimmed HEAD lists exactly the fold's
    own primary). "git show printed nothing" is the symptom the guard keys on,
    and unrelated fixture accidents produce it — without the preconditions a test
    could satisfy the refusal for the wrong reason and its control could
    "observe the defect" with no merge commit involved.
  - No legitimate fold is newly refused: a root commit *does* list its paths
    (verified empirically), and the production callers of `--commit-mode amend`
    (`aitask-explore`, `aitask-pr-import`, `aitask-contribution-review`) all
    amend a single-parent task-creation commit they just made.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_sync.sh:988` — `_rebase_advance` reads unresolved
    paths as `task_git diff --name-only --diff-filter=U 2>/dev/null || true`, so
    a failed probe yields an empty list, is taken as "no unresolved files", and
    the function proceeds to `rebase --skip`, which discards a commit. Same
    fail-open shape as this task's defect, at a destructive call site.
  - `.aitask-scripts/aitask_setup.sh:3591-3594` — the dirtiness probe suppresses
    `git ls-files --others/--modified` and `git diff --cached --name-only`
    failures with `|| true`, so an unreadable worktree reads as clean.
  Both are the mitigation task `sweep_failopen_git_probes` recorded under
  `## Risk` → `### Planned mitigations` (timing: after).
