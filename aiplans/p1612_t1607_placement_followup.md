---
Task: t1612_t1607_placement_followup.md
Branch: main
Base branch: main
Output branch: main
---

# t1612 — Give `CLAUDE.md` the same setup lifecycle as `AGENTS.md`

## Context

t1607 restored the hand-maintained-`CLAUDE.md` skip guard
(`CLAUDEMD_HAND_MAINTAINED_SENTINEL`) inside `update_claudemd_git_section`, and
its own risk section flagged that the guard is **almost unreachable**: the
function has exactly one production call site — `setup_data_branch()` Step 8,
`.aitask-scripts/aitask_setup.sh:1680-1681` — and `setup_data_branch`
early-returns before it in four places:

| line | condition | when it fires |
|---|---|---|
| 1409-1412 | not a git repo | non-git projects |
| 1415-1419 | `.aitask-data/.git` exists | **every re-run of `ait setup`** on a configured project |
| 1452-1459 | user declines the data-branch prompt | legacy mode, first setup |
| 1493-1497 | `git worktree add` failed | error path |

So `CLAUDE.md`'s aitasks block is written **only** on a successful first-time
data-branch setup: never refreshed on re-runs, never written at all in legacy
mode. `AGENTS.md` has no such problem — `update_agentsmd` is called
unconditionally from `setup_code_agents` (`:2555`) and is regenerated on every
`ait setup`.

This task moves the `CLAUDE.md` call to sit beside `update_agentsmd`, which both
gives the file the same lifecycle and makes t1607's guard reachable on real
runs instead of only under direct function invocation.

`update_claudemd_git_section` is safe to move: it takes only `project_dir`,
reads no `setup_data_branch`-local state (no branch name, no `needs_migration`,
no `gitignore_changed`), and `setup_code_agents` computes the identical
`local project_dir="$SCRIPT_DIR/.."`. In `main()` the order is
`setup_data_branch` (`:3801`) → `setup_code_agents` (`:3876`) →
`commit_framework_files` (`:3885`), so the data-branch symlinks and the seed
metadata are in place at the new call site (`populate_data_branch_seed_metadata`
`:1844` and `ensure_agent_config_seeds` `:1865` both run earlier), and the write
still lands before the framework commit.

### Two things this does NOT buy — state them, don't over-claim

1. **Early-return case 4 stays broken on installed projects.** `install.sh:1335`
   deletes `seed/` after install, so `assemble_aitasks_instructions`' fallback
   (`:1281-1287`) is gone and it depends solely on
   `aitasks/metadata/aitasks_agent_instructions.seed.md`. If `git worktree add`
   failed on a fresh clone of a branch-mode repo, `aitasks` is a *dangling
   committed symlink*, the seed is unreachable, `assemble` returns 1 and
   `update_claudemd_git_section` returns 0 at `:1363` without writing —
   wherever it is called from. This change fixes cases 1-3, not case 4.
2. **The write moves from position ~1 to position ~20 of a `set -euo pipefail`
   script.** `install_cli_tools`, `setup_python_venv`, `setup_pypy_venv`,
   `setup_chat_deps`, `setup_dev_deps` and `install_global_shim` (`:3786-3874`)
   now all run *before* the CLAUDE.md write; a hard failure in any of them
   aborts `main()` first. That is exactly the exposure `AGENTS.md` already has,
   so it is parity rather than a regression — but it is a tradeoff, not a
   strict improvement.

## Implementation

### 1. `.aitask-scripts/aitask_setup.sh` — move the call

**1a. Delete Step 8 from `setup_data_branch` (`:1680-1681`)** — both the
`# --- Step 8: Update CLAUDE.md ---` comment and the call. Do **not** renumber
the remaining steps (Step 9's comment stays; renumbering would churn the diff
and break step references in `test_data_branch_setup.sh` comments). Leave a
one-line pointer so the next reader does not re-add it:

```bash
    # CLAUDE.md is intentionally NOT written here: it is regenerated on every
    # `ait setup` from setup_code_agents, beside update_agentsmd (t1612).
```

**1b. Drop `CLAUDE.md` from Step 9's `files_to_add` (`:1690-1692`).** This is a
real bug fix, not tidy-up. With the write gone, the clause can only stage a
`CLAUDE.md` that *someone else* modified — and the Step 9 commit is **not**
path-scoped (`git diff --cached --quiet` at `:1696` and `git commit -m …` at
`:1697-1701` both run with no `--` pathspec), so a user's uncommitted `CLAUDE.md`
edits get swept into `ait: Configure task data branch…`, bypassing the
`snapshot_pre_setup_dirty` baseline entirely. `_ait_framework_paths` (`:2980`)
already lists `CLAUDE.md`, and `commit_framework_files` (`:3113`) commits it
path-scoped (`git add --` / `git diff --cached --quiet --` / `git commit --`,
`:3204-3212`) **and** subtracts the baseline (`:3145-3155`).

Consequence to record in the docs: after this change, a `CLAUDE.md` that was
already dirty before `ait setup` ran has its refreshed block **deliberately left
uncommitted** and reported under "Pre-existing uncommitted changes under
framework paths" (`:3157-3166`). That is the intended behavior — and a change
from today's forced `git add`.

**1c. Add the call in `setup_code_agents`, immediately after
`update_agentsmd "$project_dir"` (`:2555`)**:

```bash
    # CLAUDE.md gets the same unconditional lifecycle as AGENTS.md, but it is
    # project-OWNED mixed content: update_claudemd_git_section's
    # CLAUDEMD_HAND_MAINTAINED_SENTINEL guard (t1607) skips a markerless file
    # that already documents the conventions by hand. Living here rather than in
    # setup_data_branch Step 8 is what makes that guard -- and the refresh --
    # reachable on re-runs and in legacy mode (t1612).
    update_claudemd_git_section "$project_dir"
```

`setup_code_agents` (`:2546-2573`) has **no early return of its own** — every
`return` in its call graph belongs to a callee — so placing the call after
`update_agentsmd` and before the `_is_agent_installed` gates keeps it
unconditional.

### 2. Shared test drive helper

Both suites need to invoke the real `setup_code_agents` against a fixture. Add
this helper to each file (they are self-contained and run individually):

```bash
# Drive the real setup_code_agents against <project_dir>. Only _is_agent_installed
# is stubbed, and only for determinism: it is `command -v codex/opencode`
# (aitask_setup.sh:215-222), i.e. a property of the developer's machine -- both ARE
# present on this box, so without the stub the drive would really run
# setup_codex_cli/setup_opencode against the fixture. setup_claude_code and
# prune_retired_skills self-no-op here (no aitasks/metadata/claude_settings.seed.json,
# no $SCRIPT_DIR/aitask_prune_retired_skills.sh) -- note that in PRODUCTION both do
# run, since ensure_agent_config_seeds (:1878) installs the settings seed before
# setup_code_agents. update_agentsmd and update_claudemd_git_section run for real.
# stdout: setup_code_agents' own output, unmerged -- T41/T42 assert on info()
#         lines, and info() writes to STDOUT (aitask_setup.sh:137).
# stderr: passed through to the test's stderr, so assemble_aitasks_instructions'
#         warn stays visible on failure without polluting the stdout assertions.
# exit:   setup_code_agents' real status -- callers assert it (see below).
run_setup_code_agents() {
    local project_dir="$1"
    (
        SCRIPT_DIR="$project_dir/.aitask-scripts"
        mkdir -p "$SCRIPT_DIR"
        _is_agent_installed() { return 1; }
        setup_code_agents </dev/null
    )
}
```

**Every call site captures stdout and the status**, even the ones that only
assert on files — a drive that died early would otherwise look identical to one
that ran and wrote nothing:

```bash
out=""; rc=0
out="$(run_setup_code_agents "$TMPDIR_TEST")" || rc=$?
assert_eq "T40: setup_code_agents exited 0" "0" "$rc"
```

Three harness constraints, each of which silently produces a false green if
ignored:

- **Assertions stay OUTSIDE the subshell.** Both suites use in-process
  `PASS`/`FAIL`/`TOTAL` with no `assert_counters_init`, so an assertion inside
  `( … )` is lost (CLAUDE.md `### Testing`, t1207). The subshell exists to keep
  the stub from leaking into later tests.
- **No `2>&1` inside the helper, and no `|| true` either.** Merging stderr would
  let a `warn` line satisfy a message assertion; swallowing the status would
  hide a callee that started returning non-zero. The
  `out="$(…)" || rc=$?` idiom above is what makes this `set -e`-safe:
  `tests/test_agent_instructions.sh:7` sets `set -e` *and* line 14 sources
  `aitask_setup.sh`, whose line 2 is `set -euo pipefail`, so that file runs
  under `-u` and `-o pipefail` too — a bare `out="$(…)"` returning non-zero
  would abort the whole file at the assignment, printing no `FAIL:` line and
  never reaching the summary. (`tests/test_data_branch_setup.sh:101` and
  `tests/test_setup_git.sh:45` undo the flags explicitly; that is why only the
  `test_agent_instructions.sh` copy is exposed — but use the same idiom in all
  three for consistency.)
- **`assert_file_contains` has opposite argument orders in the two suites** —
  `test_agent_instructions.sh:26` is `(desc, expected, file)`,
  `test_data_branch_setup.sh:42` is `(desc, file, pattern)`. `tests/lib/asserts.sh`
  deliberately provides no shared version. Copying an assertion across suites
  inverts the args and yields a check that passes on an empty string. Prefer
  `assert_file_exists` / `assert_file_not_exists` from `tests/lib/asserts.sh`.

### 3. `tests/test_data_branch_setup.sh`

**3a. Test 1 (`:204-206`) — flip the characterization, then prove the handoff.**
Test 1 is the *only* fixture that reaches Step 8 today (it copies the seed at
`:110-112`), so it is the discriminating production-reachable case:

1. after `setup_data_branch`, assert `CLAUDE.md` does **not** exist
   (`assert_file_not_exists`);
2. `run_setup_code_agents "$TMPDIR_1/local"` → assert the block is there
   (`## Git Operations on Task/Plan Files`, `./ait git`, exactly one
   `^>>>aitasks$`);
3. **the re-run case the task asks for, on a genuinely already-configured
   project** (`.aitask-data/.git` now exists): replace the marked block's body
   with `STALE BLOCK t1612`, call `run_setup_code_agents` again, and assert
   `STALE BLOCK t1612` is gone, the regenerated content is back, and there is
   still exactly one marker pair.

The absence assertion alone would be vacuous; steps 2-3 on the same fixture are
what prove the responsibility *moved* rather than *vanished*.

**3b. New test — the Step 9 baseline bypass (covers 1b).** This is the only
assertion in the whole plan that fails on today's code *and* on the
"added the call but left `files_to_add` alone" mutant:

- fixture: `setup_local_repo` + `setup_seed_file`, with a `CLAUDE.md` committed
  to `HEAD`, then modified in the worktree to contain `USER EDIT t1612`;
- run `setup_data_branch` (reaches Step 9);
- assert `git show HEAD:CLAUDE.md` does **not** contain `USER EDIT t1612`, and
  `git status --porcelain` still reports `CLAUDE.md` as modified.

Today the unscoped `git add` + `git commit` commits the user's edit; after 1b it
is left alone.

**3c. Test 3 (`:305-341`) — leave it alone.** Its fixture (`:308-310`) copies no
seed, so `assemble_aitasks_instructions` returns 1 and
`update_claudemd_git_section` has *never* written anything there — today or
after this change. (That it silently passed regardless is itself evidence for
t1612's premise.) Extending it would require adding a seed fixture for no
coverage that 3a does not already provide on a real already-configured project.

### 4. `tests/test_agent_instructions.sh` — new section after T39

Four tests. T40/T41/T42 drive the real `setup_code_agents`; T43 is structural.
Deliberately **not** added: a marker-refresh test (T12d, `:338-355`, already
pins stale-body removal and the single-marker-pair invariant against a direct
call) and a separate "legacy layout" test (`setup_tmpdir` already *is* a legacy
layout — real `aitasks/`, no `.aitask-data/` — and nothing in
`setup_code_agents`' call graph reads `.aitask-data/`, symlinks or branch mode,
so such a test could not distinguish any implementation from any other).

- **T40 — reachability.** Fixture has no `CLAUDE.md` ⇒ after
  `run_setup_code_agents`, `CLAUDE.md` has the marker pair and the shared
  content, **and `AGENTS.md` does too**. The `AGENTS.md` half is the positive
  control that the drive really executed the function body rather than no-opping.
- **T41 — the upgrade path this change actually unlocks.** An already-installed
  project whose markerless `CLAUDE.md` carries user prose and **no** sentinel now
  receives the whole shared block on its next `ait setup`. That is a large,
  unsolicited mutation of a project-owned file, so pin it: run
  `run_setup_code_agents` **twice**; assert the user's prose survives both runs,
  the block is present, and there is still exactly one `^>>>aitasks$` /
  `^<<<aitasks$` pair (i.e. the second run refreshes in place, it does not append
  a second block). Mirrors T21's AGENTS.md shape (`:537-556`).
- **T42 — the t1607 guard fires on the now-live path.** Markerless `CLAUDE.md`
  containing `$CLAUDEMD_HAND_MAINTAINED_SENTINEL` plus custom prose ⇒
  byte-identical before/after, no `>>>aitasks` added, and all three `info`
  fragments on the captured stdout (`leaving it hand-maintained`,
  `'>>>aitasks' / '<<<aitasks' line pair`, `overwritten on every setup`).
  T12b asserts this against a direct call; the point of t1612 is that the guard
  now stands on the path `ait setup` really takes, so it needs an assertion
  there. T40 and T42 together cover both branches of the new call site.
- **T43 — structural pair; both halves load-bearing.** Probe the *sourced
  function bodies* (`declare -f` reproduces from the parsed AST and strips
  comments, so neither the 1a nor the 1c comment can skew it; precedent at
  `tests/test_setup_git.sh:614-624`):
  - `assert_not_contains` `update_claudemd_git_section` in
    `"$(declare -f setup_data_branch)"` — this is what proves **no**
    `setup_data_branch` path writes `CLAUDE.md`, including the decline branch
    that cannot be driven (it needs `[[ -t 0 ]]` true and `tests/` has no
    pty/expect harness), and it is the **only** detector of the
    "added the new call but forgot to delete Step 8" double-write — which is
    otherwise functionally invisible, since `insert_aitasks_instructions`'
    marker replacement makes a double write byte-identical to a single one;
  - `assert_contains` it in `"$(declare -f setup_code_agents)"` — the positive
    control; without it, renaming the function zeroes both halves and reads green.

  Use `assert_contains` / `assert_not_contains` (they wrap `grep -qF` in an
  `if`, so they are `set -e`-safe). Do **not** write `n=$(declare -f … | grep -c …)`
  — that aborts the file under `set -e` when the count is zero.

### 4b. `tests/test_setup_git.sh` — the commit guarantee and the `main()` wiring

§3 and §4 drive `setup_code_agents` **directly**, so on their own they would
stay green even if `main()` stopped calling it, called it *after*
`commit_framework_files`, or if `commit_framework_files` failed to pick
`CLAUDE.md` up. Those are exactly the two things the task's Scope notes ask to
*verify rather than assume* ("`commit_framework_files` should cover it" and
"the ordering … still leaves `CLAUDE.md` committed exactly once"), and this
change is what makes them load-bearing: before it, `CLAUDE.md` was committed by
`setup_data_branch`'s own self-contained Step 9; after it, correctness depends
on a cross-function ordering invariant in `main()` that nothing pins.

`tests/test_setup_git.sh` is the right home — it already owns
`commit_framework_files` (Tests 1/1b/10/11/12/14), the baseline behavior
(Tests 20/21) and the `declare -f main` ordering probe (Test 22) — and it does
`set +euo pipefail` at `:45`.

**Fixture note that decides whether these tests mean anything:**
`setup_fake_project` (`:24-38`) creates `aitasks/metadata/` but **no**
instructions seed and no `seed/` dir, so `assemble_aitasks_instructions` returns
1 and `update_claudemd_git_section` writes nothing. Each of the two tests below
must first copy `seed/aitasks_agent_instructions.seed.md` into the fixture's
`aitasks/metadata/`, exactly as `test_data_branch_setup.sh:56-58` does. Without
it both tests pass vacuously. Add the `run_setup_code_agents` helper here too.

- **Test A — a generated `CLAUDE.md` is committed, exactly once.** Model on
  Test 20 (`:544-570`): `setup_fake_project`, `git init` + commit, then
  `snapshot_pre_setup_dirty` (so the baseline is armed and non-bootstrap —
  `.aitask-scripts/VERSION` is tracked, which is what `:3078-3081` keys on),
  then `run_setup_code_agents`, then `commit_framework_files </dev/null`.
  Assert: `git show HEAD:CLAUDE.md` carries the block;
  `git status --porcelain -- CLAUDE.md` is **empty**; and
  `git log --oneline -- CLAUDE.md | wc -l` is **1** — the literal "committed
  exactly once" the task asks for, which also fails if a future edit
  reintroduces a second writer.
- **Test B — a pre-existing dirty `CLAUDE.md` is reported, not committed.**
  Model on Test 21 (`:572-611`), whose whole shape is this negative control.
  Fixture: `CLAUDE.md` tracked in the init commit with ordinary prose and **no**
  sentinel (so the t1607 guard does not fire and the block really is appended on
  top of the dirty file — the strong version of the claim), then modified with
  `USER EDIT t1612` **before** `snapshot_pre_setup_dirty`. Then
  `run_setup_code_agents` + `commit_framework_files`. Assert: `USER EDIT t1612`
  is **not** in `git show HEAD:CLAUDE.md`; the captured output reports it under
  "left alone" / "Pre-existing uncommitted changes"; and
  `git status --porcelain` still shows `CLAUDE.md` modified. Reset
  `AIT_SETUP_BASELINE_ARMED=0` afterwards, as Tests 20/21 do.
- **Test C — `main()` ordering.** Mirror Test 22 (`:613-624`) exactly, on
  `main_body="$(declare -f main)"`: assert `main()` calls `setup_code_agents` at
  all, that `setup_data_branch` precedes it (the seed metadata and symlinks must
  exist first, or `assemble_aitasks_instructions` silently falls back to `seed/`
  — present in a dev checkout, deleted in an installed project), and that
  `setup_code_agents` precedes `commit_framework_files` (or the generated block
  is never committed). Use `declare -f`, not the
  `awk '/^main\(\) \{/,/^\}/'` variant at `test_data_branch_setup.sh:557` — the
  parsed body is comment-stripped and independent of source formatting.

### 5. Docs

**5a. `aidocs/framework/aitasks_extension_points.md`.** Two edits:

- The `CLAUDE.md` bullet (`:96-108`): "A project with **no** aitasks prose in
  `CLAUDE.md` still gets the block appended on **first setup**" → written and
  then **refreshed on every `ait setup`**, from `setup_code_agents` beside
  `AGENTS.md`. Name the call site, so "why is this file different" is answered
  by the *guard* rather than by an accident of reachability.
- The `AGENTS.md` commit note (`:93-95`, "`ait setup` **commits `AGENTS.md`
  itself** (`ait: Add aitask framework`)"): this now applies to `CLAUDE.md` too.
  It is the sentence that tells a reader which commit to look in, so leaving it
  AGENTS-only makes the two bullets contradict each other. Add the baseline
  caveat from 1b (a pre-dirty `CLAUDE.md` is reported, not committed).

**5b. `tests/test_agent_instructions.sh` T38's comment (`:843-847`).** It
currently says the hand-maintained contract "was true only by accident until
t1607: `setup_data_branch` Step 8 early-returns here because `.aitask-data/.git`
exists, so the append branch was never reached." That reason is falsified by
this change — this repo's own `ait setup` now *does* reach
`update_claudemd_git_section`, and T38 passes because the guard fires. Rewrite
it; T38's assertions are unchanged and become strictly stronger.

No website changes: the only `CLAUDE.md` references under `website/content/docs/`
are hyperlinks to the repo file, not descriptions of setup behavior.

### Post-phase (risk mitigations)

Both confirmed inline mitigations. They run after §1-§5 and are part of the same
commit.

1. **[announce_claudemd_append_on_upgrade]** In `update_claudemd_git_section`,
   distinguish the three outcomes that today all print the same
   `"Updated aitasks instructions in CLAUDE.md"` (`:1381-1383`). Capture the
   file's state immediately before the write:

   ```bash
       local pre_state="absent"
       if [[ -f "$claudemd" ]]; then
           if grep -qF ">>>aitasks" "$claudemd"; then
               pre_state="managed"
           else
               pre_state="unmanaged"
           fi
       fi

       insert_aitasks_instructions "$claudemd" "$content"

       if grep -qF ">>>aitasks" "$claudemd"; then
           if [[ "$pre_state" == "unmanaged" ]]; then
               info "  Added a managed '>>>aitasks' block to your existing CLAUDE.md."
               info "  Everything between the markers is regenerated on every setup; the rest of your file is untouched."
               info "  To keep CLAUDE.md hand-maintained instead: delete the marker pair and keep a '$CLAUDEMD_HAND_MAINTAINED_SENTINEL' section of your own — 'ait setup' then leaves the file alone."
           else
               info "  Updated aitasks instructions in CLAUDE.md"
           fi
       fi
   ```

   The opt-out wording is load-bearing for the same reason t1607's opt-in
   wording was: deleting the markers *alone* would simply make the file
   append-eligible again on the next run. It is the sentinel section that arms
   the guard, so the message must name both halves. Reuse the constant, never a
   literal — T39 is what pins it to the seed.

   §4's **T41** gains two assertions on the captured stdout, which is what makes
   this phase falsifiable and what makes T41 discriminate both branches of the
   new code: run 1 (`unmanaged` → append) must print
   `Added a managed '>>>aitasks' block`; run 2 (`managed` → refresh) must print
   `Updated aitasks instructions in CLAUDE.md` and must **not** repeat the
   append announcement.

2. **[document_case4_gap]** In `aidocs/framework/aitasks_extension_points.md`,
   append one sentence to the `CLAUDE.md` bullet edited in §5a: a failed
   `git worktree add` on an *installed* project still leaves `CLAUDE.md`
   unwritten, because `aitasks/` is then a dangling symlink and `install.sh`
   deletes the `seed/` fallback — so `assemble_aitasks_instructions` has no
   resolvable seed and every instruction surface is skipped, not just this one.
   The sentence must state the exception, not merely hedge the claim: "on every
   `ait setup`" with a silent carve-out is the failure mode this phase exists to
   prevent.

## Verification

```bash
bash -n .aitask-scripts/aitask_setup.sh
shellcheck .aitask-scripts/aitask_setup.sh   # baseline is 19 findings, all pre-existing
                                             # and outside the edited regions — expect 19
bash tests/test_agent_instructions.sh        # T10-T12d, T22-T39, new T40-T43
bash tests/test_data_branch_setup.sh         # Tests 1-12, flipped 1 + new baseline test
bash tests/test_data_branch_migration.sh
bash tests/test_setup_git.sh                 # + new Tests A/B/C (commit guarantee, main wiring)
bash tests/test_init_data.sh
bash tests/test_task_git.sh
bash tests/test_opencode_setup.sh            # insert_aitasks_instructions untouched
```

Mutation checks, run against copies in the session scratchpad (never on tracked
files). Each must turn a **named** test red — if one does not, that is the
missing coverage, not an acceptable gap:

| mutant | must fail |
|---|---|
| add the `setup_code_agents` call, **keep** Step 8 (double write) | T43's `setup_data_branch` half, and Test 1's flipped absence assertion — nothing else can see it |
| delete the new `setup_code_agents` call | T40, T41, T42, Test 1 step 2 |
| move the call inside `if _is_agent_installed codex` | T40, T41, T42 (the stub returns 1) |
| revert 1b (`files_to_add+=("CLAUDE.md")` restored) | the new 3b baseline-bypass test — and **only** it |
| degrade the t1607 guard to a bare `return 0` | T42's three message assertions |
| collapse the post-phase announcement back to one unconditional `info` line | T41's run-1 append-announcement assertion — the file writes are byte-identical either way, so only the stdout assertions can see it |
| delete `setup_code_agents` from `main()`, or move it after `commit_framework_files` | §4b Test C — every direct-drive test in §3/§4 stays green |
| drop `CLAUDE.md` from `_ait_framework_paths` (`:2980`) | §4b Test A — nothing else notices, and the block would silently never be committed |
| arm no baseline / restore the unscoped sweep in `commit_framework_files` | §4b Test B |

Manual end-to-end on a throwaway copy — the scenario this repo could not reach
before:

```bash
work=$(mktemp -d); mkdir -p "$work/.aitask-scripts" "$work/aitasks/metadata"
cp seed/aitasks_agent_instructions.seed.md "$work/aitasks/metadata/"
cp CLAUDE.md "$work/CLAUDE.md"                       # hand-maintained, markerless
before=$(md5sum < "$work/CLAUDE.md")
source .aitask-scripts/aitask_setup.sh --source-only
( SCRIPT_DIR="$work/.aitask-scripts"; _is_agent_installed() { return 1; }; \
  setup_code_agents </dev/null )
[ "$before" = "$(md5sum < "$work/CLAUDE.md")" ] && echo "PASS: guard held on the live path"
grep -c '>>>aitasks' "$work/CLAUDE.md"               # expect 0
```

Positive controls on the same fixture, so the PASS is not vacuous: (1) strip the
`## Git Operations on Task/Plan Files` section → the block **is** appended;
(2) run the drive twice on that stripped copy → still exactly one marker pair
and the surrounding prose intact.

## Risk

### Code-health risk: low
- **The change makes `ait setup` mutate a project-owned file it never touched
  before.** Every already-configured project whose `CLAUDE.md` is markerless and
  carries *no* aitasks prose (so the t1607 sentinel guard does not fire) will,
  on its next `ait setup`, receive the entire shared instructions block appended
  — and `commit_framework_files` will commit it. That is the intended goal, but
  it is a large, unsolicited, auto-committed edit landing on upgrade with no
  announcement distinguishing it from a routine refresh. · severity: low
  (residual — the append still happens and is still auto-committed; the inline
  post-phase only makes it *legible and reversible*, it does not gate it) ·
  → mitigation: inline post-phase announce_claudemd_append_on_upgrade
- **Commit ownership for `CLAUDE.md` changes hands (1b).** A `CLAUDE.md` that
  was already dirty before `ait setup` ran is now *deliberately left
  uncommitted* by `commit_framework_files`' baseline subtraction, where Step 9's
  unscoped `git add` previously force-committed it. Strictly safer, but a
  visible behavior change. · severity: low · → mitigation: none — this is the
  bug being fixed; §3b pins that Step 9 no longer sweeps it, §4b Tests A/B pin
  both halves of the replacement guarantee (committed exactly once when clean;
  reported and left alone when pre-dirty), and doc 5a records it.
- The new tests drive `setup_code_agents` with `_is_agent_installed` stubbed and
  a fixture where `setup_claude_code` self-no-ops, so the harness is not
  representative of a production run (where `ensure_agent_config_seeds:1878`
  installs the settings seed and that prompt really fires). · severity: low ·
  → mitigation: none — the stub is required for determinism (both CLIs are
  installed on this box); the drive helper's comment states the divergence.

### Goal-achievement risk: low
- **`setup_data_branch` early-return case 4 is not fixed on installed
  projects.** `install.sh:1335` deletes `seed/`, so after a failed
  `git worktree add` on a fresh branch-mode clone the `aitasks` symlink dangles,
  `assemble_aitasks_instructions` returns 1, and
  `update_claudemd_git_section` writes nothing wherever it is called from. The
  task's goal ("`CLAUDE.md` is regenerated on every `ait setup`") is therefore
  delivered for cases 1-3 only. · severity: low (residual — the exception is now
  named in the shipped doc and the underlying resolver defect is tracked as its
  own task; neither mitigation makes case 4 work in this task) ·
  → mitigation: inline post-phase document_case4_gap, and
  seed_resolution_fallback_for_installed_projects
- **The task's stated verification asks for a "legacy mode (data branch
  declined)" test that the harness cannot express**: the decline branch needs
  `[[ -t 0 ]]` true and `tests/` has no pty/expect harness. Covered instead by a
  legacy-layout fixture plus T43's structural `declare -f` guard, which
  generalizes to *every* `setup_data_branch` early return. · severity: low
  (user-decided: the layout-fixture + structural-guard option was chosen over
  adding a pty harness or an env override) · → mitigation: none — the
  substitution and its rationale are recorded in §4 T42/T43.

### Planned mitigations
- timing: post-phase | name: announce_claudemd_append_on_upgrade | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: setup now appends a managed block to a project-owned CLAUDE.md it previously never touched, indistinguishably from a routine refresh | desc: update_claudemd_git_section announces the append-to-a-pre-existing-file case separately from create/refresh, naming what was added and how to keep the file hand-maintained; T41 asserts the wording
- timing: post-phase | name: document_case4_gap | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the "regenerated on every ait setup" claim is untrue for the failed-worktree-add path on installed projects | desc: one sentence in the aitasks_extension_points.md CLAUDE.md bullet naming the exception and why (install.sh:1335 deletes the seed/ fallback)
- timing: after | name: seed_resolution_fallback_for_installed_projects | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: medium | addresses: assemble_aitasks_instructions has no reachable seed when aitasks/ is a dangling symlink and seed/ was deleted at install, so no instruction surface can be generated | desc: give the resolver a third fallback (e.g. a packaged copy under .aitask-scripts/) so CLAUDE.md, AGENTS.md, .codex/ and .opencode/ all still generate; spawned rather than inlined because it reshapes a resolver shared by four surfaces

## Post-Implementation

See `task-workflow` **Step 9** for cleanup, archival, and merge. Current-branch
mode (profile `fast`): nothing to merge; Step 9 archives `t1612` and this plan.
