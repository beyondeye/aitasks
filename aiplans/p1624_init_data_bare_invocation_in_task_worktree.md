---
Task: t1624_init_data_bare_invocation_in_task_worktree.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1624 — `init_data` bare invocation inside a task worktree

## Context

`ait`'s task worktrees (`aiwork/<task_name>`) are linked git worktrees of the
code branch. Running `aitask_init_data.sh` with **no flags** inside one dies
with advice that cannot possibly work:

```
Error: Failed to create worktree. Run: git worktree add .aitask-data aitask-data
```

Reproduced live (scratchpad fixture, exit 1). The mechanism:

1. **Check 1** (`ALREADY_INIT`) probes the *relative* `.aitask-data/.git`. In an
   unlinked worktree neither exists → does not fire.
2. **Check 2** (`LEGACY_MODE`) tests whether `aitasks` is a real directory. In a
   worktree of a branch-mode project it is absent entirely → does not fire.
3. **Check 3** finds the `aitask-data` branch (a real branch of the shared
   repo) → proceeds.
4. **Step 4** runs `git worktree add .aitask-data aitask-data`, which git
   refuses because that branch is **already checked out at the primary's**
   `.aitask-data`. The `die` then names that exact impossible command as the
   remedy, and never mentions `--link-worktree`, the flag that actually applies.

t1616 added `--link-worktree <dir>` as a *separate* code path and deliberately
left the bare path alone, so this edge is pre-existing and untouched. Intended
outcome: the bare form classifies what it is standing in and names a remedy
that works.

### Three worktree cases, not one — all verified live

Probing the fixture showed the bare form has **three** distinct outcomes inside
a linked worktree, and only one of them is the reported defect:

| primary's state | today | correct? |
|---|---|---|
| has `.aitask-data` worktree | dies with the impossible remedy | **no** — the reported defect |
| no `aitask-data` branch at all | `NO_DATA_BRANCH`, exit 0 | **yes** — must be preserved |
| branch exists, no `.aitask-data` worktree | `INITIALIZED` — and plants the repo's **only** data checkout at `aiwork/tA/.aitask-data` | **no** — silently worse than the defect: the data worktree dies with the task worktree |

This is what fixes the guard's placement: it must sit **after** Check 3 (so the
`NO_DATA_BRANCH` answer survives) and must branch on whether the primary is
actually initialized (so it never claims a branch is checked out when it isn't).

Verified live: `aitask_init_data.sh --link-worktree "$PWD"` run from *inside*
the worktree succeeds (`LINKED`, exit 0), and a subsequent bare invocation there
reports `ALREADY_INIT`. The remedy the new message names is correct and runnable
from where the user is standing.

## Contract decision (user-confirmed)

The new states print a token on stdout and exit **non-zero (`die_code 3`)**,
with the real remedy on stderr.

Rationale: the four skill trees that call the bare form
(`aitask-pickrem` / `aitask-pickweb` × claude / codex / opencode, plus goldens)
already say *"If the command fails (non-zero exit), display the error and
abort."* A non-zero exit therefore makes every existing caller behave correctly
**with no doc changes**, and is fail-safe — a caller that has never heard of the
token still stops rather than proceeding into a checkout with no `aitasks/`.
Exit `3` is disjoint from `1` (the script's generic `die`/crash code) so a
caller can distinguish a recognized refusal from a genuine crash on the exit
code alone.

## Files to modify

- `.aitask-scripts/aitask_init_data.sh` — the guard, the two doc blocks, the
  Step 4 `die` message.
- `tests/test_init_data.sh` — a git-tracing runner and cases 23a–23h.

Reused as-is (no new derivation): `ait_canon_path` and `AIT_DATA_DIR_NAME` from
`lib/data_symlinks.sh`, `die_code` from `lib/terminal_compat.sh`, and the
already-absolute `SCRIPT_DIR` (line 31). The main-root derivation and the
primary-initialized probe copy the ones `--link-worktree` already uses
(`aitask_init_data.sh:83-87` and `:118-122`).

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_data_worktree_legacy_mode]` **Before touching the script**,
   add a test case asserting a bare invocation with `cwd` inside
   `<main>/.aitask-data/` reports `LEGACY_MODE` at exit 0. Run it against the
   **unmodified** script and confirm it passes — that is what makes it a
   characterization test rather than a restatement of the new behavior. This
   case is load-bearing: the data worktree *is* a linked worktree, so if Check 2
   ever stopped winning, the new guard would classify it as an unlinked task
   worktree. Re-run after the guard lands; it must still pass.

### 1. New Check 3b — classify the linked worktree, immediately before Step 4

Insert **after** Check 3 (the branch probe, line 178) and **before** Step 4.
Placement is the whole correctness argument: after Check 1/2 so `ALREADY_INIT`
and `LEGACY_MODE` still win; after Check 3 so `NO_DATA_BRANCH` still wins.

```bash
# --- Check 3b: bare invocation inside a linked worktree ---
# Checks 1 and 2 probe RELATIVE paths, so they only ever see this checkout. In a
# linked worktree with no data layout neither fires, and control reaches Step 4 —
# where `git worktree add` does one of two wrong things depending on the
# primary's state. Classify instead of guessing.
#
# Ordering is load-bearing. This runs AFTER Check 3, so a repo with no
# aitask-data branch still answers NO_DATA_BRANCH from inside a worktree exactly
# as it does today; that answer is already correct and must not be swallowed.
#
# Keyed on the worktree ROOT, not on $PWD: an ordinary subdirectory of the
# primary shares the primary's toplevel and must NOT be called a worktree, and a
# nested subdirectory of a task worktree must still resolve to that worktree.
# Both resolutions must be non-empty before refusing — anything unresolvable
# (not a repo, an unusual GIT_DIR) falls through to the pre-existing Step 4.
wt_git_common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [[ -n "$wt_git_common" ]]; then
    wt_main_root="$(ait_canon_path "$(dirname "$wt_git_common")" 2>/dev/null || true)"
    wt_toplevel="$(ait_canon_path "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || true)"
    if [[ -n "$wt_main_root" && -n "$wt_toplevel" && "$wt_toplevel" != "$wt_main_root" ]]; then
        # SCRIPT_DIR is absolute (line 31), so the printed command is copy-safe
        # from ANY cwd — including a nested subdirectory of the worktree, where
        # a ./.aitask-scripts/... spelling does not resolve.
        self="$SCRIPT_DIR/${BASH_SOURCE[0]##*/}"
        if [[ -d "$wt_main_root/$AIT_DATA_DIR_NAME/.git" \
              || -f "$wt_main_root/$AIT_DATA_DIR_NAME/.git" ]]; then
            # The primary holds the aitask-data branch, so a second worktree of
            # it cannot be created here. --link-worktree is the operation that
            # applies — and it accepts this worktree from any cwd.
            echo "WORKTREE_UNLINKED"
            die_code 3 "'$wt_toplevel' is a linked git worktree with no task-data layout, and the primary checkout at '$wt_main_root' already has the aitask-data branch checked out — a second worktree of it cannot be created here. Run: \"$self\" --link-worktree \"$wt_toplevel\""
        fi
        # The branch exists (Check 3 passed) but the primary has no data
        # worktree. Step 4 would SUCCEED here and put the repo's only task-data
        # checkout inside a throwaway task worktree, which is removed when the
        # task lands. Same state --link-worktree already calls NOT_INITIALIZED.
        echo "NOT_INITIALIZED"
        die_code 3 "'$wt_toplevel' is a linked git worktree, and the primary checkout at '$wt_main_root' has no $AIT_DATA_DIR_NAME worktree. Initializing from here would put the repo's only task data inside this worktree. Run 'ait setup' in '$wt_main_root' first, then: \"$self\" --link-worktree \"$wt_toplevel\""
    fi
fi
```

`NOT_INITIALIZED` is deliberately the **same** token `--link-worktree` already
emits for the same state — one name per state. Only the exit code differs (0
there, because that path's no-op is harmless; 3 here, because proceeding is
not), and both doc blocks say so explicitly.

### 2. Step 4 — stop advising the impossible command

After Check 3b the remaining ways to reach this `die` are a subdirectory of the
primary and genuine failures (permissions, corrupt repo). For all of them
`Run: git worktree add .aitask-data aitask-data` is wrong or useless. Surface
git's own error instead:

```bash
wt_add_err="$(git worktree add .aitask-data aitask-data 2>&1 >/dev/null)" || {
    die "Failed to create the .aitask-data worktree in '$PWD'. git said: ${wt_add_err:-<no output>}"
}
```

(`2>&1 >/dev/null` in that order captures stderr and discards stdout.)

### 3. Document the new vocabulary

Add to **both** output lists — the header comment (lines 14-17) and the
`--help` heredoc (lines 50-54):

```
WORKTREE_UNLINKED  Linked worktree, primary already holds the data branch
                   (exit 3) — give this worktree the layout with
                   --link-worktree <dir>
NOT_INITIALIZED    Linked worktree, primary has no .aitask-data worktree
                   (exit 3) — run 'ait setup' at the primary first.
                   Same state as the --link-worktree token of that name,
                   which exits 0 because its no-op is harmless.
```

### 4. Tests — `tests/test_init_data.sh`, appended after Test 22

**A git-tracing runner, because state assertions cannot prove intent here.**
A failed duplicate-branch `git worktree add` leaves *precisely* the state a
never-attempted one leaves — no `.aitask-data` directory, the same three
worktree entries (confirmed in the repro). So asserting on leftovers cannot
distinguish "the guard stopped it" from "Step 4 ran and git refused", and a
regression that reaches Step 4 would pass. Trace the invocations instead:

```bash
# trace_run <dir> -> bare (no-flag) invocation with cwd=<dir>, run with a
# PATH-injected `git` shim that appends every argv to $TRACE_LOG before
# delegating to the real git. Exposes BARE_OUT / BARE_ERR / BARE_RC / TRACE.
#
# Needed because a REFUSED `git worktree add` and a NEVER-ATTEMPTED one leave
# identical on-disk state; only the attempt itself distinguishes them.
trace_run() {
    local shimdir errfile real_git
    shimdir="$(mktemp -d)"; errfile="$(mktemp)"; TRACE_LOG="$(mktemp)"
    real_git="$(command -v git)"
    cat > "$shimdir/git" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$TRACE_LOG"
exec "$real_git" "\$@"
EOF
    chmod +x "$shimdir/git"
    BARE_RC=0
    BARE_OUT="$(cd "$1" && PATH="$shimdir:$PATH" \
        bash "$LW_MAIN/.aitask-scripts/aitask_init_data.sh" 2>"$errfile")" || BARE_RC=$?
    BARE_ERR="$(cat "$errfile")"; TRACE="$(cat "$TRACE_LOG")"
    rm -rf "$shimdir" "$errfile" "$TRACE_LOG"
}
```

The script is invoked by its **primary** path (as `lw_run` already does —
`install_script` copies into the working tree without committing, so the
worktree has no `.aitask-scripts/`), while `cwd` is the directory under test,
which is what the bare form keys on.

- **23a — the defect.** `lw_repo primary`, `trace_run "$LW_WT"`:
  stdout exactly `WORKTREE_UNLINKED`; `BARE_RC` is `3`; stderr contains
  `--link-worktree` and the worktree path; stderr does **not** contain
  `git worktree add .aitask-data aitask-data` (the direct pin on the impossible
  advice); `assert_not_contains "worktree add" "$TRACE"`; and
  `assert_contains "rev-parse" "$TRACE"` — shim-liveness, so an empty log from a
  failed PATH injection cannot pass the not-contains vacuously.
- **23b — nested subdirectory.** `mkdir -p "$LW_WT/nested/deep"`,
  `trace_run "$LW_WT/nested/deep"` → same token and exit 3, proving the guard
  keys on the worktree root. Then extract the command from `BARE_ERR`, assert
  the script path in it is absolute and exists, and **run it verbatim** →
  `LINKED`, exit 0. This is the copy-safety pin: the old `./.aitask-scripts/…`
  spelling does not resolve from that cwd.
- **23c — positive control, the guard must not shadow a working worktree.**
  `lw_run "$LW_WT"` to link it, then `trace_run "$LW_WT"` → `ALREADY_INIT`,
  exit 0. Without this, 23a would also pass if the guard fired unconditionally.
- **23d — the primary is unaffected.** With the linked worktree present,
  `trace_run "$LW_MAIN"` → `ALREADY_INIT`, exit 0.
- **23e — an ordinary subdirectory is not a worktree.** `mkdir "$LW_MAIN/sub"`,
  `trace_run "$LW_MAIN/sub"` → stdout carries **neither** new token, and stderr
  does not claim "linked git worktree". Pins the toplevel-vs-`$PWD` choice.
- **23f — `NO_DATA_BRANCH` survives (the ordering pin).** A repo with a linked
  worktree and **no** `aitask-data` branch (`setup_repo_with_remote` +
  `install_script`, no `create_data_branch_setup`) → `NO_DATA_BRANCH`, exit 0.
  This is the case the earlier draft of this plan would have regressed.
- **23g — uninitialized primary is classified, not initialized-into.** From
  `lw_repo`, `git worktree remove --force .aitask-data` at the primary, then
  `trace_run "$LW_WT"` → `NOT_INITIALIZED`, exit 3, stderr mentions `ait setup`;
  `assert_not_contains "worktree add" "$TRACE"`; and
  `assert_dir_not_exists "$LW_WT/.aitask-data"` — the concrete harm (today this
  case creates it, verified live).
- **23h — tracer positive control.** A branch-mode primary that is **not** a
  worktree and **not** yet initialized: `trace_run` at its root → `INITIALIZED`
  and `assert_contains "worktree add" "$TRACE"`. Proves the `not_contains`
  assertions in 23a/23g are capable of failing.
- Extend **Test 9** (help flag) with `assert_contains` for `WORKTREE_UNLINKED`,
  matching how it already pins `NOT_INITIALIZED`.

### Post-phase (risk mitigations)

1. `[verify_guard_against_real_repo_geometry]` After the change lands and the
   suite passes, exercise the bare form inside a **real** `aiwork/` worktree of
   this repo — genuine branch-mode `.aitask-data`, real remote, the installed
   `git` — rather than only the synthetic fixture. Confirm the token, exit `3`,
   and that the command printed in stderr, pasted verbatim, links the worktree.
   Remove the throwaway worktree afterwards.

## Flagged, not in scope

`.aitask-scripts/aitask_setup.sh:1522` carries the same impossible advice
(`warn "Failed to create worktree. You may need to run: git worktree add
.aitask-data aitask-data"`). It is a `warn`+`return` inside `ait setup`, which
operates on an explicit `$project_dir` rather than `$PWD` — a different flow
with a different contract. Recorded for Step 8b to route as its own
upstream-defect follow-up.

## Verification

```bash
bash tests/test_init_data.sh                       # all cases, incl. 23a-23h
shellcheck .aitask-scripts/aitask_init_data.sh
bash tests/test_task_worktree_helper.sh            # exercises --link-worktree
bash tests/test_task_git.sh                        # other init_data caller
```

End-to-end by hand against the scratchpad fixtures that reproduced each case:

1. Bare invocation in an unlinked `aiwork/tA` → `WORKTREE_UNLINKED`, exit 3.
2. Paste the command from that stderr verbatim, from a nested subdirectory →
   `LINKED`, exit 0.
3. Bare invocation in the same worktree again → `ALREADY_INIT`, exit 0.
4. Bare invocation at the primary → `ALREADY_INIT`, exit 0 (unchanged).
5. Bare invocation inside `.aitask-data/` → `LEGACY_MODE` (unchanged).
6. Worktree with no data branch → `NO_DATA_BRANCH`, exit 0 (unchanged).
7. Worktree whose primary lost its `.aitask-data` → `NOT_INITIALIZED`, exit 3,
   and **no** `.aitask-data` created in the worktree.

## Risk

### Code-health risk: low
- The guard could shadow a state that already answers correctly — `ALREADY_INIT`
  for a linked worktree, `LEGACY_MODE` inside `.aitask-data/` (which is itself a
  linked worktree, so only Check 2 winning keeps it out of the guard), or
  `NO_DATA_BRANCH` · severity: medium · → mitigation: inline pre-phase
  characterize_data_worktree_legacy_mode (plus the 23c/23d/23e/23f controls)
- `git rev-parse` mis-resolving under an unusual `GIT_DIR` / bare repo could
  make the guard misfire at the primary · severity: low · → mitigation: inline
  post-phase verify_guard_against_real_repo_geometry
  (also contained by construction: both resolutions must be non-empty before
  refusing, so any resolution failure falls through to today's behavior)

### Goal-achievement risk: low
- The guard now has three outcomes rather than one, and the review of an earlier
  draft caught a placement that would have regressed `NO_DATA_BRANCH`. Each of
  the three is now pinned by its own case (23a / 23f / 23g), and the two
  "nothing was attempted" claims rest on a git tracer with a positive control
  (23h) rather than on state that a failed attempt reproduces exactly ·
  severity: low · → mitigation: covered by the test set above

### Planned mitigations
- timing: pre-phase | name: characterize_data_worktree_legacy_mode | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: guard shadowing a state that already answers correctly | desc: characterize LEGACY_MODE for a bare invocation inside .aitask-data/ against the unmodified script, then re-run after the guard lands
- timing: post-phase | name: verify_guard_against_real_repo_geometry | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: git rev-parse resolving differently under production geometry | desc: exercise the bare form in a real aiwork/ worktree of this repo and paste the printed remedy verbatim

**Reassessment after inlining:** both mitigations are additive
test/verification steps that touch no production code path, so the levels above
are unchanged — code-health **low**, goal-achievement **low** — and now rest on
executed checks rather than on construction alone.

## Implementation notes

Landed as planned. Deviations, all recorded here rather than silently absorbed:

- **Test numbering.** The pre-phase characterization case is **Test 23**; the
  guard cases are **24a–24h** (the plan said 23a–23h). Splitting the numbers
  keeps the characterization case, which must be written and run *before* the
  guard, visually separate from the cases that require it.
- **`strip_ansi` helper added to the test file.** Not in the plan. `die_code`
  wraps its message in `${RED}…${NC}` unconditionally — not tty-gated — so the
  remedy extracted from stderr in 24b carried a trailing reset that broke
  `eval`. The helper builds a literal ESC byte rather than using the GNU-only
  `\x1b` shorthand, matching `shadow_strip_ansi` in `aitask_shadow_capture.sh`.
- **24c establishes its own precondition.** It calls `lw_run "$LW_WT"`
  (idempotent) instead of inheriting the linked state from 24b's remedy run, so
  a break in 24b fails 24b alone rather than also failing this control for the
  wrong reason.

### Evidence

- **Pre-phase mitigation executed as specified.** Test 23 was written and run
  against the **unmodified** script first: 87/87 pass. It characterizes today's
  behavior, so its post-change pass is meaningful.
- **Forced-failure injection.** With the guard's condition neutralized
  (`"$wt_toplevel" = "XXX_GUARD_DISABLED"`), 16 assertions failed — including
  `24a: never attempted a worktree add` (the trace recorded the git calls) and
  `24g: no data checkout planted in the worktree` (the directory appeared).
  24d/24e/24f/24h kept passing, as they must. The guard was then restored from a
  file copy and the suite re-run.
- **Final:** `tests/test_init_data.sh` 118/118;
  `tests/test_task_worktree_helper.sh` 102/102; `tests/test_task_git.sh` 24/24.
  `shellcheck` reports the same code set as HEAD on both files (SC1091 info on
  both, pre-existing SC2034 on the test file) — no new findings.
- **Post-phase mitigation executed.** Against a real `aiwork/` worktree of this
  repo, not the fixture: `WORKTREE_UNLINKED`, exit 3; the printed command pasted
  verbatim returned `LINKED`, exit 0; a repeat bare invocation returned
  `ALREADY_INIT`, exit 0. The probe worktree and its branch were removed.

## Final Implementation Notes

- **Actual work done:** Added Check 3b to `.aitask-scripts/aitask_init_data.sh`,
  placed after the branch probe and immediately before Step 4. It classifies a
  bare invocation made from a linked worktree into two states — `WORKTREE_UNLINKED`
  (the primary holds the `aitask-data` branch, so a second worktree of it cannot
  be created here) and `NOT_INITIALIZED` (the primary has no `.aitask-data`
  worktree, so initializing from here would put the repo's only task data inside
  a throwaway task worktree) — each exiting 3 with a copy-safe absolute remedy
  built from `SCRIPT_DIR`. Step 4's `die` now reports git's own error instead of
  naming the command that just failed. Both output vocabularies (header comment
  and `--help`) document the new tokens. `tests/test_init_data.sh` gained a
  characterization case, eight guard cases, a `strip_ansi` helper and a
  git-tracing runner (+188 lines).
- **Deviations from plan:** Three, all detailed under "Implementation notes"
  above — test numbering (23 + 24a-h rather than 23a-h), the unplanned
  `strip_ansi` helper, and 24c establishing its own precondition. None changes
  the shipped behavior of the script.
- **Issues encountered:** (1) `die_code` colours its message unconditionally —
  it is not tty-gated — so the remedy extracted from stderr in 24b carried a
  trailing ANSI reset and `eval` failed. Fixed with a portable `strip_ansi`
  helper that builds a literal ESC byte rather than using the GNU-only `\x1b`
  shorthand. (2) Review of the first draft caught that placing the guard before
  Check 3 would have regressed the already-correct `NO_DATA_BRANCH` answer and
  produced a message falsely claiming the branch was checked out; the guard was
  moved after Check 3 and gated on the primary's actual state.
- **Key decisions:** (a) Token **plus non-zero exit** rather than exit 0 — the
  four skill trees calling the bare form already abort on a non-zero exit, so
  every existing caller behaves correctly with no doc changes, and a caller that
  has never heard of the token still fails safe. Exit 3 is disjoint from the
  script's generic `die` code of 1. (b) The guard keys on the **worktree root**
  (`git rev-parse --show-toplevel`), not `$PWD`, so an ordinary subdirectory of
  the primary is not miscalled a worktree and a nested subdirectory of a task
  worktree still resolves correctly. (c) `NOT_INITIALIZED` deliberately reuses
  the token `--link-worktree` already emits for the same state — one name per
  state — with the exit-code difference documented in both output lists.
  (d) The "nothing was attempted" claims are proven by a PATH-injected git
  tracer with a positive control, because a refused `git worktree add` and a
  never-attempted one leave identical on-disk state.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:1522 — the same impossible remedy text ("Failed to create worktree. You may need to run: git worktree add .aitask-data aitask-data") on ait setup's own worktree-creation failure path; it warns and returns rather than dying, and operates on an explicit $project_dir instead of $PWD, so it is a separate flow with its own contract.`
