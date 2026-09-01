---
Task: t1658_2_anchor_data_worktree_resolution_to_repo_root.md
Parent Task: aitasks/t1658_data_branch_metadata_push_strands_local_branch.md
Sibling Tasks: aitasks/t1658/t1658_3_manual_verification_data_branch_metadata_push.md
Archived Sibling Plans: aiplans/archived/p1658/p1658_1_converge_local_data_branch_after_offbranch_push.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-01 17:54
---

# t1658_2 — Anchor data-worktree resolution and the metadata entry scripts to the repo root

Covers parent **AC5**. The converge seam (AC1–AC4) belongs to t1658_1, which has
**landed** (commit `cb271b5a9`) — do not change `task_data_converge()` or
`verified_update_lib.sh` here beyond what the entry scripts' `cd` requires.

## Context

`_ait_detect_data_worktree()` (`.aitask-scripts/lib/task_utils.sh:35`) resolves
`.aitask-data` **relative to the caller's cwd** and falls back to legacy mode
`"."` when it is absent. The fallback is silent and, by design, indistinguishable
from a genuine legacy-mode project.

Re-reproduced on this repo at plan-verification time:

- from `website/` → `_AIT_DATA_WORKTREE=.`, and the seam operates on **`main`**
- from `.aitask-crews/crew-brainstorm-1017/` → operates on **`crew-brainstorm-1017`**

Both report success while the data branch is never reconciled. **None of the 15
scripts that perform data-branch git ops `cd` to the repo root** — re-derived at
verification time and still exactly: `aitask_archive`, `aitask_artifact`,
`aitask_attach`, `aitask_create`, `aitask_fold_mark`, `aitask_followup_backfill`,
`aitask_gate`, `aitask_gate_record`, `aitask_issue_import`, `aitask_lock`,
`aitask_pick_own`, `aitask_remote_drift_check`, `aitask_sync`, `aitask_update`,
`aitask_zip_old`. Task worktrees are safe (task-workflow Step 5 runs
`aitask_init_data.sh --link-worktree`); crew worktrees are **not** linked —
`.aitask-crews/crew-brainstorm-1017` carries neither `.aitask-data`, `aitasks/`
nor `ait`.

**The two metadata entry scripts have two independent cwd anchors, not one.**
Both must be fixed by the same `cd`:

1. `aitask_usage_update.sh` (`models_file_for_agent` at **:170**, the
   `[[ -f "$models_file" ]] || die` at **:254**) and
   `aitask_verified_update.sh` (**:183** / **:282**) resolve
   `aitasks/metadata/models_<agent>.json` relative to cwd, so from a
   subdirectory they die on "Model config not found".
2. `verified_update_lib.sh:54` invokes **`./ait git`** — also relative. From a
   subdirectory `./ait` does not exist, so `has_remote_tracking()` returns 1 and
   the script silently degrades to the **local-only** update path. This is a
   second, quieter failure mode that the die in (1) currently masks; fixing only
   the models-file path would expose it.

## Decision already taken — do not re-litigate

**Anchor detection *and* both entry scripts** (user-selected over "narrow guard
in the metadata seam only" and "detection only"). A silent fallback to legacy
mode from inside a branch-mode project must not remain possible for any of the
15 scripts, and the two metadata scripts must additionally work from any cwd.

## Verification-pass findings (2026-09-01)

Recorded because they change the work, not merely its description:

- **`tests/lib/test_scaffold.sh` already copies `data_symlinks.sh`** (landed with
  t1616), and **no** test that copies `task_utils.sh` skips
  `setup_fake_aitask_repo` — verified by sweeping all 68 copy sites. The
  source-on-startup ↔ test-scaffold rule is therefore already satisfied; the
  remaining scaffold work is a comment correction (see step 1).
- **The ladder can abort every caller under `set -e`.** Measured:
  `root="$(git rev-parse --show-toplevel 2>/dev/null)"` exits **128** and kills
  the enclosing script under `set -euo pipefail` when cwd is not a git
  repository. Every framework script sets `set -euo pipefail`. Every rung's
  command substitution must be explicitly guarded (step 2).
- **The ladder was prototyped read-only** and returns the intended answer for all
  six shapes: repo root → `.aitask-data`; `website/`, `tests/`, inside
  `.aitask-data`, and a crew worktree → `/home/ddt/Work/aitasks/.aitask-data`;
  `/tmp` → `.`.
- **The consumer audit is exact.** Every `_AIT_DATA_WORKTREE` use is `git -C` or
  a `"$_AIT_DATA_WORKTREE/<suffix>"` prefix; every equality test is against
  `"."`; **no site compares against the literal `.aitask-data`**.
- `lib/sync_action_runner.py:149` documents passing `cwd=<root>` so
  `_AIT_DATA_WORKTREE` resolution applies. The ladder makes that unnecessary for
  the `repo_root=None` (board) path — a strict improvement. **No change needed**;
  do not touch it.

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_data_worktree_seam]` **Before touching any resolution code**,
   add characterization tests that pin today's behaviour, so the change is a
   demonstrated flip rather than an untested green:
   - Pin `_ait_detect_data_worktree`'s current answer for every shape: repo root
     of a branch-mode project (`.aitask-data`), a subdirectory of one (today
     `"."` — the bug), inside `.aitask-data` itself (today `"."`), a linked
     worktree with no `.aitask-data` of its own (today `"."` — the crew case),
     and a genuine legacy project (`"."`, correct). Existing
     `tests/test_task_git.sh` Tests 1–3 already cover the root and legacy rungs;
     extend rather than duplicate them.
   - Assert every `$_AIT_DATA_WORKTREE` consumer resolves the **same physical
     location** when the value is absolute rather than `.aitask-data`:
     `artifact_manifest.sh:34`, `attachment_meta.sh:34`, `attachment_lock.sh:31`,
     `artifact_backends/local.sh:18`, `aitask_sync.sh:436`, plus
     `_ait_data_gitdir` (`task_utils.sh:50`), whose relative
     `.git/worktrees/-aitask-data` fast path must fall through to its
     `git -C … rev-parse --absolute-git-dir` branch off-root.
   - Record the **current failure** of the two non-root entry-point invocations
     in step 4 below (they die with "Model config not found" today), so their
     post-fix pass is a real flip.

2. `[guard_ladder_under_set_e]` Add the characterization case that the ladder's
   own failure mode needs — folded into the same pre-phase, in
   `tests/test_task_git.sh`:
   - Drive a **real subprocess** (not the already-sourced in-process function)
     that runs `set -euo pipefail`, sources `task_utils.sh`, calls
     `_ait_detect_data_worktree` from a **non-git-repo cwd**, and then echoes a
     sentinel. Assert the sentinel is printed, the exit status is `0`, and
     `_AIT_DATA_WORKTREE` is `"."`.
   - This is the discriminating control for the guard in step 2 of the
     implementation: with any rung's command substitution left unguarded the
     subprocess dies with status **128** and no sentinel, which the in-process
     tests cannot see (the file runs `set +euo pipefail` before its test bodies).

### 1. Test scaffold — correct the stale rationale (no new copy needed)

`tests/lib/test_scaffold.sh` already copies `data_symlinks.sh`; its comment
currently reads "Not in ./ait's own source chain". That becomes **false** the
moment `task_utils.sh` sources it. Update the comment in the same commit to name
`task_utils.sh` as a startup consumer — which is what makes the lib reach
essentially every scaffolded test — and drop the now-wrong sentence. Do **not**
add a second `cp`.

### 2. The resolution ladder in `.aitask-scripts/lib/task_utils.sh`

Replace `_ait_detect_data_worktree()`'s single cwd-relative probe with four rungs
(first hit wins; the result is still cached in `_AIT_DATA_WORKTREE`, and the
`[[ -n "$_AIT_DATA_WORKTREE" ]] && return` guard at the top is unchanged, so
tests that set the global directly — all of `tests/test_task_push.sh` — still
short-circuit detection):

1. `./.aitask-data/.git` (directory **or** file) → `.aitask-data`. Today's fast
   path — byte-identical behaviour when cwd is the repo root, which is every
   `./ait`-dispatched invocation. It stays a **pure filesystem probe**: Test 2 in
   `tests/test_task_git.sh` writes a `.git` file whose `gitdir:` target does not
   resolve, and must keep passing.
2. `<toplevel>/.aitask-data/.git`, where
   `toplevel="$(git rev-parse --show-toplevel 2>/dev/null)"` → that absolute
   path. Covers `website/`, `tests/`, any subdirectory, and a task worktree's own
   `.aitask-data` symlink.
3. `<main>/.aitask-data/.git`, where `main` comes from **the canonical
   `ait_main_worktree_root`** in `lib/data_symlinks.sh:96` (sets
   `AIT_WT_MAIN_ROOT`) → that absolute path. Covers a linked worktree that was
   never `--link-worktree`d — the crew-worktree case. **Reuse that helper; do
   not reimplement `--git-common-dir` handling** — it already deals with
   submodule gitdirs, `--separate-git-dir` refusal, and canonicalization, and it
   derives everything from its `<dir>` argument so no ambient cwd can select a
   different repository.
4. Otherwise `"."` — now reachable only from a genuinely legacy-mode project.

**Rung 3 has THREE states and must not conflate them (review finding, blocking).**
`ait_main_worktree_root` returns `0` resolved, `1` not a git repository, and `2`
*inside* a repository whose topology did not resolve — `git init
--separate-git-dir` is a documented layout that answers `2` (the KNOWN LAYOUT
BOUNDARY note in `data_symlinks.sh`). Treating `2` as "fall through to rung 4"
makes an unlinked linked worktree of such a **branch-mode** primary answer `"."`
and commit task data to its own code branch — reinstating this task's exact bug
in a different layout. Reproduced before the fix. So:

- `0` → probe `<main>/.aitask-data`, else fall to rung 4.
- `1` → rung 4; legacy is a proven answer.
- `2` → legacy is safe **only if this checkout provably owns its repository**.
  Ask `ait_linked_worktree_roots "."`: it decides on the
  `--git-dir != --git-common-dir` predicate, which still works when the main root
  does not resolve, and returns `1` for "definitively NOT linked". It **cannot**
  return `0` here (it calls `ait_main_worktree_root` itself and propagates the
  same failure), so `1` is the only safe state. Anything else → **`die`** with an
  actionable message, matching the framework's existing posture on state 2
  (`aitask_init_data.sh:118`).

**A blanket refusal on state `2` would be a regression, not a fix**: a *legacy*
`--separate-git-dir` project also answers `2` from a subdirectory, and `"."` is
correct there. That case is the negative control the refusal test must carry.

**Every rung's command substitution MUST be guarded.** This is not style: an
unguarded assignment aborts the caller with status 128 and no message from any
non-repo cwd (measured — see the verification-pass findings). `ait_main_worktree_root`
returns 1 (not a repository) and 2 (indeterminate), so it must be called in an
`if`, never bare:

```bash
_ait_detect_data_worktree() {
    if [[ -n "$_AIT_DATA_WORKTREE" ]]; then return; fi
    local root=""
    # Rung 1: today's fast path — a pure filesystem probe, byte-identical at the
    # repo root, which is every ./ait-dispatched invocation.
    if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
        _AIT_DATA_WORKTREE=".aitask-data"
        return
    fi
    # Rung 2: this checkout's toplevel. `|| root=""` is load-bearing — a bare
    # assignment exits 128 under `set -euo pipefail` outside a repository and
    # kills the caller with no message.
    root="$(git rev-parse --show-toplevel 2>/dev/null)" || root=""
    if [[ -n "$root" && ( -d "$root/.aitask-data/.git" || -f "$root/.aitask-data/.git" ) ]]; then
        _AIT_DATA_WORKTREE="$root/.aitask-data"
        return
    fi
    # Rung 3: the MAIN worktree, for a linked worktree that was never
    # --link-worktree'd (the crew case). ait_main_worktree_root returns 1/2 for
    # "not a repo" / "indeterminate", so it must be called in an `if`.
    if ait_main_worktree_root "."; then
        if [[ -d "$AIT_WT_MAIN_ROOT/.aitask-data/.git" || -f "$AIT_WT_MAIN_ROOT/.aitask-data/.git" ]]; then
            _AIT_DATA_WORKTREE="$AIT_WT_MAIN_ROOT/.aitask-data"
            return
        fi
    fi
    # Rung 4: a genuine legacy-mode project.
    _AIT_DATA_WORKTREE="."
}
```

Use the **uncanonicalized** `<root>/.aitask-data` spelling (not `pwd -P`), so a
task worktree's symlinked data dir keeps its friendly path in messages; git
follows the symlink either way.

**Deliberate boundary:** a submodule (or any nested repository) resolves to its
own root and therefore to legacy mode, never to the parent repo's data branch.
That is `ait_main_worktree_root`'s documented same-repo property and is the
correct answer — record it in a comment so a later reader does not "fix" it. A
comment is the *only* thing holding that boundary in this task: no test exercises
a nested repository today, so a later change to rung 2 or rung 3 could silently
make a nested checkout operate on its parent's data branch. A spawned "after"
follow-up closes that gap — see `nested_repo_boundary_regression` under
**Planned mitigations**.

`task_utils.sh` gains, alongside its existing sources (after
`terminal_compat.sh`, matching the established `${SCRIPT_DIR}/lib/…` spelling at
lines 11–18):

```bash
# shellcheck source=data_symlinks.sh
source "${SCRIPT_DIR}/lib/data_symlinks.sh"
```

`data_symlinks.sh` sources only `terminal_compat.sh` — self-anchored via its own
`BASH_SOURCE`, so no cwd dependency — and guards against double-sourcing, so
there is no cycle and no ordering constraint against `aitask_setup.sh` /
`aitask_init_data.sh`, which already source it.

### 3. Consumer safety — why an absolute value is safe

Re-verified at plan-verification time by `grep -rn '_AIT_DATA_WORKTREE'
.aitask-scripts/`: every consumer is either `git -C "$_AIT_DATA_WORKTREE" …`
(`task_utils.sh:65,76,198`) or a `"$_AIT_DATA_WORKTREE/<suffix>"` path prefix
(`artifact_manifest.sh:34`, `attachment_meta.sh:34`, `attachment_lock.sh:31`,
`artifact_backends/local.sh:18`, `aitask_sync.sh:92-93,435-436`) — both correct
with an absolute value. The only equality tests are against `"."`
(`aitask_remote_drift_check.sh:131`, `aitask_sync.sh:92,435`,
`task_utils.sh:52,75,154,197`), and legacy still yields exactly `"."`. **No site
compares against the literal `.aitask-data`.** Re-run that grep during
implementation and fail loudly if a new comparison has appeared.

### 4. `ait_cd_repo_root` and the entry scripts

Add to `task_utils.sh`, immediately beside the ladder. **Reuse the framework's
existing spelling** — `aitask_skillrun.sh:26,35` and `aitask_run_gates.sh:21`
already do `REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"` — rather than a `dirname`
form, so the repo root is canonicalized the same way everywhere:

```bash
# Anchor the process to the repository root — the same rule `ait` applies
# (`cd "$AIT_DIR"`, ait:9) so relative paths like aitasks/metadata/... and ./ait
# resolve. Call it ONCE, early, from an ENTRY-POINT script only; never from a
# library, and never from a sourced helper.
ait_cd_repo_root() {
    local script_dir="${1:?ait_cd_repo_root: script dir required}" root
    root="$(cd "$script_dir/.." && pwd)" || die "Cannot resolve repo root from $script_dir"
    cd "$root" || die "Cannot cd to repo root $root"
}
```

It deliberately does **not** honour `AITASK_REPO_ROOT`: that env var is a
single-script test hook read only by `aitask_add_model.sh:23` (and set only by
`tests/test_add_model.sh`), and promoting it to a framework-wide override here
would silently broaden its blast radius.

Call it once at the top of both `aitask_usage_update.sh` and
`aitask_verified_update.sh`, after `SCRIPT_DIR` is computed and after the libs
are sourced — i.e. immediately after the `verified_update_lib.sh` source at
line 10 in each, at file scope, **not** inside `main()`:

```bash
ait_cd_repo_root "$SCRIPT_DIR"
```

This fixes **both** anchors from the Context: the relative
`aitasks/metadata/models_<agent>.json` and the relative `./ait` in
`verified_update_lib.sh`. No-op in every existing test — they already `cd` to the
fixture root, whose `.aitask-scripts` is the one they invoke.

### 5. Tests

`tests/test_task_git.sh` (already sources `aitask_setup.sh --source-only` for
`setup_data_branch`, which builds a real `.aitask-data` worktree — see its
Test 5) — the resolution rungs:

- from `<root>/website/` in a branch-mode project → resolves to the data
  worktree, not `"."` (rung 2);
- from a linked worktree created **without** `--link-worktree` → resolves to the
  main checkout's data worktree (rung 3);
- from inside `.aitask-data` itself → resolves to that same physical directory
  (rung 3), not `"."`;
- legacy project from a subdirectory → still `"."` (rung 4);
- the `set -e` subprocess control from pre-phase step 2;
- existing Tests 1–3, 5, 10 (caching) and 12 (linked worktree *with* the
  symlink, which stays on rung 1) pass unchanged.

**The consumer-agreement assertions must exercise the REAL consumers (review
finding, blocking).** Comparing two values produced by the identical command is
tautological and cannot catch a relative-vs-absolute bug. Source the named
consumer functions from the repo under test — `artifact_manifest_dir`,
`attach_meta_dir`, `attachment_lock_dir`, `_artifact_local_root` — and compare
the **canonical** directory each resolves to for (relative value, repo root)
against (absolute value, subdirectory); `mkdir -p` + `cd && pwd -P` makes the
comparison physical rather than textual. Carry a **negative control**: the
relative value used from a subdirectory must NOT agree, or the assertion cannot
fail. `aitask_sync.sh`'s two sites are a stated gap — it calls `main()` at
import, so it cannot be sourced; do not claim them as covered.

**The no-silent-fallback contract needs its own test.** Build a
`--separate-git-dir` **branch-mode** primary plus an unlinked linked worktree,
drive detection as a real subprocess (the refusal is a `die`), and assert it
emits no answer and exits non-zero. Two negative controls in the same test: a
*legacy* `--separate-git-dir` project still answers `"."` and exits 0 (the
refusal is not blanket), and the branch-mode root still answers `.aitask-data`
(rung 1 untouched).

**Real entry points from a non-root cwd.** The resolution tests alone cannot see
a missing, misplaced, or later-regressed `ait_cd_repo_root` — that is exactly the
gap this bullet closes. Build on **t1658_1's shared fixture**
`tests/lib/metadata_update_fixture.sh` :: `setup_branch_mode_metadata_repo`
(do not fork a second branch-mode fixture), following the shape of
`tests/test_verified_update.sh` **Test 30**, which already drives the real script
in branch mode and carries discriminating assertions. Add to **both**
`tests/test_usage_update.sh` (new tests start at 17; the file does not use the
branch-mode fixture yet) and `tests/test_verified_update.sh` (new tests start at
32) — each script has its own `main()` and its own `cd` call site, so both must
be driven:

**Each cwd gets its OWN fresh fixture — do not share one across the two
invocations.** `setup_branch_mode_metadata_repo`'s seed carries no `usagestats`
key and `verified.pick = 80`, so a second run against the same fixture shifts
every discriminating value at once: `aitask_usage_update.sh` returns
`UPDATED:…:pick:2` instead of `:1`, `verifiedstats.pick.all_time.runs` becomes
`2`, and `git rev-list --count HEAD` becomes `3`. Meanwhile
`aitask_verified_update.sh`'s stdout value is the **rolling average**, which
stays `80` on both runs — so stdout alone cannot tell the two invocations apart
and a reused fixture would leave the `/tmp` pass asserted against stale numbers
or silently non-discriminating. A fresh fixture per cwd keeps both invocations
independently discriminating with **identical** expected values, isolates the one
variable under test (the caller's cwd), and matches this file's existing
convention — every test in both files already takes its own fixture and
`rm -rf`s it.

So, twice per script — once with the script launched from `"$WORK/website"`
(`mkdir -p` it in the fixture), once from an unrelated cwd (`/tmp`) via an
absolute path — each against its own `setup_branch_mode_metadata_repo`:

- assert stdout is exactly `UPDATED:claudecode/opus4_6:pick:1` for
  `aitask_usage_update.sh` and `UPDATED:claudecode/opus4_6:pick:80` for
  `aitask_verified_update.sh --score 4`, and that the exit status is `0` — not
  the `Model config not found` die (exit 1, empty stdout, which is today's answer
  and the recorded pre-fix control), and not `UPDATED_REMOTE_ONLY:` / exit 3;
- assert local-ref convergence in the data worktree: the pushed commit is an
  ancestor of local `HEAD`, and `git rev-list --count HEAD..@{u}` is `0`;
- keep Test 30's **discriminating** assertions so a fixture that silently
  degraded to legacy mode cannot pass vacuously: the data branch must have gained
  exactly one commit (`git rev-list --count HEAD` == `2`), and the metadata must
  land on the data branch — `verifiedstats.pick.all_time.runs` == `1`, from a
  seed that has no such key. Both numbers are correct **only** on a fresh
  fixture, which is the second reason for the isolation above.

The fixture's `ait` shim is itself cwd-relative (`git -C ".aitask-data"`,
`metadata_update_fixture.sh:52`), which is what makes these tests
discriminating: without `ait_cd_repo_root` the shim cannot find the data
worktree from a subdirectory.

If any new test body runs inside a `( … )` subshell, opt into the file-backed
counters (`assert_counters_init` / `assert_counters_load`) per CLAUDE.md. The
existing bodies in all three files run at top level and must stay that way.

### Post-phase (risk mitigations)

None for this child.

## Verification

```bash
bash tests/test_task_git.sh
bash tests/test_usage_update.sh
bash tests/test_verified_update.sh
bash tests/test_remote_drift_check.sh   # shares _ait_detect_data_worktree
bash tests/test_init_data.sh            # shares data_symlinks.sh
bash tests/test_task_push.sh            # shares task_utils.sh
bash tests/test_artifact_cli.sh         # legacy-mode fixture, asserts "."
bash tests/test_artifact_manifest_lib.sh
bash tests/test_attach_local_backend.sh
bash tests/run_all_python_tests.sh
shellcheck .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/aitask_verified_update.sh
```

Baseline for shellcheck is clean apart from pre-existing `SC1091` info notes on
the `source` lines; the new `source` adds one more and must carry the same
`# shellcheck source=` directive as its neighbours.

Read only the last line of a test file's output for its verdict; for the Python
suite read the final `PYTHON SUITE: PASSED|FAILED` banner, and remember that
piping discards the exit status — use `set -o pipefail` or check
`${PIPESTATUS[0]}`.

Live check on this repo, **read-only first** (the entry scripts push a metadata
commit, so run the mutating check only once, deliberately):

```bash
# read-only: the ladder itself
cd website && bash -c 'source ../.aitask-scripts/lib/task_utils.sh
  _ait_detect_data_worktree; echo "$_AIT_DATA_WORKTREE"'
# expect the absolute <root>/.aitask-data, not "."
```

then the real entry point:

```bash
cd website && ../.aitask-scripts/aitask_usage_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --silent
```

and confirm it prints `UPDATED:` and exits `0` — today it dies with "Model
config not found". Then from the repo root confirm
`./ait git rev-list --count HEAD..@{u}` is `0`.

Step 9 (Post-Implementation) covers cleanup, archival and merge.

## Out of scope

The converge seam itself (parent AC1–AC4) belongs to **t1658_1**, now landed. Do
not change `task_data_converge()` or `verified_update_lib.sh` here beyond the
entry scripts' `cd`. Do not touch `lib/sync_action_runner.py`.

## Risk

### Code-health risk: medium
- `_ait_detect_data_worktree()` is sourced by essentially every framework script and 15 of them perform data-branch git ops; rungs 2/3 return an **absolute** path where today's value is the relative `.aitask-data`, so a consumer assuming the relative spelling could silently target a different branch. The verification pass re-ran the audit and found **no** such consumer today (every use is `git -C` or a path prefix; every comparison is against `"."`), which bounds but does not eliminate the risk for future call sites · severity: medium · → mitigation: inline pre-phase characterize_data_worktree_seam
- The ladder adds command substitutions inside a function that every framework script calls under `set -euo pipefail`. An unguarded `root="$(git rev-parse …)"` exits **128 and kills the caller with no message** from any non-repo cwd — measured, not hypothesised. The failure is invisible to the existing in-process tests, which run after `set +euo pipefail` · severity: medium · → mitigation: inline pre-phase guard_ladder_under_set_e
- `aitask_usage_update.sh` / `aitask_verified_update.sh` gain a `cd`, changing their cwd contract for any caller relying on cwd-relative resolution. The known call sites are the `satisfaction-feedback.md` renders, which invoke them as `./.aitask-scripts/…` from the repo root — a no-op under the new anchoring · severity: low · → mitigation: inline pre-phase characterize_data_worktree_seam
- The nested-repository boundary (a submodule or any nested checkout must resolve to its **own** legacy mode, never the parent's data worktree) is preserved by a source comment alone — no test exercises a nested repository today. A later change to rung 2 or rung 3 could therefore make a nested checkout silently operate on its parent's data branch, which is the same silent-wrong-target class this task exists to remove · severity: medium · → mitigation: spawned after-task t1674 (nested_repo_boundary_regression)

- Rung 3's helper has three states, and treating the *indeterminate* one (`2`, which `git init --separate-git-dir` produces) as "fall through to legacy" silently reinstates the bug for an unlinked worktree of such a branch-mode primary. Found in review, reproduced, and closed by the refusal above plus Test 14 · severity: medium · → mitigation: the state-2 refusal and its two negative controls (§2, §5)

### Goal-achievement risk: low
- The ladder's four rungs are each directly testable and were prototyped read-only against all six shapes before implementation; the entry-point tests drive the real scripts from a non-root cwd rather than the resolution function alone, so a missing `ait_cd_repo_root` cannot pass silently.

### Planned mitigations
- timing: pre-phase | name: characterize_data_worktree_seam | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: the absolute-path consumer risk and the entry-script cwd-contract risk | desc: before touching the resolution, pin today's `_ait_detect_data_worktree` answer for every shape (repo root, subdirectory, inside `.aitask-data`, linked worktree, legacy), assert every `$_AIT_DATA_WORKTREE` consumer plus `_ait_data_gitdir` still resolves the same physical location under an absolute value, and record the current failure of the two non-root entry-point invocations so the fix is a demonstrated flip
- timing: pre-phase | name: guard_ladder_under_set_e | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: the `set -e` abort risk | desc: add a real-subprocess characterization that runs `set -euo pipefail`, sources `task_utils.sh`, calls `_ait_detect_data_worktree` from a non-git-repo cwd and echoes a sentinel — asserting sentinel present, exit 0 and `"."`; it is the only control that can see an unguarded rung, since the in-process tests run after `set +euo pipefail`
- timing: after | name: nested_repo_boundary_regression | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | disposition: spawn | created: t1674 | addresses: the nested-repository boundary risk | desc: add a nested-repository/submodule-shaped regression case to `tests/test_task_git.sh` — a branch-mode parent whose `.aitask-data` exists, containing an inner checkout that is its own repository with no `.aitask-data` — asserting `_ait_detect_data_worktree` answers `"."` from inside the inner repo and that no parent lookup occurs (the resolved value must not name the parent's data worktree). Spawned rather than inlined because building a genuine nested/submodule fixture is a separable medium-effort piece of test infrastructure, while the boundary itself is already correct by construction in this change

## Final Implementation Notes

- **Actual work done:** Replaced `_ait_detect_data_worktree()`'s single
  cwd-relative probe with the four-rung ladder in
  `.aitask-scripts/lib/task_utils.sh`, added `ait_cd_repo_root()` beside it, and
  called it once at file scope in `aitask_usage_update.sh` and
  `aitask_verified_update.sh`. `task_utils.sh` now sources `data_symlinks.sh`
  for `ait_main_worktree_root`. Tests: `test_task_git.sh` Test 13 (five cwd
  shapes, the `set -e` subprocess control, real-consumer agreement) and Test 14
  (the no-silent-fallback refusal contract); `test_usage_update.sh` Test 17 and
  `test_verified_update.sh` Test 32 (the real entry points from `website/` and
  `/tmp`, one fresh fixture per cwd).

- **Deviations from plan:**
  - The plan's "copy `data_symlinks.sh` in `tests/lib/test_scaffold.sh`" step was
    already done (it landed with t1616), and no shell test copies
    `task_utils.sh` without `setup_fake_aitask_repo` — verified across all 68
    copy sites. The step became a comment correction: the old rationale claimed
    the lib was "Not in ./ait's own source chain", which this change falsifies.
  - `ait_cd_repo_root` uses the framework's established
    `root="$(cd "$script_dir/.." && pwd)"` spelling (as `aitask_skillrun.sh:26`
    and `aitask_run_gates.sh:21` do) rather than the plan's `dirname` form, so
    the repo root is canonicalized the same way everywhere. It deliberately does
    not honour `AITASK_REPO_ROOT` — a single-script test hook in
    `aitask_add_model.sh` only.
  - The live acceptance check was run with `--agent-string claudecode/opus5`
    rather than the plan's literal `claudecode/opus4_6`: that invocation writes a
    real usage statistic, and recording a run against a model that did not run it
    would be a false stat. Result: `UPDATED:claudecode/opus5:pick:18`, exit 0,
    `./ait git rev-list --count HEAD..@{u}` = 0.

- **Issues encountered:**
  - **A regression the shell sweep missed.** `tests/test_desync_state.py` keeps
    its own hand-maintained lib list rather than using
    `tests/lib/test_scaffold.sh`, so the new `data_symlinks.sh` startup
    dependency broke it at source time. The initial sweep covered only *shell*
    fixtures; the Python suite caught it. Fixed by extending that list and
    recording why it must be extended by hand. No install-flow change was needed
    — `install.sh` / `aitask_setup.sh` ship the whole `.aitask-scripts/` tree.
  - **Review finding (blocking): rung 3 conflated three helper states.**
    `ait_main_worktree_root` returns `2` for an indeterminate topology, which
    `git init --separate-git-dir` produces. The first implementation fell through
    to `"."`, so an unlinked linked worktree of such a *branch-mode* primary
    silently operated on its own code branch — this task's own bug in a different
    layout. Reproduced, then fixed by distinguishing `1` (not a repository →
    legacy is proven) from `2` (refuse unless `ait_linked_worktree_roots` proves
    the checkout owns its repository). A blanket refusal on `2` was rejected: a
    *legacy* `--separate-git-dir` project answers `2` too and `"."` is correct
    there.
  - **Review finding (blocking): a tautological assertion.** Test 13g compared
    two values computed by the identical command and exercised none of the named
    path-prefix consumers. Rewritten to source and drive the four real consumer
    functions and compare canonical directories, with a negative control proving
    the comparison is prefix-sensitive.
  - **Concurrent session.** `.aitask-scripts/lib/task_utils.sh` carried another
    session's uncommitted t1599_3 work (a `--no-stage` flag on
    `task_git_commit_scoped`) throughout. The hunks are disjoint — mine at old
    lines 18–41, theirs at 206–227 — so only my hunks were staged; theirs were
    left in the working tree untouched.

- **Key decisions:**
  - Rung 1 stays a pure filesystem probe, byte-identical at the repo root, so
    every `./ait`-dispatched invocation is unchanged.
  - Rungs 2/3 return an **uncanonicalized** `<root>/.aitask-data`, so a task
    worktree's symlinked data dir keeps a readable path in messages.
  - Every rung's command substitution is explicitly guarded. Measured: an
    unguarded `root="$(git rev-parse --show-toplevel 2>/dev/null)"` exits 128 and
    kills the caller with no message from any non-repo cwd, and the in-process
    tests cannot see it (the file runs `set +euo pipefail`), which is why the
    control is a real subprocess.
  - A nested repository or submodule resolves to its own root and therefore to
    legacy mode, never the parent's data branch —
    `ait_main_worktree_root`'s same-repo property. Held by a comment here; the
    spawned `nested_repo_boundary_regression` follow-up adds the test.

- **Upstream defects identified:** None

- **Notes for sibling tasks:**
  - `tests/lib/test_scaffold.sh` is *not* the only place a startup dependency has
    to be registered: `tests/test_desync_state.py` carries a parallel,
    hand-maintained list. Any future addition to `task_utils.sh`'s source chain
    must update both, and a shell-only sweep will miss the second.
  - `ait_main_worktree_root` / `ait_linked_worktree_roots` are three-state
    helpers. `1` and `2` mean different things and a caller that treats "non-zero"
    as one outcome will fail open on the `--separate-git-dir` layout.
  - `setup_branch_mode_metadata_repo` (from t1658_1) is the fixture for anything
    that must run in real branch mode; give each mutating invocation its own
    instance, since the seed's counters and commit count are what discriminate.
  - t1658_3 (manual verification) can rely on: `website/` and an unlinked crew
    worktree both resolving `aitask-data`, and `aitask_usage_update.sh` /
    `aitask_verified_update.sh` succeeding from any cwd.
