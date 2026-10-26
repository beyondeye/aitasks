---
Task: t2154_dash_parity_local_tests.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: run the Go engines suite under dash locally (t2154)

## Context

GitHub's `ubuntu-latest` runners use **dash** as `/bin/sh`; this dev box uses
bash. t2148's hosted-only LEAK came from that difference: `dash -c "sleep 300"`
forks `sleep`, while bash execs it. Every local run passed, and every hosted run
failed. t2154 is the "after" mitigation of t2148. The goal is a local entry point
that runs the Go suite under dash, so these differences show up before a push.

### Options evaluated (decision: docker, full suite)

- **bwrap, dash bound over `/bin/sh`** — rejected. This box has no dash binary.
  `/bin/sh` is a symlink (`/usr/bin/sh -> bash`), and a bind mount follows the
  symlink, so it would replace **bash** itself and break every bash-using test.
- **Static `go test -c` binaries run in bare `ubuntu:24.04`** (the t2148 recipe)
  — rejected as the default. The bare image has no git, python3, pytest or go,
  so `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` fails those tests, and without it they
  silently skip. It also covers only a package subset.
- **Chosen: the whole CI sequence (`./ci/preflight.sh` then `go test ./...`)
  in an `ubuntu:24.04` container shaped like the hosted runner**: dash
  `/bin/sh`, git from `ppa:git-core/ppa` (as runner images do), python3 3.12,
  pinned `pytest==8.4.2 pytest-xdist==3.8.0` (the CI pin), a non-root uid, and
  `--init`. The host's Go toolchain is mounted read-only (official Go builds are
  statically linked), so nothing is downloaded at run time.

### Prototype evidence (done during planning, in the scratchpad)

- Image build: about 30s, once. The full uncached suite in the container (`-count=1`): all 23 packages ok.
- `/bin/sh` → `/usr/bin/dash` inside the container.
- With Ubuntu's **stock** git 2.43, `internal/testmap/fixture` `TestHistory`
  fails: `%cI` prints `+00:00` where newer git prints `Z`. The PPA git (2.56,
  the same as the host and close to the hosted runners) passes. So the PPA is
  needed for fidelity. The test's dependence on the git version goes to Step 8b
  as an upstream finding; it is not fixed here.
- **False-pass hazard found:** the container shares the host `GOCACHE`. The
  test cache does not key on which `/bin/sh` a test exec'd, so a result cached
  from a bash run would replay as `ok (cached)`. Fix: the script always puts
  `-count=1` before the user's args, so an explicit `-count=N` still wins (Go's
  last-flag-wins rule).

## Implementation

### 1. New `goengines/ci/dashcheck.sh` (dev-tree only, like `benchci.sh`; never shipped)

Header comment in the style of `benchci.sh`/`preflight.sh`: purpose (t2148's
root cause), usage, output protocol, exit codes.

```
dashcheck.sh [--stress N] [--] [go test args...]   # default args: ./...
```

Output: progress goes to stderr. The **last stdout line** is the verdict:

| line | exit |
|---|---|
| `DASHCHECK:PASS` | 0 |
| `DASHCHECK:FAIL:<probe\|preflight\|suite>:<rc>` | 1 |
| `DASHCHECK:NOT_RUN:<reason>` | 3 — never 0. `no-docker`, `docker-unreachable`, `not-linux`, `modules-unavailable`, `image-build-failed` |
| usage error | 2 |

Flow:
1. Parse args. `--stress N` takes a positive integer, else usage. An optional `--`
   comes next, then the rest goes to `go test`, defaulting to `./...`.
2. `DOCKER="${AIT_DASHCHECK_DOCKER:-docker}"`, overridable so tests can make it
   absent. `command -v "$DOCKER"` fails → `NOT_RUN:no-docker`.
   `"$DOCKER" info >/dev/null` fails → `NOT_RUN:docker-unreachable`.
3. `cd` to the module (`$(dirname BASH_SOURCE)/..`). Read
   `go env GOHOSTOS GOROOT GOCACHE GOMODCACHE`. A GOHOSTOS other than `linux` →
   `NOT_RUN:not-linux`, because the host toolchain must run in a Linux container.
4. `go mod download` on the host, a no-op when cached. A failure gives
   `NOT_RUN:modules-unavailable`. The container then runs with `--network none`
   and `GOPROXY=off`.
5. Image: the Dockerfile text is held in a variable (the PPA git + python3 + pip
   pytest pins above). The tag is `aitasks-dashcheck:<first 12 hex of the
   sha256 of that text>`, so any content change means a new image.
   `image inspect` misses → `build -t <tag> -` with the Dockerfile on stdin (no
   context dir). A build failure gives `NOT_RUN:image-build-failed`.
6. Common `docker run` args (an array): `--rm --init --network none --user
   $(id -u):$(id -g)`. The mounts are `GOROOT:ro`, `GOMODCACHE:ro`, `GOCACHE`
   (rw) and the **module dir `:ro`** (the suite writes only to `t.TempDir()`,
   which the prototype confirmed), each at the same path, with `-w <module>`.
   The env is `HOME=/tmp/home`,
   `PATH=<GOROOT>/bin:/usr/local/sbin:...:/bin`, `GOROOT`, `GOCACHE`,
   `GOMODCACHE`, `GOTOOLCHAIN=local`, `GOPROXY=off`, `GOFLAGS=-mod=readonly`,
   `CGO_ENABLED=0` (the image has no C compiler) and
   `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` (as in CI). With `--stress N`, add
   `--cpus 1`.
7. **Probe** run: `sh -c 'readlink -f /bin/sh; go version'`. A nonzero exit, or
   a first line whose basename is not `dash`, gives `FAIL:probe:<rc>`, with a
   message naming the cause: the dash parity is not proven, or the host Go
   could not run in the container (for example a dynamically linked distro Go).
   This fails closed, because a check that claims dash parity must observe
   dash.
8. **Preflight** run: `./ci/preflight.sh`. A nonzero exit gives
   `FAIL:preflight:<rc>`, and the suite does not run (the CI ordering).
9. **Suite** run: `go test -count=1 "$@"`. With `--stress N`, the run goes
   through an inner wrapper that starts N `(while :; do :; done) &` loops
   (`--init` reaps them at exit) and then `exec`s `go test`. A nonzero exit
   gives `FAIL:suite:<rc>`, otherwise `PASS`.

All docker invocations take their exit status directly (`|| rc=$?`); container
output is never parsed for the verdict, except the probe's `/bin/sh`
identity line.

### 2. New `tests/test_goengines_dashcheck.sh` (stub-driven; needs no docker or Go)

The structure follows `tests/test_goengines_benchci.sh` (scratch cwd, the
`asserts.sh` helpers, a `Results:` footer, no subshell test bodies). A stub
`go` (canned `go env` / `mod download`) and a stub `docker` go on a scratch
`PATH` dir, plus `AIT_DASHCHECK_DOCKER=<stub>`. Each stub appends its argv, one
invocation per line, to a log. Env knobs pick each step's exit code and the
probe's `/bin/sh` path. Cases:
- the docker command is absent → `NOT_RUN:no-docker`, exit 3, no `PASS` in the
  output, and no `run` in the log;
- `info` fails → `NOT_RUN:docker-unreachable` (3);
- GOHOSTOS=darwin → `NOT_RUN:not-linux` (3);
- `mod download` fails → `NOT_RUN:modules-unavailable` (3);
- `build` fails (`image inspect` miss) → `NOT_RUN:image-build-failed` (3);
  when `image inspect` hits, no `build` is logged;
- the probe reports `/bin/bash` → `FAIL:probe:…` (1), and neither preflight nor
  suite is logged. A failing probe exit gives the same result;
- the preflight fails → `FAIL:preflight:…` (1), and the suite is not logged;
- the suite exits 2 → `FAIL:suite:2` (1);
- all steps ok → `DASHCHECK:PASS`, exit 0, and the suite argv contains
  `--init`, `--network none`, `--user`, the module mount ending in `:ro`,
  `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`, `-count=1` before the default `./...`,
  and no `--cpus`;
- user args `-run X ./internal/procsup/ -count=5`: `-count=1` comes first,
  then the user args in order, and no `./...`;
- `--stress 2` → `--cpus 1`, and the inner command starts 2 loops;
- `--stress 0`, `--stress x` or `--stress` without a value → exit 2;
- negative control: a scratch copy of the script with the `-count=1` insertion
  removed makes the "`-count=1` precedes" assertion fail. This proves the
  assertion has teeth. It runs against the copy only.

### 3. CI wiring (keeps the script from rotting; it is not a dash leg)

- `.github/workflows/goengines-check.yml`: a `dashcheck.sh tests` step in the
  `check` job right after `benchci.sh tests` (`working-directory: .`,
  `run: bash tests/test_goengines_dashcheck.sh`). Add
  `tests/test_goengines_dashcheck.sh` to both `paths` lists.
- `tests/test_release_workflow_goengines.py`: add the path to `CHECK_PATHS`,
  add it to the `test_check_job_runs_the_guards` guard list, and mention it in
  the module docstring's goengines-check bullet.

### 4. Docs

- `goengines/README.md` "Build, test, bench": a short "Dash parity (local)"
  paragraph covering why (hosted `/bin/sh` is dash), the command
  (`./ci/dashcheck.sh`, `--stress N`, pass-through args), the verdict line and
  exit codes, that NOT_RUN is never a pass, the image refresh
  (`docker rmi aitasks-dashcheck:<tag>`), and the remaining gaps (kernel,
  scheduling, host Go rather than the go.mod toolchain pin, `CGO_ENABLED=0`).
  Also add `ci/dashcheck.sh` to the Layout table if `ci/` is listed there (it
  is not today; leave it alone if absent).
- CLAUDE.md: **no change**. The task says to document it there only if it
  becomes part of the routine pre-push check, and it does not: it needs docker
  and is opt-in.

## Verification

1. `shellcheck goengines/ci/dashcheck.sh tests/test_goengines_dashcheck.sh`;
   `bash tests/test_goengines_dashcheck.sh`;
   `python3 -m unittest tests/test_release_workflow_goengines.py`;
   `bash tests/test_goengines_benchci.sh` (unchanged neighbour).
2. Real run: `goengines/ci/dashcheck.sh` → `DASHCHECK:PASS`, exit 0.
   `goengines/ci/dashcheck.sh --stress 2 -run 'TestSupervisorDeathHalts|TestHaltStartInterleavings' -count=20 ./internal/procsup/`
   → PASS.
3. **Negative control (the tool has teeth):** a scratch `git worktree` at
   `a06e4f5d8^` (the pre-t2148-fix tree), under the scratchpad, never touching
   the shared tree. Copy the new `dashcheck.sh` into its `goengines/ci/` and
   run `ci/dashcheck.sh ./internal/procsup/`. Expected: `DASHCHECK:FAIL:suite:1`
   with `LEAK:TestHaltStartInterleavings|…:sleep`. The same tree under plain
   local `go test -count=1 ./internal/procsup/` (bash `/bin/sh`) passes, which
   is the gap closed. Remove the worktree afterwards.
4. NOT_RUN for real: `AIT_DASHCHECK_DOCKER=nope goengines/ci/dashcheck.sh` →
   `DASHCHECK:NOT_RUN:no-docker`, exit 3.

## Step 9

Commit the code as `test: … (t2154)` and the plan separately (current-branch
mode, no merge). Archive via task-workflow Step 9.

## Risk

### Code-health risk: low
- A new standalone dev script and its stub test, plus one CI step and a
  guard-list entry in `test_release_workflow_goengines.py`. No production or
  engine code changes. The new CI step needs neither docker nor Go (stubs), so
  it cannot turn the hosted `check` job flaky · severity: low · → mitigation:
  none needed

### Goal-achievement risk: low
- The container matches the hosted runner's shell and tools, but not its
  kernel, scheduling, toolchain pin (it uses the host Go, not go.mod's
  `toolchain`) or `CGO_ENABLED`. A hosted-only failure on one of those axes can
  still slip through. This is inherent and documented in the README, and
  `--stress` narrows the scheduling side · severity: low · → mitigation: none
  needed
- The host toolchain must be a Linux, statically linked Go (official builds
  are). Otherwise the probe fails loudly as `FAIL:probe`; it never passes ·
  severity: low · → mitigation: none needed
- The image's PPA git is frozen at build time while the hosted runners' git
  moves on. A git-version-dependent test (like `TestHistory`) can diverge until
  the image is rebuilt. The README documents the refresh · severity: low ·
  → mitigation: none needed
