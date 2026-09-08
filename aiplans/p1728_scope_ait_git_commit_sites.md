---
Task: t1728_scope_ait_git_commit_sites.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1728 — Scope the `./ait git commit` sites

## Context

`t1599_4` converted every unscoped `task_git commit` in `.aitask-scripts/` to the
path-scoped `task_git_commit_scoped` seam and added
`tests/test_no_unscoped_task_commit.sh` to keep them that way. That guard scans
**one** seam and says so in its header: `./ait git commit` is explicitly declared
out of detection scope.

`./ait git <args>` is literally `task_git <args>` in a subprocess (`ait:333-346`
sources `lib/task_utils.sh` and dispatches to `task_git`), so it carries the
identical hazard: a `commit` with no `--` pathspec commits the **entire index**.
On the shared `.aitask-data` branch, whatever a concurrent session has staged at
that instant lands in a commit whose message names unrelated work.

**Re-derived the sites (line numbers had not drifted, but the count had).** The
task names two; a sweep of `.aitask-scripts/**/*.sh` finds **three** real command
sites with the latent shape (narrow `add`, index-wide `commit`):

| # | site | staged path |
|---|---|---|
| 1 | `.aitask-scripts/aitask_verification_followup.sh:250-251` | `$origin_plan` |
| 2 | `.aitask-scripts/lib/verified_update_lib.sh:122-128` | `$models_file` |
| 3 | `.aitask-scripts/aitask_create_manual_verification.sh:176-177` | `$new_path` (**not named by the task**) |

The other five `ait git commit` occurrences in `.aitask-scripts/` are **prose**
inside message strings (`aitask_note.sh:695`, `:1068`, `aitask_sync.sh:650`,
`aitask_setup.sh:3948`, `lib/txn_snapshot.sh:114`) — recovery hints, already
written path-scoped. `lib/verified_update_lib.sh:168` commits inside a private
temp clone (`git -C "$clone_dir"`), which owns its own index — no hazard.

**Finding on "does the `./ait git` route need its own equivalent?" — No.**
Because `./ait git` *is* `task_git`, the existing seams in `lib/task_utils.sh`
are the equivalent, and they are reachable from all three sites: sites 1 and 2
already source `task_utils.sh` (site 2's two callers, `aitask_verified_update.sh`
/ `aitask_usage_update.sh`, source it before the lib); site 3 sources only
`terminal_compat.sh` and needs one added `source` line whose whole dependency
chain the test scaffold already copies. No new `ait_git_commit_scoped` helper,
and no per-site reimplementation.

**Which seam: `ait_commit_paths_staging_untracked`, not bare
`task_git_commit_scoped`.** The latter's default mode runs
`task_git add -- "$@"` unconditionally, and its own header records why that is
wrong for a shared branch: *"an unconditional `add` of a TRACKED path can replace
an index entry another session staged and has not yet committed (t1599_3)."*
Fixing the pathspec while introducing that write would trade one shared-index
hazard for another, and the foreign-*file* controls this task calls for cannot
see it — they prove `commit -o` ignores unrelated entries, not that the target
path's own staged version survives. `ait_commit_paths_staging_untracked`
(`lib/task_utils.sh:481`, the t1702 seam) stages **only** paths git does not
track yet, records them in `AIT_STAGED_BY_US`, unstages exactly those on any
failure, and delegates to `task_git_commit_scoped --no-stage` — so the pathspec
fix is still what lands.

`--no-stage` alone is not a substitute here: it is only correct when trackedness
is *proven*, and `commit -o -- <untracked>` fails outright with "pathspec did not
match any file(s) known to git". At sites 1 and 3 that failure would be swallowed
by their best-effort `|| true` and the commit would simply vanish. The t1702 seam
handles both cases, so it is used at all three.

## Implementation

### Pre-phase (risk mitigations)

1. `[red_control_proof]` Before touching any of the three sites, write both
   control families (A — foreign staged file; B — the target's own staged
   version; see Verification) and run each against the **unmodified** source.
   Record the observed failure for each: for A the foreign file appearing inside
   the commit, for B the target's staged content having become `B`. A control
   that is already green here does not discriminate and must be rewritten before
   the fix lands — site 1's commit has never executed in its fixture, so that is
   the specific way its control could be vacuous.

### 0. Shared shape at every call site

Two bash rules apply to all three conversions and are easy to get wrong:

- **Absorb the status, never `&&`.** These files run under `set -euo pipefail`.
  A bare call returning 2 ("verified nothing to commit" — a normal outcome)
  aborts the script *after* the file was already written. Capture with
  `|| crc=$?` against a pre-declared `local crc=0`. Equally, a trailing
  `(( crc == 1 )) && warn …` is a **complete `&&` list**: when the test is false
  the list's status is 1 and `set -e` fires. Every such branch is written as a
  real `if … fi`.
- **Arm the unstage trap, composing with any trap already there.** The seam's
  cleanup trap is armed by the caller, deliberately (see the comment at
  `aitask_task_commit.sh:142-152`), so the library cannot clobber a caller's own
  EXIT handler. Sites 1 and 3 *already* have one (`trap 'rm -f "${tmp:-}"' EXIT`
  at `aitask_verification_followup.sh:95`, `aitask_create_manual_verification.sh:91`),
  so a naive `trap 'ait_unstage_staged_by_us' EXIT` would silently drop their
  temp-file cleanup. Compose instead — a single named cleanup function per
  script that does both.

### 1. `.aitask-scripts/aitask_verification_followup.sh` (~line 250)

Replace the `./ait git add` / `./ait git commit` pair with the seam. The block is
deliberately best-effort today (`2>/dev/null || true` on both lines — the
back-reference is a nice-to-have on an archived plan), and that stays true, but
1 and 2 are no longer conflated:

```bash
local crc=0
ait_commit_paths_staging_untracked \
    "ait: Back-reference manual-verification failure on t${origin}" \
    "$origin_plan" || crc=$?
# 0 = committed, 2 = verified nothing to commit, 1 = failed.
if (( crc == 1 )); then
    warn "back-reference appended to $origin_plan but not committed"
fi
```

Extend the existing EXIT trap to `trap 'followup_cleanup' EXIT` with
`followup_cleanup() { ait_unstage_staged_by_us; rm -f "${tmp:-}"; }`.

Note `stdout` here is a **data channel** (`FOLLOWUP_CREATED:…`); the seam already
routes git's stdout to `/dev/null`, and `warn` goes to stderr.

### 2. `.aitask-scripts/lib/verified_update_lib.sh` — `commit_metadata_update_local` (~line 115)

Replace the `add` + `diff --cached --quiet` early-return + bare `commit` with a
single scoped call. The seam's `git status --porcelain -- <path>` check subsumes
the early return (`return 2` = verified nothing to commit), so the out-param
contract pinned by Test 29 is preserved: `AIT_METADATA_VALUE` is never touched
on either existing return, and both still report converged.

**A commit failure must NOT be absorbed.** Today the bare `commit` is the
function's last command, so its non-zero status propagates and `set -e` aborts
the caller (`aitask_verified_update.sh:314` and `aitask_usage_update.sh:286` call
it as bare statements). Returning 0 with `AIT_METADATA_LOCAL_CONVERGED=1` would
make `aitask_verified_update.sh:317-327` take the success branch and print
`UPDATED:<agent>:<skill>:<value>` for a score that is on no branch at all — the
false-save the whole convergence out-param exists to prevent. Only rc 2 is
absorbed:

```bash
AIT_METADATA_LOCAL_CONVERGED=1

local crc=0
ait_commit_paths_staging_untracked \
    "${_AIT_COMMIT_PREFIX} for ${agent_string} ${skill_name}" \
    "$models_file" || crc=$?

# 2 = verified nothing to commit: the local branch already carries what the
# caller wanted, so convergence holds. This is the old `diff --cached --quiet`
# early return, and it is the ONLY status absorbed.
if (( crc == 2 )); then
    return 0
fi

# Anything else is a real failure. Propagate it, exactly as the pre-t1728 bare
# `commit` did, and retract the verdict first so no caller in a condition
# context can read a convergence claim for an update that was never committed.
if (( crc != 0 )); then
    AIT_METADATA_LOCAL_CONVERGED=0
    return "$crc"
fi

return 0
```

`run_git_quiet` is dropped at this call site: the seam is already quiet on stdout
and passes `--quiet` to git, so `SILENT` no longer needs a wrapper here.

Two accompanying edits in the same file:

- Widen the domain comment at line 27 — `AIT_METADATA_LOCAL_CONVERGED` currently
  reads `# 1 = local branch has the commit, 0 = origin only`; `0` must now also
  cover "the local commit failed", or the field is untrue on the new path.
- Add the trap to the file's documented **caller obligations** preamble
  (lines 3-6, which already list "must source terminal_compat.sh and
  task_utils.sh first" and the required globals): callers must arm
  `trap 'ait_unstage_staged_by_us' EXIT`. Arm it in `aitask_verified_update.sh`
  and `aitask_usage_update.sh` `main()` before the `has_remote_tracking` branch —
  neither has an EXIT trap today, so nothing to compose with.

### 3. `.aitask-scripts/aitask_create_manual_verification.sh` (~line 176)

Add `source "$SCRIPT_DIR/lib/task_utils.sh"` next to the existing
`terminal_compat.sh` source (idempotent — `task_utils.sh` is double-source
guarded and sources `terminal_compat.sh` itself; its top level is pure
definitions plus `${VAR:-default}` assignments, and the scaffold already copies
every lib it pulls in), then use the same absorbed seam call for the post-seed
commit, preserving its best-effort semantics, and compose the EXIT trap with the
existing `rm -f "${tmp_desc:-}"` one.

### 4. `tests/test_no_unscoped_task_commit.sh` — extend the guard

**Decision: extend it**, with a stated boundary. Evidence from running the
candidate scanner over the real tree: matching the pattern
`(\./)?ait[[:space:]]+git[[:space:]]+commit` against the **quote-stripped** text
(the same `bare` string `is_scoped` already builds) yields exactly the three
command sites and drops three of the five prose sites, because those sit inside a
balanced quoted span on one logical line.

The two remaining false positives are `aitask_note.sh:695` and `:1068` —
continuation *physical* lines of multi-line `warn` strings. Only `\`-continuations
are reassembled, so those lines carry unbalanced quoting and the scanner's
**fail-closed** rule reports them. Relaxing fail-closed is not an option (the
existing `aitask_unbalanced_quote.sh` control proves a real unscoped command can
hide behind a multi-line message), so:

- add a **second, separate** allowlist (`AIT_GIT_ALLOWLIST`) that applies **only**
  to the new pattern, holding `.aitask-scripts/aitask_note.sh` with the reason:
  its two matches are recovery-hint prose, it has no `./ait git commit` command
  site, and its real task-data commits go through `task_git` — which the primary
  pattern still guards there in full;
- rewrite the header's "OUT OF DETECTION SCOPE: `./ait git commit`" paragraph to
  state the seam is now scanned, that matching happens on the quote-stripped text
  so string-embedded hints are ignored, and that the one allowlisted file is a
  known hole for this pattern only.

Add fixture negative controls in the existing style (rogue unscoped `./ait git
commit`; one carrying `-- "$file"`; a hint inside a balanced string that must
**not** be flagged) and update the pinned violation count.

### 5. `aidocs/framework/shell_conventions.md`

Update the "Committing task-data paths" bullet: its closing sentence currently
says the guard does **not** scan `./ait git commit`. Replace with the new scope
plus the allowlist boundary, and state that `./ait git` is `task_git` in a
subprocess — so the same two seams serve both routes, and the bullet's existing
"pass `--no-stage` when the call site has already staged deliberately" guidance
gains its third case: reach for `ait_commit_paths_staging_untracked` when the
target may be tracked and another session may have it staged, which is the
default situation on the shared branch.

### Post-phase (risk mitigations)

1. `[set_e_abort_control]` Add a control per converted site that drives it under
   `set -euo pipefail` with **nothing to commit** (the rc-2 path), asserting the
   site exits 0 *and* that the statement following the seam call still executes —
   an observable side effect after the call, not merely the exit status. This
   pins the absorb (`|| crc=$?`), which the pathspec controls do not exercise:
   without it, an unabsorbed `return 2` aborts silently on the metadata hot path.
   For site 2 this is the existing Test 29(a) shape extended with an
   after-the-call witness. Cover the two neighbouring hazards in the same
   control, since they share the fixture: (a) the rc-1 path must **not** be
   absorbed at site 2 — non-zero return, `AIT_METADATA_LOCAL_CONVERGED=0`, no
   `UPDATED:` line; (b) at sites 1 and 3, assert the pre-existing temp file is
   still removed after the run, so a composed EXIT trap that dropped the original
   `rm -f` is caught.

## Verification

**Control A — foreign staged file (the pathspec).** Per site: seed a foreign
staged file, run the site, assert it is *absent from the resulting commit* and
*still staged afterwards*.

**Control B — the target path's own staged version (the staging write).** Per
site, because Control A cannot see this: stage content `A` for the target path,
then set its worktree content to `B`, then force the commit to fail via a
`pre-commit` hook that exits 1 (a documented git seam), then assert `git show :T`
is still `A`. With the default-staging helper the `add` writes `B` into the
shared index before the doomed commit and `A` is gone; with
`ait_commit_paths_staging_untracked` a tracked target is never staged, so `A`
survives. **This control's discriminating power must be established, not
assumed:** run it against both variants — it must be red with default staging and
green with the t1702 seam. If git's `--only` failure path turns out to restore
the real index anyway, the control is non-discriminating for the tracked case and
must be replaced (e.g. by asserting through a `task_git` shim) rather than kept
as a green no-op.

Both controls are run against the unmodified source before the fix lands
(`[red_control_proof]`), to confirm they are red rather than vacuously green.

- `tests/test_verification_followup.sh` — add an `./ait` pass-through stub to
  `setup_project()` (the fixture has none today, so the back-reference commit
  currently no-ops and the code path is completely uncovered), then add the
  control.
- `tests/test_create_manual_verification.sh` — fixture already stubs `./ait`;
  add the control.
- `tests/test_verified_update.sh` — add the controls alongside Test 29, which
  already sources `task_utils.sh` + `verified_update_lib.sh` directly and drives
  `commit_metadata_update_local` at helper level. Add one more there:
  **a failing commit must not report success** — force the failure with the same
  `pre-commit` hook and assert the helper returns non-zero *and* leaves
  `AIT_METADATA_LOCAL_CONVERGED` at `0`, plus an end-to-end assertion that
  `aitask_verified_update.sh` does not print `UPDATED:` in that case. Test 29's
  existing `early_converged=1` / `commit_converged=1` assertions must still pass
  unchanged — they pin the rc-2 and rc-0 paths.

Then:

```bash
bash tests/test_no_unscoped_task_commit.sh
bash tests/test_verification_followup.sh
bash tests/test_verification_followup_anchor.sh
bash tests/test_create_manual_verification.sh
bash tests/test_create_manual_verification_gates.sh
bash tests/test_verified_update.sh          # incl. Test 30 branch-mode fixture
bash tests/test_verified_update_flags.sh
bash tests/test_usage_update.sh
bash tests/test_note.sh                     # allowlist must not mask a real note.sh site
shellcheck .aitask-scripts/aitask_verification_followup.sh \
           .aitask-scripts/aitask_create_manual_verification.sh \
           .aitask-scripts/lib/verified_update_lib.sh
```

Step 9 (Post-Implementation) handles cleanup, archival, and merge.

## Risk

Levels below are the **reassessment** after the two inline mitigations were
confirmed (per `risk-evaluation.md` Step 3). Code-health was `medium` before
they were added to the plan body: every remaining bullet is now directly
controlled by a pre- or post-phase step, so the level is `low` as approved.

### Code-health risk: low
- `commit_metadata_update_local` is on the hot metadata-write path every skill
  run touches, and the seam changes the site's return-code contract in **both**
  directions: an unabsorbed `return 2` ("nothing to commit", a normal outcome)
  would abort the caller under `set -euo pipefail`, while an over-absorbed
  `return 1` would turn a real failure into a printed `UPDATED:` · severity:
  medium · → mitigation: inline post-phase set_e_abort_control
- Sites 1 and 3 already own an EXIT trap, so arming the seam's unstage trap
  naively would silently drop their temp-file cleanup · severity: medium ·
  → mitigation: inline post-phase set_e_abort_control
- Converting site 1 makes a commit that has **never executed** in its test
  fixture start executing there, so existing assertions meet a genuinely new
  code path · severity: low · → mitigation: inline pre-phase red_control_proof
- The `AIT_GIT_ALLOWLIST` entry leaves `aitask_note.sh` unguarded for the new
  pattern — a documented hole that only closes if its two multi-line hint
  strings are restructured · severity: low · → mitigation: note_hint_restructure

### Goal-achievement risk: low
- The task scopes "two sites"; the fix covers three. If the third is unwanted
  here it must be split out rather than silently folded in · severity: low ·
  → mitigation: inline pre-phase red_control_proof

### Planned mitigations
- timing: pre-phase | name: red_control_proof | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "a never-executed commit starts executing" + goal-achievement "the control could be vacuous" | desc: Run each new negative control against the unmodified source first and record the observed failure, so a control that passes for the wrong reason is caught before the fix lands.
- timing: post-phase | name: set_e_abort_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health "hot-path return-code contract change" + code-health "composed EXIT trap could drop temp-file cleanup" | desc: Drive each converted site under set -euo pipefail with nothing to commit, asserting exit 0 and that a side effect after the seam call still lands; additionally assert rc 1 is not absorbed at site 2 (non-zero return, CONVERGED=0, no UPDATED: line) and that sites 1 and 3 still remove their temp file.
- timing: after | name: note_hint_restructure | type: refactor | priority: low | effort: low | inline_risk: medium | added_complexity: medium | addresses: code-health "allowlist leaves aitask_note.sh unguarded for the new pattern" | desc: Restructure aitask_note.sh's two multi-line recovery-hint warn strings so their ./ait git commit text is parseable on one logical line, then delete the AIT_GIT_ALLOWLIST entry and its fixture.
