---
Task: t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md
Base branch: main
Output branch: main
---

# t2226 — stop fixtures copying `__pycache__`; make test_goengines_build failures visible

## Context

`tests/lib/sync_fixture.sh:96` does `cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts`
and then `git add -A`. In a working checkout that copies (and commits into the fixture)
21 gitignored `__pycache__` dirs, about 12 MB of the tree's 24 MB.
`test_sync_deferral_and_quarantine.sh` builds 48 fixtures and grows `/tmp` by about 2 GB
(about 1 GB from a clean tree). That exhausts the per-user `/tmp` quota (`usrquota`), truncates
logs and fails the sync tests under parallel load (t2215 sweep). The copied caches are
useless anyway: `cp -r` gives the `.py` files fresh mtimes, so Python treats every copied
`.pyc` as stale and recompiles it.

`tests/test_goengines_build.sh` runs `out="$("$BUILD" … 2>/dev/null)"` at five sites under
`set -euo pipefail`. When the build fails, the script exits 1 and prints nothing. This is
reproduced on this machine: rc=1 and an empty log, caused by the local
`go1.27.3-X:nodwarf5` toolchain mismatch.

A grep found 22 recursive `cp -r "$PROJECT_DIR/.aitask-scripts[/sub]"` copies across 17
bash test files: 14 copy the whole tree and 8 copy only `lib/` or another package dir. The
Python fixtures (`test_concern_body_display_contract.py`, `test_trail_discovery_cache.py`)
already pass `ignore_patterns("__pycache__")`. `test_install_engine_binary.sh` copies from a
work tree (`$T`), not from PROJECT_DIR, so it is out of scope. None of the 17 files is dirty
in the shared worktree.

## Implementation

### 1. New helper `tests/lib/framework_copy.sh`

```bash
# copy_framework_tree <src_dir> <dst_dir>: copy the CONTENTS of src_dir into dst_dir
# (created if missing) without Python bytecode caches (__pycache__/, *.pyc).
copy_framework_tree() {
    local src="$1" dst="$2" st
    [[ -d "$src" ]] || { echo "copy_framework_tree: not a directory: $src" >&2; return 1; }
    mkdir -p "$dst" || return 1
    tar -C "$src" --exclude='__pycache__' --exclude='*.pyc' -cf - . | tar -C "$dst" -xmf -
    st=("${PIPESTATUS[@]}")
    [[ "${st[0]}" -eq 0 && "${st[1]}" -eq 0 ]]
}
```
- Uses tar, not `git ls-files`: an in-flight, untracked module
  (`lib/relation_candidates_contract.py` exists right now) must still reach fixtures.
- GNU tar and bsdtar both treat exclusions as unanchored, and both support `-C`, `-m` and `-`.
- `-m` keeps the fresh mtimes `cp -r` produced. Mode bits are kept, so executables stay
  executable.
- Checks both sides of the pipe via `PIPESTATUS`; no `pipefail` dependency (hub_shell_bash_gotchas).
- The header comment explains why the helper exists (t2226, the quota) and states the
  copy-contents semantics.

### 2. Convert every site (one pattern)

`cp -r "$PROJECT_DIR/.aitask-scripts[/X]" <dst>` → `copy_framework_tree "$PROJECT_DIR/.aitask-scripts[/X]" <explicit dst dir>`,
with the destination always written out as the full directory (for example `"$STAGING/.aitask-scripts"`
for `cp -r … "$STAGING/"`). I checked every destination: each is fresh before its copy,
except `test_task_data_writer_guard.sh:144`, whose `lib/.` → existing-dir form already
has copy-contents semantics. Each converted file sources the helper next to its existing
`asserts.sh` source. `sync_fixture.sh` sources it itself, so its ~20 consumers need no change.

Files: `tests/lib/sync_fixture.sh`, `test_sync.sh` (3), `test_task_git.sh` (2),
`test_aitask_merge_boardgroup.sh`, `test_sync_branch_mode_automerge.sh`, `test_task_push.sh`,
`test_note_cross_repo.sh`, `test_ait_git_gateway_pull.sh`, `test_artifact_fetch_exclusion.sh`,
`test_install_create_data_dirs.sh`, `test_sitrep_corpus.sh`, plus the lib/package copies in
`test_contribute.sh`, `test_task_data_writer_guard.sh`, `test_brainstorm_context_helper.sh` (3),
`test_setup_hooks_only.sh`, `test_run_project_command.sh` (3), `test_data_branch_setup.sh`.

**The `cp -R` + prune sites (nine tracked files, also converted).** These files already do
`cp -R "$PROJECT_DIR/.aitask-scripts" <dst>` followed by
`find <dst> -type d -name __pycache__ -prune -exec rm -rf {} +`:
`test_data_branch_migration.sh`, `test_crew_groups.sh`, `test_crew_addwork_output_instructions.sh`,
`test_revert_analyze.sh`, `test_crew_report.sh`, `test_crew_status.sh`, `test_crew_cleanup.sh`,
`test_crew_runner.sh`, `test_crew_branch_delete_bounded.sh`. Each `cp -R` + `find` pair
becomes one `copy_framework_tree` call. The destinations are fresh and the following
`chmod +x` lines stay. This gives one mechanism instead of two, removes the transient
write-then-delete, and the guard in 4.3 holds with no allowlist. None of the nine is dirty.
The inventory now comes from the guard's own regex (`cp -[flags incl. r/R/a]`), not the
lowercase-only grep that missed these sites, so the conversion list and the guard cannot
disagree. Step 4.3 runs against the same regex.

**Foreign untracked file `tests/test_setup_relations.sh:43`** (`cp -R … "$t/"`, no
prune). It was created by another live session, probably t1981_3 (relations,
Implementing), but that is not confirmed. **This task does not touch it.** At Step 8,
re-check its state:
- still untracked → leave it. The guard (4.3) selects tracked files only, so it stays
  green. After my
  commit, send a note through `/aitask-note` (the recipient is resolved by the skill, with
  t1981_3 as the likely owner, hedged). The note says the new
  `tests/test_framework_copy.sh` guard will reject line 43 once the file is committed, and
  that `copy_framework_tree "$PROJECT_DIR/.aitask-scripts" "$t/.aitask-scripts"` from
  `tests/lib/framework_copy.sh` is the replacement.
- already committed by its owner and clean → the guard would fail on it, so convert that
  one line in this commit and still send the note, recording that its line changed.

### 3. `tests/test_goengines_build.sh`: a failed build is a named FAIL

Add `run_build <desc> <build.sh> <args…>`. It sets `out` from stdout and sends stderr to
`$TMP/build.err`. On a non-zero exit it calls `assert_record_fail`, prints
`FAIL: <desc>: build.sh exited <rc>` and the indented stderr, prints the `Results:` line and
exits 1. The run has to stop there because later cases execute the binaries, and under
errexit that would die silently again. Replace all five
`out="$("$BUILD"|"$fake/goengines/build.sh" … 2>/dev/null)"` sites. On success the output
stays quiet, as it is today.

**Deterministic self-check of the failure report, with no broken Go needed:**
- Seam: `BUILD="${AIT_TEST_GOENGINES_BUILD:-$PROJECT_DIR/goengines/build.sh}"`. It is
  test-only and read only by this file.
- New final section `# --- 7. a failing build is a named FAIL`, skipped when
  `AIT_TEST_GOENGINES_BUILD` is set so it cannot recurse. It writes a stub to `$TMP`
  that prints `STUB_STDERR_MARKER: compile: version mismatch` to stderr and exits 1. It
  then runs the file itself, capturing rc and combined output, with
  `AIT_TEST_GOENGINES_BUILD=<stub> bash "$SELF"`. `SELF` is set at the top as
  `SELF="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"`, right after `SCRIPT_DIR` is resolved
  and **before** `enter_scratch_cwd`. `BASH_SOURCE[0]` is relative under the documented
  `bash tests/test_goengines_build.sh`, and would no longer resolve after the scratch
  cd.
- It asserts: rc ≠ 0; the output contains `FAIL: host build` (case 1's desc), contains
  the marker (the original stderr got through), and contains `Results:` with
  `1 failed`.
- The inner run passes the outer `command -v go` gate, since the self-check only runs
  where the outer run did, and it stops at case 1. That makes it fast and uses the real
  top-level `set -e` shape that hid the failure in the first place.

### 4. Regression test `tests/test_framework_copy.sh` (new, file-backed counters not needed: no subshell bodies)

1. **Helper:** a synthetic src with `__pycache__/` at top level and nested, a stray
   top-level `x.pyc`, an executable `a.sh`, a dotfile and a nested `.py`. Copy into a
   non-existent dst and assert no `__pycache__`/`*.pyc` remain, every kept file is present,
   the exec bit is kept and the dst was created. Copy into an existing dir and assert the
   contents merge with no nesting. A missing src returns non-zero.
2. **sync_fixture integration:** build a synthetic PROJECT_DIR (the real `ait`, plus
   `.aitask-scripts` copied by the helper, plus planted `__pycache__/x.cpython.pyc` in
   the root, `lib/` and `board/`). Source `sync_fixture.sh` with that PROJECT_DIR and run
   `setup_repo`. Assert that the fixture's `.aitask-scripts` has no `__pycache__` on disk and
   that `git ls-tree -r HEAD` has no `__pycache__`/`.pyc`. Planting the caches makes the
   check meaningful on a clean CI checkout, which has none.
3. **Static guard, tracked files only.** No **tracked** `tests/*.sh` or `tests/lib/*.sh`
   file may recursively `cp` from `PROJECT_DIR/.aitask-scripts`. Candidates come from
   `git -C "$PROJECT_DIR" ls-files -z -- ':(glob)tests/*.sh' ':(glob)tests/lib/*.sh'`, and the
   working-tree contents of those paths are scanned. Untracked files belong to whichever
   session is writing them and are outside the contract until committed. That matches the
   ownership policy in Step 2, so the foreign `tests/test_setup_relations.sh` does not fail
   this guard while it stays untracked, and the note tells its owner before they commit.
   It fails closed: if `git ls-files` exits non-zero or the candidate list is empty, that
   is a FAIL, never a vacuous pass. The regex is assembled from fragments so the guard does
   not match itself (scanner-safe fixture). The check uses ERE over `cp -[flags with r/R/a]`
   followed by `PROJECT_DIR}?/.aitask-scripts` on the same line, and reports every hit
   with file:line.

### Post-phase (risk mitigations)

- **affected_suite_sweep:** after steps 1–4, run every converted test file and every
  `sync_fixture.sh` consumer (`grep -l sync_fixture.sh tests/*.sh`) at `xargs -P2`,
  logging each to the scratchpad. Bucket each file as pass, fail or refused. Every
  failing file is re-run on HEAD in a helper-only detached worktree (`git worktree add
  --detach` into the scratchpad, removed afterwards), and the failing assertion
  descriptions are compared, not the exit codes. A failure counts as this change's only
  when it is absent on HEAD. Any such failure is fixed before Step 8.

## Verification

- **Red, before the fix:** `bash tests/test_goengines_build.sh` → rc=1, empty log (already
  observed). After the fix it shows a named `FAIL:` with the go version-mismatch stderr and a
  `Results:` line. Where Go works, cases 1–6 pass and section 7 proves the failure
  report on its own. Pre-fix control for section 7: the scratchpad copy of the
  test with the old `2>/dev/null` capture and the seam kept. Section 7 must FAIL there,
  because the inner output has no `FAIL:` and no `Results:`. Run the fixed test through the
  documented relative invocation (`bash tests/test_goengines_build.sh` from the repo root)
  and also by absolute path from another cwd. Section 7 must reach the stub both ways:
  its marker appears in the inner output and there is no `No such file`.
- Guard file selection: with the foreign untracked `tests/test_setup_relations.sh` present,
  `test_framework_copy.sh` 4.3 passes. In the scratch mirror, a **tracked** file with an
  unconverted `cp -R` fails it, naming file:line.
- **Pre-fix control for test 4.2 / 4.3:** in the scratchpad, build a mirror project
  (`ait` and `.aitask-scripts` symlinked, `tests/` copied) whose `sync_fixture.sh` has the old
  `cp -r` line restored. `test_framework_copy.sh` must FAIL there (both the integration and
  guard checks), and PASS in the real tree. No `git restore` or stash is used in the shared
  worktree.
- **Size evidence:** `du -s` of one `setup_repo` fixture before (scratch mirror) and after.
  Expect a cut of about 12 MB on disk, plus the matching git objects.
- **Affected-suite sweep:** see the Post-phase step `affected_suite_sweep`.
- `shellcheck tests/lib/framework_copy.sh tests/test_framework_copy.sh`; `bash tests/test_cd_guard_lint.sh`.

## Step 9

Post-implementation: commit the code (`bug: … (t2226)`), commit the plan through
`aitask_task_commit.sh`, then archive per the Step 9 workflow.

## Risk

### Code-health risk: low
- Mechanical conversion across 26 test files could change one site's copy semantics
  (nest vs contents, mtime, mode) and break that test silently or loudly. · severity: low ·
  → mitigation: inline post-phase affected_suite_sweep
- `tar` exclusion behaviour differs between GNU tar and bsdtar (macOS). · severity: low · → mitigation: macos_tar_exclusion_check

### Goal-achievement risk: low
- None identified. The root cause is measured (the caches account for the whole real-vs-clean
  difference) and both defects named in the task are addressed directly.

Reassessed after the inline post-phase was added: both levels stay low. The sweep only
adds verification and changes no code path.

### Planned mitigations
- timing: post-phase | name: affected_suite_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: mechanical conversion changes a site's copy semantics | desc: Run every converted and sync_fixture-consuming test, attributing failures against HEAD per assertion
- timing: after | name: macos_tar_exclusion_check | type: test | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: GNU tar vs bsdtar exclusion semantics | desc: Run tests/test_framework_copy.sh on macOS to confirm bsdtar's unanchored --exclude drops nested __pycache__ and *.pyc

## Post-Review Changes

### Change Request 1 (2026-11-08 00:20)
- **Requested by user:** (1) the guard used newline-delimited `git ls-files`, so
  git's C-quoting of unusual names (e.g. `tests/test_café.sh`) made line 135 skip
  the file silently, contrary to the plan's `-z`; (2) a redundant
  `find … __pycache__ -prune` survived in `test_brainstorm_context_helper.sh:39`
  (the conversion script matched only the `-type d -name` argument order).
- **Changes made:** section 3 now goes through `guard_hits <root>`. It runs
  `git ls-files -z` into a temp file and reads it with `read -d ''`; it returns 2
  on an ls-files failure or an empty enumeration. Added synthetic-repo checks:
  a tracked `tests/test_café.sh` is flagged by file:line, an untracked file is
  ignored, a clean tracked file is not flagged, and an empty repo refuses with 2.
  Pre-fix control (the newline enumeration in a scratch copy) fails exactly the
  café check (33/34). Removed the leftover `find`; grepped every converted file
  for prune lines next to a copy, and none remain. test_framework_copy 34/34;
  test_brainstorm_context_helper passes.
- **Files affected:** tests/test_framework_copy.sh, tests/test_brainstorm_context_helper.sh

### Change Request 2 (2026-11-08 00:35)
- **Requested by user:** `guard_hits` spliced each raw filename into
  `sed "s|^|$f:|"`. A tracked `tests/test_pipe|name.sh` or a name with a
  newline broke the expression, `|| true` swallowed the sed error, and the
  violation read as a clean scan.
- **Changes made:** the prefix is printed literally (`printf '%s:%s\n' "$f"`
  per grep line). A grep exit >= 2 (the file could not be scanned) now makes
  `guard_hits` return 2 and name the file, instead of being swallowed. Added
  checks: a tracked `|` name and a newline name are each flagged by line, the
  count of reported copies is 3, and an unreadable tracked file (chmod 000,
  skipped as root) fails with rc 2 naming it. Pre-fix control (the sed prefix
  restored in a scratch copy): 5 of the new checks fail (35/40). Real tree:
  40/40.
- **Files affected:** tests/test_framework_copy.sh

## Final Implementation Notes
- **Actual work done:** Added `tests/lib/framework_copy.sh` (`copy_framework_tree`:
  tar-based, excludes `__pycache__`/`*.pyc`, copies contents into dst, `-m` for
  cp-like mtimes, PIPESTATUS-checked). Converted 26 files: `tests/lib/sync_fixture.sh`,
  14 full-tree and 8 lib/package `cp -r` sites, and 9 `cp -R` + `find -prune`
  pairs (crew tests, data_branch_migration, revert_analyze). Made
  `test_goengines_build.sh` report a failed build as a named FAIL with stderr and
  a Results line (`run_build`), plus a self-check that re-runs the file against a
  failing stub. Added `tests/test_framework_copy.sh` (40 checks: helper contract,
  setup_repo on a cache-planted synthetic project, guard over tracked tests with
  synthetic-repo checks of the guard itself).
- **Deviations from plan:** (1) The goengines self-check is section **0** (before
  case 1), not section 7. In the planned position it only ran after a successful
  real build, so it could never run on a host with a broken toolchain, this one
  included (the go binary itself is built `X:nodwarf5`; no env override fixes
  it). It now runs wherever `go` exists. (2) The guard is a `guard_hits <root>`
  function, so it can be tested against synthetic repositories (post-review
  CR1/CR2).
- **Issues encountered:** The first inventory grep matched only lowercase `cp -r`
  and missed the 9 `cp -R` sites (caught at plan review; the inventory now uses
  the guard's own regex). The conversion script matched one `find` argument
  order and left a redundant prune in test_brainstorm_context_helper.sh (CR1).
  The guard's first version mishandled unusual filenames (CR1: C-quoting without
  -z; CR2: the sed-spliced prefix plus `|| true`). Each fix has a pre-fix control
  run in a scratchpad mirror.
- **Key decisions:** tar exclusion rather than `git ls-files` (untracked in-flight
  modules must still reach fixtures). The guard selects tracked files only
  (untracked files belong to their writing session). Foreign untracked
  `tests/test_setup_relations.sh:43` (`cp -R`, no prune) was still untracked at
  commit time and left untouched; a note goes to its likely owner.
- **Evidence:** a sync fixture is 22 MB instead of 46 MB (`.aitask-scripts` 12 MB
  instead of 24 MB, 0 cache dirs instead of 21); `test_sync_deferral_and_quarantine`
  passes in 61s. Affected-suite sweep (post-phase `affected_suite_sweep`): 40/40
  files pass at -P2, no `Disk quota` lines, so no HEAD attribution was needed.
  `test_goengines_build.sh` still exits 1 on this host, now as a named FAIL with
  the compile-mismatch stderr (environmental, as the task notes).
- **Upstream defects identified:** None
