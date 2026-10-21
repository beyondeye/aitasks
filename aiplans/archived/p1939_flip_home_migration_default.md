---
Task: t1939_flip_home_migration_default.md
Base branch: main
Output branch: main
---

# t1939 — `ait setup` migrates the legacy per-user root by default

## Context

t1852_6 shipped `ait engine home [--migrate]` as an explicit verb. Today `ait setup`
only prints the `HOME_LEGACY:` hint (`report_home_legacy()`). This task makes setup
run the migration itself, with the opt-outs the proposal reserves:
`--no-home-migration` and `AIT_HOME_MIGRATE=0`.

The admission precondition is met. t1931 passed on this Linux real home
(`HOME_MIGRATED:7`). t2086 passed on macOS: the test suite gave 236/0, the real home
gave `HOME_MIGRATED:4`, and the TUIs and setup worked through the symlink.

## Step 0 — reality check (measured 2026-10-21, main @ f0d1e5712)

| # | task says | repository has | decision |
|---|---|---|---|
| R1 | decide where in `main()` migration runs relative to the tenant writers | Every writer of `~/.aitask/<tenant>` runs from `setup_python_venv` onward: venv, python, uv, bin via `install_python_wrappers`, then `setup_pypy_venv` and `setup_dev_deps`. Nothing after `setup_dev_deps` writes a tenant. `setup_aitasks_home` and `install_engine_binary` write only `$AITASKS_HOME/engine` | **Run it last.** The call goes after `commit_framework_data_files` and before `check_latest_version`/the summary. (a) Setup never recreates a tenant after moving it. (b) A **fresh install** also ends in the new layout: setup creates `~/.aitask/venv`… and the same run moves it. Running the migration first would find `no-legacy-root` and then build a legacy tree. (c) Every setup commit is already done, so an exit-2 stop loses nothing. (d) The summary's `report_home_legacy` then shows the state after migration |
| R2 | install.sh pass-through "if the upgrade path should migrate too; decide and record" | 9+ test files run the full `install.sh` against the **real** `$HOME`: crew_runner_config_delivery, install_upgrade_changelog, upgrade_prunes_retired_scripts, t644, install_changelog_preservation, t167, install_create_data_dirs, install_engine_binary, …. Making install.sh migrate would move a contributor's real `~/.aitask` during a test run, which the task forbids | **install.sh does not migrate.** It prints the read-only `report_home_legacy` hint, which points at `ait setup`, so upgrade-only users learn about it. No `--no-home-migration` in install.sh, since there is nothing to opt out of. Per CLAUDE.md's verb rule, a layout repair belongs to `ait setup` |
| R3 | keep setup's own update check out of the migration window | `ait` skips `check_for_updates` for `setup` and `upgrade`. `check_latest_version` writes nothing and runs after the migration | **holds**, no change |
| R4 | D7: engine slot writers don't take the home lock | `install_engine_binary` and the migration run sequentially in one process. The migration never touches `$AITASKS_HOME/engine` | **holds**: no concurrency within a run, so D7 is unchanged |
| R5 | setup "branches on the protocol" and prints lines verbatim | `warn`/`info` use `echo -e`, which would interpret backslashes in `%q`-quoted `HOME_RESTORE` commands | protocol lines are printed with `printf '%s\n'`, raw and unindented. `report_home_legacy`'s `info "  $line"` gets the same fix |
| R6 | full-setup tests use a scratch HOME | `test_setup_python_install.sh` and `test_frozen_agents_acceptance.sh` (level 3) run full `ait setup` with a scratch `HOME` but **inherit `AITASKS_HOME`**. With the default flipped, a developer who exports it would have scratch tenants migrated into their real root | add `env -u AITASKS_HOME` to those two invocations. Their `~/.aitask/venv/...` assertions keep passing through the symlink |
| R7 | 18 doc files | re-measured: the same 18 plus `CLAUDE.md` (dev-tier table, lines 79-80) | see Step 5 for the per-line rule |

`aitask_engine.sh` needs no change.

## Implementation steps

### 1. `.aitask-scripts/aitask_setup.sh`

**a. New function** `migrate_home_legacy`, next to `report_home_legacy`. It does not
spell the legacy path, so the T9 guard needs no marker:

```bash
# --- Legacy per-user root migration (t1939) ---
# migrate_home_legacy [--no-home-migration] — run `ait engine home --migrate`
# (the one owner of the move) and branch on its exit class. Protocol lines are
# printed verbatim (printf, never echo -e: HOME_RESTORE commands are %q-quoted).
# Opt-outs: the flag, or AIT_HOME_MIGRATE=0. Returns the class to the caller:
#   0          migrated, nothing to migrate, or opted out
#   1          refused or rolled back — the legacy root is as it was; continue
#   2          rollback blocked — HOME_STRANDED/HOME_RESTORE printed; caller stops
#   128+signo  interrupted — caller stops with this status
migrate_home_legacy() {
    if [[ "${1:-}" == "--no-home-migration" ]]; then
        info "Per-user root migration skipped (--no-home-migration)"; return 0
    fi
    if [[ "${AIT_HOME_MIGRATE:-1}" == "0" ]]; then
        info "Per-user root migration skipped (AIT_HOME_MIGRATE=0)"; return 0
    fi
    local out rc=0
    out="$(bash "$SCRIPT_DIR/aitask_engine.sh" home --migrate 2>&1 </dev/null)" || rc=$?
    case "$rc" in
        0)
            # HOME_SKIPPED:no-legacy-root / already-migrated: nothing to say.
            printf '%s\n' "$out" | grep -q '^HOME_MIGRATED:' || return 0
            success "Per-user root migrated into $AITASKS_HOME (the legacy root is now a symlink to it):"
            printf '%s\n' "$out"; return 0 ;;
        1)
            warn "Per-user root not migrated — nothing was changed; setup continues:"
            printf '%s\n' "$out"; return 1 ;;
        2)
            warn "Per-user root migration FAILED and its rollback was blocked."
            warn "Run the HOME_RESTORE steps below in order, then re-run 'ait setup':"
            printf '%s\n' "$out"; return 2 ;;
        *)
            if (( rc >= 128 )); then
                warn "Per-user root migration interrupted (exit $rc):"
                printf '%s\n' "$out"; return "$rc"
            fi
            warn "Per-user root migration did not run (exit $rc); setup continues:"
            printf '%s\n' "$out"; return 1 ;;
    esac
}
```

**b. `main()`:**
- Parser: `--no-home-migration) no_home_migration=1; shift ;;` and add the
  `local no_home_migration=0`.
- After `commit_framework_data_files` / `echo ""`, and before `check_latest_version`:
  ```bash
  # Last, after every tenant writer (venv, python, uv, bin, pypy, dev tier) and
  # every setup commit: setup never recreates a tenant it just moved, a fresh
  # install also ends in the new layout, and a blocked rollback stops here
  # with nothing left uncommitted (t1939).
  local home_rc=0
  if [[ "$no_home_migration" == "1" ]]; then
      migrate_home_legacy --no-home-migration || home_rc=$?
  else
      migrate_home_legacy || home_rc=$?
  fi
  if (( home_rc >= 2 )); then
      warn "Setup stopped before completion (per-user root migration, exit $home_rc)."
      exit "$home_rc"
  fi
  echo ""
  ```
- `usage()`: add `--no-home-migration` with the line "Leave the legacy per-user root
  in place (also: AIT_HOME_MIGRATE=0)". Add a sentence to the trailer saying setup
  moves an older `~/.aitask` root into `$AITASKS_HOME` and leaves a symlink behind.

**c. `report_home_legacy`:** print the `HOME_LEGACY:` line with `printf` (R5). The
second line becomes: `'ait engine home' shows what blocks it; 'ait setup' (or 'ait
engine home --migrate') moves these into $AITASKS_HOME and leaves a symlink behind`.
Update its header comment: setup now migrates by default, and the hint appears only
after a refusal, an opt-out, or from install.sh.

### 2. `install.sh`

After the `check_superseded_model_defaults` block and before
`report_claude_session_hook`, add a read-only hint (R2). The guard is there because
`--version` can pair this installer with an older `aitask_setup.sh`, the same reason
as `setup_data_gitignore_symlink_safe`:
```bash
# The upgrade path never migrates the legacy per-user root (t1939): that is a
# layout repair, which `ait setup` owns. Surface the read-only hint instead.
if declare -F report_home_legacy >/dev/null; then
    report_home_legacy
fi
```

### 3. `tests/test_aitasks_home.sh`

The setup-driven matrix runs the **installed** tree's `aitask_setup.sh main()`,
after a real `install.sh --dir`, **under production shell options**. Running a full
installed `ait setup` instead would install CLI tools, build venvs over the network
and query GitHub; the two tests that do that are gated off by default
(`AIT_RUN_INTEGRATION_TESTS`, `AIT_ACCEPTANCE_FULL_SETUP`), so they cannot be the
evidence.

- Header (lines 11-15): "Setup only hints" becomes "setup migrates by default
  through the installed `main()` (I*); install.sh only hints (H-I2)".
- T9: add `"aitask_setup.sh:migrate_home_legacy"  # t1939 — setup-driven migration`
  to `FEATURE_FUNCTIONS`.
- **New harness `setup_strict <setup.sh> <home> <aitasks_home|-> [main args…]`**
  sets `out`/`rc`. `SETUP_ENV` adds environment (hooks, `AIT_HOME_MIGRATE`);
  `SETUP_EVAL` adds per-case overrides.
  ```bash
  out="$(env -u AITASKS_HOME HOME="$h" ${ah:+AITASKS_HOME="$ah"} ${SETUP_ENV[@]+"${SETUP_ENV[@]}"} \
      bash -c '
          source "$1" --source-only   # keeps setup'"'"'s own set -euo pipefail: production options
          shift
          keep=" main info success warn die detect_os setup_aitasks_home migrate_home_legacy report_home_legacy "
          for fn in $(compgen -A function); do
              [[ "$keep" == *" $fn "* ]] && continue
              eval "$fn() { return 0; }"   # 0, not 1: errexit stays armed in main()
          done
          eval "${SETUP_EVAL:-}"
          main "$@"' _ "$script" "$@" </dev/null 2>&1)"; rc=$?
  ```
  The parser, the call's position in `main()`, the `|| home_rc=$?` capture, the
  `exit "$home_rc"` stop and the summary are all the installed code running under
  errexit. Stubs return 0, so the tier probes answer "yes". The **real call sites**
  of `setup_python_venv`, `setup_pypy_venv` and `setup_dev_deps` are therefore
  reached. `SETUP_EVAL='source "$TENANTS"'` overrides those three with writers kept
  in a file, `$SCRATCH/tenants.sh`. They create the shapes the real steps leave in
  `$HOME/.aitask`, idempotently: a real `python3 -m venv --without-pip` venv (made
  only when absent), `python/3.x/bin/python3`, `uv/uv`, the `bin/python3` wrapper,
  `pypy_venv/bin/python` and `dev_tier`.
- **One real install** (the existing H-I `$T`, through `install.sh --dir
  --local-tarball --local-engine`) provides `$T/.aitask-scripts/aitask_setup.sh` for
  every I case. Each case uses its own scratch HOME.
- **I matrix.** Each case asserts the exit code, whether "Setup complete!" is
  printed, and `tree_sig` of both trees:

  | case | setup | expectation |
  |---|---|---|
  | **I1 fresh install** (ordering pin) | empty HOME, tenant writers on, default `AITASKS_HOME` | `HOME_MIGRATED:6`; `~/.aitask` is `LINK:$H/.aitasks`; the venv and PyPy venv run via `~/.aitask/...`; exit 0; no hint |
  | **I2 working venv + PyPy** | `mklegacy --no-engine`, writers on | `HOME_MIGRATED:7`; link; `~/.aitask/venv/bin/python -c 'print(42)'` (REAL_VENV), `pypy_venv/bin/python` and `bin/python3` run |
  | **I3 idempotent re-run** | I2's home again | no `HOME_MIGRATED`, no hint; link and `tree_sig "$H/.aitasks"` unchanged; tenants still run |
  | **I4 hostile symlink** | `~/.aitask -> elsewhere`, writers off | `HOME_SKIPPED:foreign-symlink:<t>`; exit 0, completes; link and target byte-identical |
  | **I5 cross-device** | `AITASKS_HOME` on `/dev/shm` (H8's skip rule, reported, not counted) | `HOME_SKIPPED:cross-device`; exit 0, completes; legacy byte-identical |
  | **I6 destination collision** | `mklegacy` with `engine`, `$AH/engine` pre-made | `HOME_SKIPPED:destination-exists:engine`; both trees byte-identical; exit 0; hint is the line after `AITASKS_HOME:` |
  | **I7 `AITASKS_HOME` override** | `mklegacy --no-engine`, `AH=$SCRATCH/custom` | `HOME_MIGRATED:7`; `LINK:$AH`; tenants in `$AH`; no `$H/.aitasks` created |
  | **I8 `--no-home-migration`** | real parser via main args | legacy byte-identical; names the flag; hint; exit 0 |
  | **I9 `AIT_HOME_MIGRATE=0`** | `SETUP_ENV` | as I8, naming the env var |
  | **I10 rolled back (class 1)** | H14's `post-moves` hook | `HOME_ROLLED_BACK:7`; exit 0, completes; legacy restored after removing the stray file |
  | **I11 rollback blocked (class 2)** | H22's hook | exit 2, no "Setup complete!"; `HOME_FAILED:rollback|venv`, `HOME_STRANDED:` and `HOME_RESTORE:` at line start; running the `HOME_RESTORE:venv\|` commands **taken from setup's output** restores the original and keeps the competitor aside |
  | **I12 interrupted** | H19's TERM-at-`pre-mv python` hook | exit 143, no "Setup complete!"; `HOME_SKIPPED:interrupted:TERM` + `HOME_ROLLED_BACK:`; legacy byte-identical |

  Admission criteria mapped to cases: fresh install (I1), working venv + PyPy (I2),
  idempotent re-run (I3), hostile symlink (I4), cross-device (I5), collision with
  both trees unchanged (I6) and the override (I7) all run through the installed
  setup. The direct-verb H cases stay as they are.
- **H-I2, upgrade path:** a second real `install.sh --dir` into a fresh scratch HOME
  holding `mklegacy --no-engine`. Expect exit 0, the legacy tree byte-identical
  (install.sh never migrates), and the `HOME_LEGACY:` hint in the output.
- The old S1-S3 are removed, because I1/I3/I6/I8 supersede them. `run_main` and T8
  are unchanged.

### 4. Other tests

- `tests/test_setup_python_install.sh:36` and
  `tests/test_frozen_agents_acceptance.sh:1287,1290`: prefix with `env -u
  AITASKS_HOME` (R6). Both are gated integration tests, so this is hardening, not
  coverage. Their `$HOME/.aitask/venv` assertions hold through the link.

### 5. Docs

**Why the rule works:** `~/.aitask/<tenant>` resolves in **every** layout. That
covers migrated homes (through the symlink), opted-out, refused and upgrade-only
homes, and an `AITASKS_HOME` override, where the link points at the override.
`~/.aitasks/<tenant>` resolves only in the default migrated layout. The rule for
each line:

1. **Operational commands and lookup paths keep `~/.aitask/<tenant>`.** This
   covers diagnostic invocations, `AIT_PYTHON=…`, the uninstall `rm -rf`, marker
   removal, `pip uninstall`, and "Requirements: venv at …" lines that name what the
   resolver looks up. No change there: board-stats.md:22,41,
   codebrowser/_index.md:28, codebrowser/reference.md:132,
   development/_index.md:216,218, development/pypy.md:12,47,54,61,
   installation/pypy.md:27, tui_conventions.md:45,61, python_tui_performance.md:618,
   and CLAUDE.md:79-80.
2. **Statements of where setup puts files** (what it creates, disk usage) name the
   per-user root: the files live under `$AITASKS_HOME` (default `~/.aitasks/`), and
   `~/.aitask/` is kept as a symlink to it, so every `~/.aitask/…` path keeps
   working. One cross-link goes to the Setup & Install page for the opt-out and
   refusal cases. Lines: README.md:104, installation/_index.md:125-126,
   installation/linux.md:88, installation/windows-wsl.md:48,
   installation/pypy.md:20, packaging_distribution_status.md:179,
   python_tui_performance.md:37,149, and setup-install.md step 7.
3. **Code quotes** (python_tui_performance 115/125/127, extension_points 446/453),
   **dated measurement records** (python_tui_performance 26/182-183/242-243/
   373-374/537, sed_macos_issues 502/576) and the **v0190 blog post** stay as-is.

The rule-1 and rule-3 files are left unchanged on purpose. Each one is recorded in
the Final Implementation Notes with its reason, so "18 files updated" reads as "18
files decided".

- `website/content/docs/commands/setup-install.md`: add a step "**Per-user root**"
  before the version check. It explains that `ait setup` moves an older
  `~/.aitask/` into `$AITASKS_HOME` (default `~/.aitasks/`) at the end of setup and
  leaves `~/.aitask` as a symlink, so existing paths keep working. A refusal or
  rollback leaves everything in place, prints the reasons and keeps the hint
  (`ait engine home` shows why). A blocked rollback stops setup and prints the
  restore steps. Opt-outs are `--no-home-migration` and `AIT_HOME_MIGRATE=0`, and
  `ait upgrade` only prints the hint. Rule-2 lines elsewhere link here.
- CLAUDE.md:120 gains "`ait setup` runs `--migrate` by default
  (`--no-home-migration` / `AIT_HOME_MIGRATE=0`)".
- `aidocs/testing_engine/n014_explorer_006_proposal.md`, in current-state form:
  - Component M1.6: replace "In this release `ait setup` only prints the hint;
    flipping the default … is a named follow-up admitted when …" with the
    setup-default behaviour, both opt-outs and install.sh's hint-only route.
  - Drop the item from *Named follow-ups*.
  - Fix `assumption_legacy_user_root_coexists`.
  - `tradeoff_split_home_rejected`: change "becoming the default in a named
    follow-up" to the current state.
  - `tradeoff_home_migration_window`: the "why the verb is explicit in this release"
    sentence.
  - Module table row M1.6.
- `cd website && python3 check_links.py --build`.

### 6. Verification

- `bash tests/test_aitasks_home.sh` (expect ALL PASSED; I5 may report SKIP),
  `bash tests/test_install_engine_binary.sh`, `bash tests/test_setup_help_flag.sh`
  and `bash tests/test_setup_hooks_only.sh`. Also run the real-HOME install.sh tests
  from R2: `test_t644_branch_mode_upgrade.sh`, `test_t167_integration.sh` and
  `test_upgrade_prunes_retired_scripts.sh`. They show the hint call is harmless
  there; on this already-migrated host they would be a no-op even if install.sh
  migrated, which is why H-I2/m5 carry that proof.
- The gated full-setup tests (`AIT_RUN_INTEGRATION_TESTS=1 bash
  tests/test_setup_python_install.sh`, `AIT_ACCEPTANCE_FULL_SETUP=1 bash
  tests/test_frozen_agents_acceptance.sh`) run when the network allows. Their result
  is reported, but they are **not** counted as admission evidence.
- `shellcheck .aitask-scripts/aitask_setup.sh install.sh`.
- **Mutation checks**, run in an isolated scratchpad copy and never in the shared
  worktree. Each one must make its case fail:
  - (m1) move the call before `setup_python_venv` → I1;
  - (m2) continue on class 2 → I11;
  - (m3) continue on ≥128 → I12;
  - (m4) ignore the flag → I8, and ignore the env → I9;
  - (m5) make install.sh call `migrate_home_legacy` → H-I2;
  - (m6) drop the `|| home_rc=$?` capture, so a bare call runs under errexit → I10
    aborts before "Setup complete!". This is the production-options proof.
- `./ait engine home` on this host is still `HOME_NEXT:none|already-migrated`.

## Step 9 (Post-Implementation)

Commit the code (`enhancement: … (t1939)`), then archive per the workflow.

## Risk

### Code-health risk: medium
- The default now renames the shared per-user root, which holds the venv and Python
  that every project on the host uses, on the next `ait setup` for every user. A
  verb defect would hit real homes without anyone opting in. This is bounded by the
  verb's preflight, inode checks and rollback, by its passes on real Linux and macOS
  homes (t1931/t2086), and by setup's handling of each exit class. · severity: medium · → mitigation: t2107
- A test that runs full setup with a scratch HOME but an inherited `AITASKS_HOME`
  could migrate scratch tenants into a developer's real root. Closed in-plan (R6),
  and install.sh stays non-migrating so the real-HOME install tests cannot move
  anything. · severity: low · → mitigation: none (in plan)

### Goal-achievement risk: low
- Upgrade-only users (`ait upgrade` without a later `ait setup`) are not migrated.
  They get the hint pointing at `ait setup`. This is the recorded R2 decision. The
  task allowed it ("decide and record"), but it differs from the Context's
  parenthetical. · severity: low · → mitigation: none
- The I matrix runs the installed `main()` under production options, but the steps
  that do not touch the home are stubbed. An interaction with a real heavy step, for
  example a networked venv build changing the tenant shapes, is caught only by the
  gated full-setup tests and the real-home check. · severity: low · → mitigation: t2107

### Planned mitigations
- timing: after | name: setup_default_real_home_check | type: manual_verification | priority: medium | effort: low | inline_risk: medium | added_complexity: low | addresses: code-health — default migration of real shared per-user roots | desc: On a real unmigrated home (Linux and macOS), run the released `ait setup`; confirm HOME_MIGRATED:<n>, board (PyPy) and monitor boot, and a re-run prints no hint and does not re-migrate | created: t2107

## Post-Review Changes

### Change Request 1 (2026-10-21 12:40)
- **Requested by user:** `migrate_home_legacy` buffered the verb's stdout+stderr in `$( )`. When a TERM reaches setup's whole process group, setup dies and the buffer is lost, although the verb handles the signal. The reviewer reproduced it: a competitor blocked the rollback, and the `HOME_FAILED` / `HOME_STRANDED` / `HOME_RESTORE` lines vanished while the venv stayed stranded. I12 signals only the verb, so it could not catch this. Verified valid. The impact is wider than lost output: on a signal the verb exits 128+signo **even when its rollback was blocked**, so those lines are the only record of a stranded entry, and a dead pipe reader could also SIGPIPE the verb while it prints them.
- **Changes made:**
  - The verb now writes straight to setup's stdout/stderr, with no buffer.
  - Setup holds handler traps (`trap 'sig=…'`) for INT, TERM and HUP around the call. It therefore outlives a process-group signal, waits for the verb's own recovery, then reports and stops with 128+signo. It also stops when only setup was signalled and the verb finished normally. The traps are never `''`, because an ignored signal is inherited by the verb, which could then not trap it.
  - A lock-free `ait engine home` pre-report keeps the `HOME_NEXT:none|…` case (no legacy root, already migrated) silent, which the dropped capture can no longer filter.
  - Class messages now point at the HOME_ lines *above*.
- **Tests:**
  - New `setup_strict_pg`: setup leads its own process group (`set -m` in a subshell, output to a file).
  - New **I13**: after the moves, a hook creates a competing venv and then TERMs the whole group. Expect exit 143, no "Setup complete!", setup's interrupted message, `HOME_SKIPPED:interrupted:TERM`, `HOME_FAILED:rollback|venv` and `HOME_STRANDED:` intact, and the two `HOME_RESTORE:` steps taken from setup's output restore the venv while keeping the competitor aside.
  - Suite: 320/320.
  - Mutants: **m7** (the original buffered code) fails I13, 7 assertions. **m8** (streaming without traps) fails I13 because setup does not outlive the TERM. **m9** (`trap ''` in place of handlers) fails I12, because the verb inherits SIG_IGN. m1–m6 are still each caught by their own case. Shellcheck findings are identical to HEAD.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`, `tests/test_aitasks_home.sh`, `aidocs/testing_engine/n014_explorer_006_proposal.md`

## Final Implementation Notes
- **Actual work done:**
  - `aitask_setup.sh`:
    - New `migrate_home_legacy`, run as the last step of `main()` (after `commit_framework_data_files`, before `check_latest_version`).
    - A lock-free `ait engine home` pre-report keeps `HOME_NEXT:none|…` silent. Otherwise `ait engine home --migrate` runs with its output streamed to setup's own fds, inside INT/TERM/HUP handler traps.
    - Branches on the exit class: 0/1 continue; 2 or 128+ make `main()` print "Setup stopped before completion" and exit with that status.
    - `--no-home-migration` flag and `AIT_HOME_MIGRATE=0` opt-outs, plus a usage paragraph.
    - `report_home_legacy` prints the `HOME_LEGACY:` line with `printf`, and its hint now points at `ait setup`.
  - `install.sh`: calls the read-only `report_home_legacy` (behind a `declare -F` guard) and never migrates.
  - `tests/test_aitasks_home.sh`:
    - T9 registers `migrate_home_legacy`.
    - New harnesses `setup_strict` and `setup_strict_pg` run the **installed** setup's `main()` under its own `set -euo pipefail`.
    - Cases I1–I13 cover fresh install (the ordering pin), working venv and PyPy venv, re-run, hostile symlink, cross-device, collision, override, both opt-outs, classes 1, 2 and 143, and a process-group TERM. H-I2 shows install.sh only hints. S1–S3 are removed.
    - 320/320 pass.
  - `env -u AITASKS_HOME` added in `test_setup_python_install.sh` and `test_frozen_agents_acceptance.sh`.
  - Docs: a new "Per-user root" section on the setup-install page (step 7 path, new step 11), the rule-2 location lines, a CLAUDE.md note, and the proposal's M1.6 current-state edits.
- **Deviations from plan:**
  - The plan's buffered `out="$(…)"` design was replaced by streaming plus handler traps after review (Change Request 1). Because nothing is captured, the silent no-op case now comes from the read-only `HOME_NEXT:` report.
  - The proposal edits waited until t1853_4 committed the file (1518db768). It had uncommitted hunks there, and the user confirmed it had landed.
- **Doc files decided but left unchanged** (rule 1 — `~/.aitask/…` resolves in every layout; rule 3 — code quotes, measurement records, blog):
  - `website/content/docs/commands/board-stats.md` (requirements lookup path)
  - `website/content/docs/development/_index.md` (runner's resolver path; dev-tier marker removal)
  - `website/content/docs/development/pypy.md` (resolver path; diagnostic commands)
  - `website/content/docs/tuis/codebrowser/_index.md`, `codebrowser/reference.md` (requirements lookup path)
  - `website/content/docs/installation/pypy.md:27` (uninstall command; line 20 updated)
  - `aidocs/framework/tui_conventions.md` (resolver path; `AIT_PYTHON=` command)
  - `aidocs/framework/aitasks_extension_points.md` (quotes the PATH line the code writes)
  - `aidocs/framework/sed_macos_issues.md` (dated test-run record)
  - `aidocs/framework/python_tui_performance.md` 26/115/125/127/182-183/242-243/373-374/537/618 (code quotes and measurement records; 37 and 149 updated)
  - `CLAUDE.md:79-80` (commands)
  - the v0190 blog post (historical)
- **Issues encountered:**
  - `test_frozen_agents_acceptance.sh` refuses to run inside tmux by design, so it was not run; its edit is syntax-checked only.
  - The two gated full-setup tests (`AIT_RUN_INTEGRATION_TESTS`, `AIT_ACCEPTANCE_FULL_SETUP`) were not run, because they need network and venv builds. They are hardening, not admission evidence.
  - The data branch reports unpushed commits ("data worktree has unstaged changes blocking rebase") because another session has unstaged changes there. That is left for `ait syncer`.
- **Key decisions:**
  - install.sh does not migrate (R2): several tests run the full `install.sh` against the real `$HOME`, and a layout repair is `ait setup`'s verb.
  - Migration runs last in `main()` (R1), so a fresh install also ends in the new layout and a stop loses no setup commit.
  - Handler traps, never `trap ''`: an ignored signal is inherited by the verb, and the verb could then not trap it (proved by mutant m9).
  - Docs keep `~/.aitask/…` for commands, because it works in every layout including opt-outs and overrides.
- **Upstream defects identified:** None
