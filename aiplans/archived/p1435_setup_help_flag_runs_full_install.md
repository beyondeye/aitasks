---
Task: t1435_setup_help_flag_runs_full_install.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1435 — `ait setup --help` must print help, not run the full install

## Context

`ait setup` has **no `--help` / `-h` handler**. In `aitask_setup.sh`'s `main()`
flag loop (`:3703-3712`) the `*)` catch-all swallows `--help` into `args`, so
the flag falls through and the **full guided install runs**: package-manager
installs, git init, orphan-branch setup, venv creation, global shim install,
framework commits. A user who types `ait setup --help` to find out what the
command does triggers exactly the side effects they were trying to understand
first. This contradicts the dispatcher's own `ait:105` advice ("Run
`ait <command> --help` for more information on a command").

Exploration found the **same failure mode on a second surface**: the global
shim `packaging/shim/ait:22` branches on `"${1:-}" == "setup"` alone, so
outside an aitasks project `ait setup --help` downloads `install.sh` and
installs the framework into `$PWD` — non-interactively it does not even ask.
The user chose to fix both surfaces (script + shim guard).

Outcome — **the two entry paths get different, deliberately asymmetric
contracts**, because the shim runs where the framework does not exist:

| Path | Contract |
|---|---|
| In a project (`ait setup --help` → `aitask_setup.sh`) | Prints the full usage block covering the three opt-in tiers; exits 0 before any side effect. |
| No project (global shim, `packaging/shim/ait`) | **Never bootstraps**: no download, no install, no prompt. Exits 0 with an actionable pointer saying the option list ships with the framework and how to get it. It does **not** print setup's options. |

The shim cannot honor the first contract: the authoritative option text lives in
`usage()` inside a file that is not on disk yet, and copying it into the shim
would create exactly the drift this plan's own mitigation guards against. The
user's scope decision ("no usage-text duplication in the shim") pins this, so
the acceptance criterion for the no-project path is *"does not bootstrap, and
says where the help is"* — not *"prints the help"*. Both paths are tested (§3,
§3b, §4).

## Scope

In scope: `aitask_setup.sh` help handler, `packaging/shim/ait` bootstrap guard,
tests, one docs line.

Out of scope (per the task's scope note): the 10 other dispatcher-exposed
scripts that lack `--help` (`board`, `monitor`, `minimonitor`, `codebrowser`,
`settings`, `syncer`, `applink`, `chatlink`, `stats-tui`, `diffviewer`) — all
TUI launchers whose failure mode is opening a TUI, not installing anything.
Also out of scope: making the `*)` catch-all reject unknown options (a separate
behavior change; `--source-only` currently relies on being swallowed there).

## Implementation

### 1. `.aitask-scripts/aitask_setup.sh` — add `usage()` and the flag case

Add a `usage()` function immediately above the `# --- Main ---` banner
(`:3702`), following the `aitask_zip_old.sh:44` convention (`cat << 'EOF'`
heredoc, `Options:` block, `Examples:` block). Use the `ait setup` invocation
form (as `aitask_codeagent.sh:620` and `aitask_projects.sh:73` do), not
`$(basename "$0")` — this script is only reachable via the dispatcher.

Per `aidocs/framework/code_conventions.md`, prefix it with a source-trace
comment naming the canonical origin of the condensed text:

```bash
# Usage text. Source: website/content/docs/commands/setup-install.md — "ait setup"
# section, guided-setup step 7 (the three opt-in dependency tiers and their
# remember-after-first-opt-in behavior). The setup-vs-upgrade verb split
# ("reinstall / repair" vs "move to a newer version") is from CLAUDE.md,
# "CLI Conventions".
usage() {
    cat << 'EOF'
Usage: ait setup [OPTIONS]

Install dependencies and configure the aitask framework in this project.
Safe to re-run: setup reinstalls, repairs, and populates whatever is missing,
preserving existing configuration. To move to a newer framework version, use
'ait upgrade' instead.

Options:
  --with-pypy   Also install the opt-in PyPy venv that speeds up 'ait board'
  --with-chat   Also install the opt-in chat SDK tier (discord.py, slack-bolt,
                slack-sdk) used by 'ait chatlink'
  --with-dev    Also install the opt-in dev/test tier (pytest, pytest-xdist),
                which gives the Python test suite a parallel lane
  -h, --help    Show this help message

Each opt-in tier is remembered after the first opt-in: later plain 'ait setup'
runs revalidate and repair it without re-passing the flag.

Examples:
  ait setup                            # Install / repair dependencies and config
  ait setup --with-dev                 # ... plus the pytest test tier
  ait setup --with-pypy --with-chat    # ... plus the PyPy and chat tiers
EOF
}
```

Then add one arm to the `main()` flag loop, after the three `--with-*` arms and
**before** `--)` and the `*)` catch-all:

```bash
            -h|--help)   usage; exit 0 ;;
```

This exits before `info "aitask framework setup"` — the first line of main()'s
body and the boundary the tests assert against.

### 2. `packaging/shim/ait` — do not bootstrap on a help request

Inside the `if [[ "${1:-}" == "setup" ]]` branch (`:22`), before the bootstrap
banner and the download, scan the remaining args and bail on `-h`/`--help`.
Deliberately **does not** reproduce `usage()`'s option list — the framework
(and therefore the authoritative text) is not installed at this point, and
duplicating it here would drift:

```bash
    # Help is a question, not a request to install: never bootstrap on
    # `ait setup --help`. This prints a pointer, NOT setup's option list —
    # that list lives in usage() in .aitask-scripts/aitask_setup.sh, which
    # does not exist until the framework is installed, and duplicating it
    # here would drift from it.
    for arg in "${@:2}"; do
        case "$arg" in
            -h|--help)
                echo "[ait] No aitasks project found in $PWD or any parent directory."
                echo "[ait] 'ait setup --help' lists setup's options, but they ship with the"
                echo "[ait] framework, which is not installed here."
                echo "[ait] Run 'ait setup' (no flags) to install aitasks into this directory,"
                echo "[ait] then re-run 'ait setup --help' for the full option list."
                exit 0
                ;;
        esac
    done
```

Note `install_global_shim()` copies this file verbatim, so
`tests/test_shim_extraction_parity.sh` (byte-identical compare) keeps passing
with no change. Existing `~/.local/bin/ait` shims pick the guard up on the next
`ait setup` / reinstall.

### 3. `tests/test_setup_help_flag.sh` (new)

Self-contained bash test in the house style (`PASS`/`FAIL`/`TOTAL` counters,
`. "$PROJECT_DIR/tests/lib/test_scaffold.sh"`, `. "$PROJECT_DIR/tests/lib/asserts.sh"`,
own summary). Run the **real script**, but from an isolated framework copy so a
future regression cannot touch the real repo or real `$HOME`:

- `setup_fake_aitask_repo "$tmp"` (copies `lib/python_resolve.sh`,
  `terminal_compat.sh`, …), plus `cp .aitask-scripts/aitask_setup.sh` and
  `cp .aitask-scripts/lib/github_release.sh` — the two sourced deps not already
  in the scaffold.
- Invoke as `HOME="$tmphome" run_bounded 30 "$out" bash "$tmp/.aitask-scripts/aitask_setup.sh" --help`
  (see the bounded-run helper below).

**Bounded-run helper (file-local).** `timeout` is GNU coreutils; macOS does not
ship it (only `gtimeout`, and only with Homebrew coreutils), so a bare
`timeout 30` would make this test fail on macOS *before* it exercises either
help path. Mirror the guard the framework already uses at
`.aitask-scripts/aitask_sync.sh:97` and `aitask_remote_drift_check.sh:152` —
prefer the binary, fall back to a background watchdog — keeping the bounded
safety property on every platform:

```bash
# run_bounded <secs> <outfile> <cmd...>  → command's exit status, or 124 on timeout
run_bounded() {
    local secs="$1" out="$2"; shift 2
    local runner=""
    command -v timeout  >/dev/null 2>&1 && runner=timeout
    [ -z "$runner" ] && command -v gtimeout >/dev/null 2>&1 && runner=gtimeout
    if [ -n "$runner" ]; then
        "$runner" "$secs" "$@" >"$out" 2>&1 </dev/null
        return $?
    fi
    # macOS fallback. `set -m` puts the child in its own process group so the
    # watchdog can kill the whole tree — a regression here spawns pip/git
    # children that a bare `kill $pid` would orphan.
    set -m
    "$@" >"$out" 2>&1 </dev/null &
    local pid=$!
    set +m
    local i=0
    while kill -0 "$pid" 2>/dev/null && [ "$i" -lt "$secs" ]; do
        sleep 1; i=$((i + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        return 124
    fi
    wait "$pid"; return $?
}
```

On the fixed path the command exits in milliseconds and the `while` guard is
false on first evaluation, so the fallback adds no latency to a passing run.
Assert the status is never `124` — a timeout means the help arm did not fire.

Assertions:
1. `--help` exits 0.
2. Output contains `Usage: ait setup`, `--with-pypy`, `--with-chat`,
   `--with-dev`, `-h, --help`.
3. Output does **not** contain `aitask framework setup` (main()'s banner) — the
   proof that no setup step ran.
4. `$tmphome/.aitask` does not exist (no venv/marker side effects).
5. `-h` behaves identically to `--help`.
6. `--with-dev --help` still prints help and exits 0 (order-independent: the
   arm fires mid-loop, before any side effect).

### 3b. Same file — cover the public interface, `./ait setup --help`

Direct invocation of `aitask_setup.sh` is not what users type; the in-project
public interface is the dispatcher. Cover it in the **same isolated fixture**
(never against the real repo — pre-fix, a dispatcher-path run is precisely the
full install this task exists to prevent). The fixture needs, beyond §3:

- `cp ait "$tmp/"` (chmod +x), and `lib/aitask_path.sh` — sourced by `ait` at
  startup; already provided by `setup_fake_aitask_repo`.
- Nothing else: `ait` `cd`s to its own dir, and `setup` is in the
  `check_for_updates` skip list (`ait:189`), so no network is touched.

Verified viable during planning: the fixture dispatches `./ait setup <flag>` to
the copied script, with `SCRIPT_DIR/..` resolving to the temp project so
`ensure_git_repo` cannot reach the real repo.

Assert, for `./ait setup --help` and `./ait setup -h`, run through the same
`run_bounded 30` helper with `HOME="$tmphome"`: exit 0 (never 124), output
contains `Usage: ait setup`, output does not contain `aitask framework setup`,
and `$tmphome/.aitask` still does not exist.

### 4. `tests/test_global_shim.sh` — one added test for the shim guard

Follow the existing Test 4 recipe (`:100-119`): generate a shim via
`generate_test_shim`, put a **fake `curl`/`wget` that always exits 1** on
`PATH`, run from an empty temp dir. That fake is also the test's built-in
negative control — without the guard the shim reaches the download and fails
with rc 1 and a "Downloading" line.

```bash
output=$(cd "$TMPDIR_N" && PATH="$TMPDIR_N/fakebin:$PATH" "$SHIM_PATH_N" setup --help </dev/null 2>&1)
rc=$?
```

Assert: `rc == 0`; output does **not** contain `Downloading`; output contains
the "not installed here" pointer. Repeat once for `-h`.

### 5. `website/content/docs/commands/setup-install.md` — one line

Under `## ait setup`, after the `ait setup` code block, add:

```markdown
Run `ait setup --help` for the full option list, including the opt-in dependency tiers below.
```

Current-state prose only, no version history (`aidocs/framework/documentation_conventions.md`).

### Post-phase (risk mitigations)

1. `[guard_usage_documents_every_tier_flag]` In `tests/test_setup_help_flag.sh`,
   do not hardcode the tier-flag list. Derive it from the source and assert each
   derived flag is documented in the `--help` output:

   ```bash
   # POSIX class, not \s: \s is a GNU grep extension and silently fails to
   # match on BSD/macOS grep (aidocs/framework/sed_macos_issues.md), which
   # would make the loop below vacuous instead of failing loudly.
   tier_flags=$(grep -oE '^[[:space:]]+--with-[a-z]+\)' \
                     "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" \
                | tr -d '[:space:])')
   tier_count=$(printf '%s\n' $tier_flags | grep -c . || true)
   assert_eq "tier-flag extractor found all 3 arms" "3" "$tier_count"
   for f in $tier_flags; do
       assert_contains "usage() documents $f" "$f" "$help_output"
   done
   ```

   The count assertion is load-bearing twice over: a silent zero-match
   extractor would make the loop vacuous and the guard would pass on any
   input, and a newly added fourth tier trips the count, forcing a deliberate
   update of both `usage()` and this pin. Run the test once on macOS-style
   grep semantics if available; otherwise the count assertion is what catches
   the portability regression on the first BSD run.

## Verification

```bash
shellcheck .aitask-scripts/aitask_setup.sh packaging/shim/ait
bash -n .aitask-scripts/aitask_setup.sh
bash tests/test_setup_help_flag.sh          # new (direct + dispatcher, isolated fixture)
bash tests/test_global_shim.sh              # extended
bash tests/test_shim_extraction_parity.sh   # unchanged, must still pass
bash tests/test_setup_git.sh                # touches the same script
```

Only **after** all of the above pass, run the real-environment confirmation
`./ait setup --help`. Ordering matters: run against the real repo while the bug
is still present and it performs the full install this task exists to prevent —
that is why every automated assertion above lives in the isolated fixture.

**Negative control** (run manually during implementation, not committed — it
deliberately executes the broken code): take the same fixture, delete the
`-h|--help)` arm from the copied script, and run `./ait setup --help` through
the same `run_bounded 20` helper with `HOME=<tmphome>`; confirm the output
*does* contain `aitask framework setup`. Already validated as safe and
correctly contained during planning (temp `HOME` + temp project root). Record
the observed result in the Final Implementation Notes. The shim guard needs no
separate negative control: the fake failing `curl`/`wget` in §4 makes the
unguarded path fail loudly (rc 1 + `Downloading`).

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.

## Risk

### Code-health risk: low
- The usage text is a condensation of `website/content/docs/commands/setup-install.md`; a future fourth `--with-*` tier could be added to the flag loop and to the docs but not to `usage()`, leaving the help silently incomplete. · severity: low · → mitigation: inline post-phase guard_usage_documents_every_tier_flag
- Everything else is additive and leaf-level: one new function, one case arm in a loop already covered by `bash -n` + shellcheck tests, and a guard in a shim whose byte-parity with the installed copy is test-enforced. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The shim fix only reaches a user's `~/.local/bin/ait` after their next `ait setup` or reinstall, so existing global shims keep the bootstrap-on-`--help` behavior until then. Inherent to how the shim is distributed; not fixable from this repo. · severity: low · → mitigation: none possible

### Planned mitigations
- timing: post-phase | name: guard_usage_documents_every_tier_flag | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — usage-text drift when a new `--with-*` tier is added | desc: derive the tier flags from aitask_setup.sh's case loop and assert each is documented in the --help output, with a non-empty/count guard so the loop cannot go vacuous

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in five parts.
  (1) `.aitask-scripts/aitask_setup.sh`: added a source-traced `usage()` above
  `# --- Main ---` and an `-h|--help)   usage; exit 0 ;;` arm in `main()`'s flag
  loop, placed after the three `--with-*` arms and before `--)` / the `*)`
  catch-all, so it exits before `info "aitask framework setup"`.
  (2) `packaging/shim/ait`: the no-project bootstrap branch now scans `"${@:2}"`
  and exits 0 with a pointer on `-h`/`--help`, before the banner, the Y/n prompt
  and the installer download.
  (3) `tests/test_setup_help_flag.sh` (new, 23 assertions): isolated framework
  fixture (`setup_fake_aitask_repo` + `aitask_setup.sh` + `lib/github_release.sh`
  + a copy of `ait`) with a temp `$HOME`, covering `--help`, `-h`,
  `--with-dev --help`, the `./ait setup --help` dispatcher path, the absence of
  the `aitask framework setup` banner, the absence of `$HOME/.aitask`, and the
  tier-flag drift guard. Includes a portable `run_bounded` helper
  (`timeout` → `gtimeout` → background watchdog with a process-group kill).
  (4) `tests/test_global_shim.sh`: Test 12 for the shim guard, reusing the
  existing fake-failing-`curl`/`wget` recipe.
  (5) `website/content/docs/commands/setup-install.md`: a `--help` pointer line
  plus the auto-bootstrap exception sentence.
- **Deviations from plan:** None in scope or structure. Three corrections made
  while implementing, all from running the checks rather than from re-reading
  the plan:
  - The planned extractor's `tr -d '[:space:])'` deleted the newlines as well and
    fused the three matches into one token (the count assertion caught it,
    reporting 1 instead of 3). Replaced with a per-line
    `sed 's/^[[:space:]]*//; s/)$//'`.
  - The planned drift guard used a plain substring check, which still passed
    after an Options line was deleted, because every tier flag also appears in
    the Examples block. Tightened to `assert_contains_re "^  <flag>[[:space:]]+[A-Za-z]"`
    so it matches an Options *entry*, and re-ran the mutation to confirm only
    the mutated flag now fails.
  - shellcheck SC1087 on `"^  $f[[:space:]]…"` (reads as array indexing);
    braced to `${f}`.
- **Issues encountered:** A concurrent session was modifying 24 unrelated files
  in this working tree (monitor / shadow / concern work, plus `tests/lib/asserts.sh`
  and `CLAUDE.md`). All commits below stage the five t1435 paths explicitly; no
  `git add -A` / `git add .` was used. Both test files were re-run after
  `tests/lib/asserts.sh` changed under them (t1207 file-backed counters) — they
  assert at top level, never inside a `( … )` subshell, so no counter opt-in is
  required and both still report real counts.
- **Key decisions:**
  - The two entry paths get deliberately asymmetric contracts. The shim prints a
    pointer, not the option list: `usage()` lives in a file that does not exist
    before installation, and duplicating its text into the shim would recreate
    the drift the post-phase guard exists to prevent. Documented in the plan's
    Outcome table and in the code comment.
  - Every automated assertion runs in an isolated fixture with a temp `$HOME`,
    never against the real repo. Pre-fix, a dispatcher-path run *is* the full
    install; a test that regressed would otherwise perform it on the developer's
    own checkout. The real-repo `./ait setup --help` was run only after the
    suites passed.
  - The `*)` catch-all still swallows unknown options (out of scope, and
    `--source-only` relies on it), so this change adds a help arm without
    altering argument-rejection behavior.
- **Verification results:** `test_setup_help_flag` 23/23, `test_global_shim`
  26/26, `test_shim_extraction_parity` 3/3, `test_setup_git` 70/70,
  `test_setup_git_tui` 16/16, `test_packaging_cleanup` 6/6, `test_version_checks`
  2/2 (`test_setup_python_install` self-skips without
  `AIT_RUN_INTEGRATION_TESTS=1`). `shellcheck` clean on every changed file
  (`aitask_setup.sh`'s remaining findings are all pre-existing and outside the
  new hunks); `bash -n` clean. `./ait setup --help` in the real repo prints the
  usage block, exits 0, and left the working tree unchanged.
- **Negative controls (all run in the isolated fixture, temp `$HOME`):**
  1. Deleting only the `-h|--help)` arm → `./ait setup --help` printed
     `aitask framework setup` and created `$HOME/.aitask`, so both the banner
     assertion and the `$HOME/.aitask` assertion are discriminating, not vacuous.
  2. Stripping only the shim guard block → rc 1 and a `Downloading` line, so
     Test 12's three assertions all fail without the guard.
  3. Deleting only the `--with-chat` Options line → the tightened guard fails
     for `--with-chat` and passes for the other two. (This control is what
     exposed the original substring check as non-discriminating.)
- **Upstream defects identified:** None. The shim's bootstrap-on-`--help`
  behavior was a second surface of *this* task's defect and was fixed here, not
  deferred. The ten other dispatcher-exposed scripts without a `--help` handler
  (`board`, `monitor`, `minimonitor`, `codebrowser`, `settings`, `syncer`,
  `applink`, `chatlink`, `stats-tui`, `diffviewer`) are a known scope exclusion
  recorded in the task's own Scope note, not a newly discovered defect — all are
  TUI launchers whose failure mode is opening a TUI, not installing anything.
- **Commit history anomaly:** while this task was in review, the concurrent
  t1207 session committed the entire shared git index, sweeping all five t1435
  paths into its commit `d490b2373` ("bug: Make the orphaned-counter test files
  enforce their assertions (t1207)"). The code is correct and in the tree, but
  the `(t1435)` tag was never recorded there. Resolution (user's call): an empty
  marker commit `225a8b6b5` carries the `(t1435)` tag and names `d490b2373` as
  the commit holding the diff, so tag-based lookup (`aitask_issue_update.sh`,
  changelog) resolves. History was deliberately NOT rewritten — the sweeping
  commit was still unpushed, but the other agent was live in the same tree.
