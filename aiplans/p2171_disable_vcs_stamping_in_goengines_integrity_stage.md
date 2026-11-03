---
Task: t2171_disable_vcs_stamping_in_goengines_integrity_stage.md
Base branch: main
Output branch: main
---

# t2171 — Disable VCS stamping in goengines_integrity.sh's scratch-copy go commands

## Context

`.github/scripts/goengines_integrity.sh check` copies `goengines/` into a
`mktemp -d` scratch dir and runs every go command there through `run_go`. That
copy is a bare tree, never a repository, yet `go build` and package-mode
`go list` run under the default `-buildvcs=auto`. They walk up from the scratch
dir looking for a VCS root. A concurrent Codex sandbox creates an empty
`/tmp/.git` for each sandboxed command. When one exists, go finds it, runs
`git status`, and fails with `error obtaining VCS status: exit status 128`.
`check` then reports bogus `INTEGRITY_FAIL:independent-build:` /
`INTEGRITY_FAIL:closure:` lines. aitasks_go#t56 (archived) fixed the private
twin (`promote/gocmd.go`, which appends `-buildvcs=false` to every stage
command's `GOFLAGS`). This task fixes the public twin.

**Measured on this host before planning** (scratch fixture, `TMPDIR` under an
empty ancestor `.git`, consistent toolchain):

| call (script line) | under empty ancestor `.git` | with `-buildvcs=false` |
|---|---|---|
| `go list -m all` (319) | ok | — |
| `go list -e -deps -f …` private-deps (328) | rc 0, but the main package carries `Error: error obtaining VCS status` (swallowed by `-e`) | clean |
| `go mod tidy -diff` (345) | ok | ok |
| `go build ./...` per target (349) | **fails** ×4 targets | ok |
| `go vet ./...` (353) | ok | ok |
| `go list -m` (369) | ok | ok |
| `go list -deps -f …` closure (378) | **fails** ×4 targets | ok |

`check` as a whole: `INTEGRITY_OK` with a plain `TMPDIR`. Under the empty
`.git` it gives 8 `INTEGRITY_FAIL` lines (4 build, 4 closure) and rc 1.

**Host caveat (not part of this task):** this Bash tool's shell resolves
`/usr/bin/go` (Arch, `go1.27.3-X:nodwarf5`) on `PATH` while `GOROOT` points at
mise's `go1.27.3`. Every compile then fails with a `compile: version … does not
match go tool version` error. All verification below runs with
`PATH="$GOROOT/bin:$PATH"`. Baseline: `tests/test_goengines_export_integrity.sh`
passes 181/181 that way.

## Approach

Add `-buildvcs=false` to the per-call `GOFLAGS` of the three package-loading
calls: `go build` and the two package-mode `go list -deps`. These are the
commands that stamp main packages under `auto`. Leave `INDEPENDENT_ENV`
unchanged. Putting the flag there would have no effect on these calls, because
each one sets its own `GOFLAGS=` after it and env's last assignment wins. Leave
`vet`, `tidy` and `list -m` unchanged too: they never stamp (measured above).
The flag is safe there anyway, but it would be noise.

No check reads VCS build info: closure reads ImportPath/Module, private-deps
reads Imports, and build checks only success. So the verdict is unchanged
whenever stamping did not error.

## Steps

### 1. Regression test first (red)

**Observation channel.** Exit status and stdout cannot see the private-deps
listing's stamping: `go list -e` swallows the error into the main package's
`.Error`, and the template never prints it. A user review rejected the first
draft for exactly this gap: with only build and closure fixed, `check` still
said `INTEGRITY_OK`. Making private-deps fail on `.Error` would be wrong,
because `-e` is there so that unresolvable (private) imports are still listed.

Go performs VCS stamping only by executing `git`. So the test puts a logging
`git` stub first on `PATH`. The stub appends its args and its parent's command
line to a log, then execs the real git. "`check` ran no git at all" then covers
all three calls, the swallowed one included. `check` itself never runs git
(`tree_files` is drift-only). The fixtures are stdlib-only with local replaces,
and `GOPROXY` has no `direct`, so module fetching cannot run git either.

`tests/test_goengines_export_integrity.sh`: add section `9f` after `9d`
(before `10.`):

```bash
# --- 9f. an ancestor .git that is no repository reaches no check ------------------
# A sandbox can leave an empty .git in an ancestor of TMPDIR (Codex's bwrap
# creates /tmp/.git for each sandboxed command). Under -buildvcs=auto, go build
# and go list -deps in the scratch copy walk up to it and run git status there:
# go build and the closure listing fail with "error obtaining VCS status", and
# the private-deps listing's -e swallows the same error (t2171). Go stamps only
# by running git, so a logging git stub sees every stamping attempt, including
# the one no exit status or output shows. GIT_CEILING_DIRECTORIES keeps git's
# own discovery from reaching a real repository above $TMP.
(
    d="$(mkfix vcs)"
    rm -rf "$d/.git" # the real goengines/ has no .git of its own: its copy must not either
    sandbox="$TMP/vcs/sandbox"
    stub="$TMP/vcs/bin"
    gitlog="$TMP/vcs/git.log"
    realgit="$(command -v git)"
    mkdir -p "$sandbox/.git" "$sandbox/tmp" "$stub"
    cat >"$stub/git" <<EOF
#!/usr/bin/env bash
printf '%s | parent: %s\n' "\$*" "\$(ps -o args= -p "\$PPID" 2>/dev/null)" >>"$gitlog"
exec "$realgit" "\$@"
EOF
    chmod +x "$stub/git"
    probe="$sandbox/tmp/probe"
    cp -R "$d/." "$probe"
    under_sandbox() { (cd "$probe" && PATH="$stub:$PATH" GIT_CEILING_DIRECTORIES="$TMP" CGO_ENABLED=0 "$@" 2>&1); }

    : >"$gitlog"
    rc=0; out="$(under_sandbox env GOFLAGS=-mod=mod go build ./...)" || rc=$?
    assert_eq "control: go build under the empty ancestor .git fails" "failed" "$([[ "$rc" -ne 0 ]] && echo failed || echo passed)"
    assert_contains "control: … on VCS stamping" "error obtaining VCS status" "$out"
    assert_contains "control: … after go ran git status" "status" "$(cat "$gitlog")"

    : >"$gitlog"
    rc=0; out="$(under_sandbox env GOFLAGS=-mod=readonly go list -e -deps -f '{{.ImportPath}}' ./...)" || rc=$?
    assert_eq "control: the private-deps form (go list -e -deps) exits 0 there" "0" "$rc"
    assert_contains "control: … yet it ran git status, which only the git log shows" "status" "$(cat "$gitlog")"
    rm -rf "$probe"

    : >"$gitlog"
    run check "$d" TMPDIR="$sandbox/tmp" GIT_CEILING_DIRECTORIES="$TMP" PATH="$stub:$PATH"
    assert_eq "an empty ancestor .git does not fail check" "0" "$RC"
    assert_contains "… INTEGRITY_OK" "INTEGRITY_OK" "$OUT"
    assert_not_contains "… and no check reports a VCS stamping error" "VCS status" "$OUT"
    assert_eq "… and no go command in check ran git (the -e listing included)" "" "$(cat "$gitlog")"
)
```

Notes:
- `rm -rf "$d/.git"`: `mkfix` git-inits the fixture, and `cp -R "$dir/."`
  would copy that `.git` into the scratch dir, where go would find it first and
  never reach the ancestor. The real `goengines/` has no `.git` of its own.
- The ceiling is `$TMP` (the parent of `$TMP/vcs`). git runs with
  `cwd=$sandbox`, and the ceiling keeps it from going above `$TMP` into
  whatever repository may lie outside it. The controls prove the condition is
  triggered and that the git log sees the `-e` listing, so the case cannot pass
  vacuously.
- The logged `parent:` command line makes a failure name the go command that
  stamped. `ps -o args= -p` works on both Linux and macOS; CI runs this file on
  `ubuntu-latest`.
- Run `bash tests/test_goengines_export_integrity.sh` before step 2. Expect the
  four post-control 9f assertions to fail (red) while all five controls pass.
  Record the counts.
- **Contingency:** if after step 2 the git log is still non-empty because of a
  go command outside the three (e.g. `vet`), that command stamps by
  definition. Add `-buildvcs=false` to it too, and note this in the plan's
  Final Implementation Notes.

### 2. Fix (green)

`.github/scripts/goengines_integrity.sh`:
- line 328 (private-deps per target):
  `GOFLAGS=-mod=readonly` → `GOFLAGS="-mod=readonly -buildvcs=false"`
- line 349 (independent-build per target):
  `GOFLAGS=-mod=mod` → `GOFLAGS="-mod=mod -buildvcs=false"`
- line 378 (closure per target/bin):
  `GOFLAGS=-mod=mod` → `GOFLAGS="-mod=mod -buildvcs=false"`
- Comment above `run_go` (≈ line 234): add the rule. The scratch copy is a bare
  tree, never a repository, so VCS stamping there is always wrong, and under
  `-buildvcs=auto` a stray ancestor `.git` (a sandbox's transient `/tmp/.git`)
  fails `go build` / package-mode `go list` with `error obtaining VCS status`.
  So every such call carries `-buildvcs=false` in its own `GOFLAGS`, not in
  `INDEPENDENT_ENV`, whose cleared `GOFLAGS=` a per-call value replaces.
- Header bullet list (lines 53-56): one clause noting `-buildvcs=false` on the
  build / `go list -deps` calls.

`run_go` passes `"$@"` to `env` as separate words, so a quoted
`GOFLAGS="-mod=mod -buildvcs=false"` reaches go as one space-separated
`GOFLAGS` value. That is the documented format.

### 3. Doc

`aidocs/framework/go_engine.md` (the isolated-environment bullet list, ≈ lines
253-259): add one bullet, in current-state wording:
"`-buildvcs=false` on every `go build` and `go list -deps`: the scratch copy is
never a repository, and a stray ancestor `.git` (a sandbox's transient
`/tmp/.git`) would otherwise fail them with `error obtaining VCS status`."

## Verification

All commands are run with `PATH="$GOROOT/bin:$PATH"` (host caveat above).

1. Red proof (step 1): the four non-control 9f assertions fail and the five
   controls pass. The other 181 assertions are unchanged.
2. Green: `bash tests/test_goengines_export_integrity.sh` → `ALL TESTS PASSED`
   (181 + 9 new).
3. **Per-site mutants, run isolated** (never edit the shared tree). Build a
   scratch project copy laid out like the repo: `tests/` (the test file +
   `tests/lib/`), `.github/scripts/` (the mutant script) and
   `goengines/build.sh`. The test derives `PROJECT_DIR` from its own location,
   so it then exercises the mutant. Each mutant removes `-buildvcs=false` from
   exactly one site:

   | mutant | expected 9f result |
   |---|---|
   | M-private (line 328 only, the reviewer's scenario) | red **only** on "no go command in check ran git"; rc 0, `INTEGRITY_OK` |
   | M-build (line 349 only) | red on rc / `INTEGRITY_OK` / VCS-error / git-log |
   | M-closure (line 378 only) | red on rc / `INTEGRITY_OK` / VCS-error / git-log |

   Every mutant must go red on 9f and nowhere else. Record the counts in Final
   Implementation Notes.
4. Scratch repro: `bash <scratchpad>/repro.sh .github/scripts/goengines_integrity.sh <scratch>`
   → `check` under the empty `.git` gives `INTEGRITY_OK`, rc 0.
5. `shellcheck .github/scripts/goengines_integrity.sh tests/test_goengines_export_integrity.sh`:
   no new findings compared with HEAD.
6. Real tree: `.github/scripts/goengines_integrity.sh check` (export mode,
   `goengines/EXPORT.txt` present) → `INTEGRITY_OK`, with both a plain `TMPDIR`
   and a `TMPDIR` under a private empty `.git`. This needs the module proxy for
   the real deps; if the network is unavailable, report it as not run.

## Step 9 (Post-Implementation)

Commit the code (`bug: … (t2171)`) by naming the three paths only. The plan is
committed through `./.aitask-scripts/aitask_task_commit.sh`. Archival follows
the standard Step 9 flow. No cross-repo note: the origin aitasks_go#t56 is
archived, and the private twin is already fixed.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes

- **Actual work done:** All three plan steps were done as written.
  - `-buildvcs=false` was added to the per-call `GOFLAGS` of the three
    package-loading calls in `.github/scripts/goengines_integrity.sh`: the
    private-deps `go list -e -deps`, the per-target `go build`, and the closure
    `go list -deps`.
  - The rule is explained in a comment above `run_go` and in one header clause.
  - Regression section §9f was added to
    `tests/test_goengines_export_integrity.sh`, with the logging `git` stub, 5
    controls and 4 assertions.
  - One bullet was added to the isolated-environment list in
    `aidocs/framework/go_engine.md`.
- **Deviations from plan:** None. The plan's contingency (a go command outside
  the three running git) did not fire. Before the fix, the red-run git log
  named exactly 12 `git status --porcelain` invocations, one per target:
  4 × `go list -e -deps` (private-deps), 4 × `go build`, and 4 ×
  `go list -deps` (closure). `vet`, `tidy` and `list -m` never ran git.
- **Issues encountered:** In the agent's Bash shell, `PATH` resolves
  `/usr/bin/go` (Arch, `go1.27.3-X:nodwarf5`) while `GOROOT` points at mise's
  `go1.27.3`. So every compile fails with
  `compile: version "go1.27.3" does not match go tool version "go1.27.3-X:nodwarf5"`.
  This is a host environment problem, not a repository defect. All
  verification ran with `PATH="$GOROOT/bin:$PATH"`.
- **Key decisions:**
  - The flag is not in `INDEPENDENT_ENV`, because a per-call `GOFLAGS=`
    replaces the cleared value there.
  - It is not on `vet`, `tidy` or `list -m`, which never stamp (confirmed by
    the git log).
  - The test observes at the process boundary, through the `git` stub. A user
    review of the first plan showed that exit/output assertions cannot see the
    `-e` listing's swallowed error.
- **Verification evidence:**
  - Red (test added, script unfixed): 186 passed, 4 failed (the 4 non-control
    §9f assertions); all 5 controls passed.
  - Green: 190 passed, 0 failed.
  - Isolated per-site mutants, each built in a scratch project copy with
    exactly one `-buildvcs=false` removed (2 of 3 sites left):

    | mutant | result |
    |---|---|
    | M-private (line 339) | 189/1: red **only** on "no go command in check ran git"; the logged parent is `go list -e -deps …` |
    | M-build (line 360) | 186/4: rc, `INTEGRITY_OK`, VCS-error and git-log assertions red; parent `go build ./...` |
    | M-closure (line 389) | 186/4: same four red; parent `go list -deps -f {{if not .Standard}}…` |

    No mutant reddened anything outside §9f.
  - Real `goengines/` tree (export mode), `TMPDIR` under a private empty `.git`:
    HEAD script → 8 `INTEGRITY_FAIL` (4 independent-build, 4 closure), rc 1.
    Fixed script → `INTEGRITY_OK`, rc 0. Both versions give `INTEGRITY_OK`
    with a plain `TMPDIR`.
  - shellcheck: the script has 0 findings both at HEAD and now. The test file
    has 2 at both, the pre-existing SC1091 "not following" notes.
- **Upstream defects identified:** None
