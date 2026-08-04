---
Task: t1414_install_sh_force_fresh_dir_silent_abort.md
Worktree: (current branch, repo root — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1414 — install.sh `--force` into a fresh dir aborts silently

## Context

`install.sh` runs under `set -euo pipefail` (line 2). In
`show_upgrade_changelog()` (`install.sh:880-954`) the `else` branch of the
version lookup uses a **bare `return`**, which inherits the exit status of the
immediately preceding failed `[[ -f "$install_dir/.aitask-scripts/VERSION" ]]`
test — so it returns **1**:

```bash
    if [[ -f "$install_dir/VERSION" ]]; then          # false
    elif [[ -f "$install_dir/.aitask-scripts/VERSION" ]]; then   # false -> status 1
    else
        return  # install.sh:895 — propagates status 1
    fi
```

`main()` calls it unguarded at `install.sh:1250`, immediately after
`download_tarball` and **before** `tar -xzf` (line 1253). Under errexit the
caller treats the 1 as fatal: the script exits silently with the tarball
downloaded and **nothing installed, no error printed** — and because the abort
precedes extraction, the target directory is still completely empty. That empty
directory is the bug's observable signature.

`FORCE=true` is what makes this reachable — it skips the early return at
`install.sh:885`, so the version lookup runs. This is exactly the command
`install.sh:142` recommends to users (`… | bash -s -- --force`), so anyone
forcing a fresh re-install into a directory with no `VERSION` and no
`.aitask-scripts/VERSION` gets a silent no-op exit 1. Normal `ait upgrade` is
unaffected (`aitask_upgrade.sh:152` targets a dir that already has `VERSION`).

Pre-existing since `485b7bd17` (t85_11), not a recent regression. Found while
running the t1085 manual-verification checklist.

**Verified during planning (read-only probes, not assumptions):**

| probe | today |
|---|---|
| task's minimal repro (`bash -c 'set -euo pipefail; …'`) | prints nothing, `exit=1` |
| real `show_upgrade_changelog` on an empty dir, `FORCE=true` | **rc=1** |
| same, `FORCE=false` (site 886) | rc=0 |
| same, `current == new` version (site 912) | rc=0 |
| happy path (`1.0.0` → `2.0.0` + CHANGELOG) | rc=0, prints `Upgrading: v1.0.0 → v2.0.0` and only the v2.0.0 section |

A repo-wide scan for the same *shape* (`else` whose first statement is a bare
`return`) finds **exactly one** site — line 895. The other 43 bare `return`s in
`install.sh` sit at the end of `then` branches where the preceding command
succeeded; sites 886 and 912 are among them and are safe **only by accident**
of what precedes them (`[[ "$FORCE" != true ]]` succeeded / `rm -rf` succeeded).

There is currently **zero** test coverage of this function
(`grep -rl show_upgrade_changelog` matches only `install.sh`).
`tests/test_t167_integration.sh:184` runs a `--force` upgrade, but against a dir
that *has* `.aitask-scripts/VERSION`, so it takes the happy branch at
`install.sh:893` and never reaches the defective `else`.

## Change 1 — the fix (`install.sh`)

Make all three returns in `show_upgrade_changelog()` explicit, per the task's
"prefer explicit `return 0` at all three sites":

| line | before | after |
|---|---|---|
| 886 | `        return` | `        return 0` |
| 895 | `        return  # Can't determine current version, skip` | `        return 0  # Can't determine current version, skip` |
| 912 | `        return` | `        return 0` |

Only line 895 changes behavior; 886 and 912 are hardening so a future reordering
cannot reintroduce the class.

## Change 2 — regression test (`tests/test_install_upgrade_changelog.sh`, new)

Two surfaces in one file — the same split `tests/test_install_create_data_dirs.sh`
already uses (sourced unit tests 1-10 + a real subprocess run in test 11).

### 2a. Case 1 — hermetic full-installer run (**the regression test**)

This asserts the failure t1414 actually names — *the target directory stays
empty* — by driving the real `main()` end to end, not just the helper:

```bash
scratch="$(mktemp -d)"; mkdir -p "$scratch/home" "$scratch/bin" "$scratch/target"
HOME="$scratch/home" SHIM_DIR="$scratch/bin" \
  bash "$PROJECT_DIR/install.sh" --force \
       --dir "$scratch/target" --local-tarball "$tarball" </dev/null >"$log" 2>&1
rc=$?
```

Asserts: `rc == 0`, `$scratch/target/ait` exists, and
`$scratch/target/.aitask-scripts/VERSION` exists.
**Today this fails on all three** (rc=1, target empty) — it is discriminating,
and it proves the extraction at line 1253 is now reached, which the helper-level
cases cannot.

**Why this is hermetic — each containment point verified in source, not assumed:**

| hazard | containment | source |
|---|---|---|
| global shim written to `~/.local/bin` | `SHIM_DIR="${SHIM_DIR:-$HOME/.local/bin}"` — env-overridable | `aitask_setup.sh:9` |
| PATH line appended to `~/.zshrc`/`~/.bashrc`/`~/.profile` | `ensure_path_in_profile` writes only under `$HOME` | `aitask_setup.sh:983-1019` |
| real `git commit` in the target | `commit_installed_files` also requires `.aitask-scripts/VERSION` to be **git-tracked at the target path** — impossible for a freshly created dir, so it early-returns unconditionally here (verified: `git -C <fresh subdir of this repo> ls-files --error-unmatch .aitask-scripts/VERSION` → rc=1, vs rc=0 at the repo root) | `install.sh:977-987` |
| `rm -rf` of `packaging/` | `cleanup_packaging_leftover` only touches `$dir/packaging`, inside the target | `install.sh:1219-1227` |
| data-branch commit | `commit_installed_data_files` early-returns without `$INSTALL_DIR/.aitask-data/.git` | `install.sh:1138` |
| network | `--local-tarball` → plain `cp`; `check_prerequisites` requires curl/wget only when `LOCAL_TARBALL` is empty | `install.sh:260-263`, `92-107` |
| `python3` / pyyaml | `merge_seed` shells out only when the dest file already exists; on a fresh dir every dest is missing → plain `cp` | `install.sh:414-421` |
| interactive prompts (`confirm_install`, the "Proceed with upgrade? [Y/n]" read) | `</dev/null` makes every `[[ -t 0 ]]` false | `install.sh:150`, `946` |

One mechanic the test must get right: **`--dir` must already exist** —
`install.sh:89` does `cd "$INSTALL_DIR"` and `die`s otherwise. Hence the
`mkdir -p "$scratch/target"`.

**Case 1 is unconditional — it has no skip path and no environment
precondition.** An earlier draft guarded it on `$scratch` not being inside a git
work tree; that guard is both unnecessary (see the `commit_installed_files` row
above — the tracked-`VERSION` requirement already makes a commit impossible for
a fresh dir, regardless of `TMPDIR`) and harmful, because a skip would let the
suite report green without ever running the one assertion that proves the
task's observable outcome. If the setup ever cannot be built (fixture tarball
fails to pack), the test **fails loudly** — `FAIL++` and a diagnostic — it never
skips.

**Tarball fixture** (release layout, `.github/workflows/release.yml:86-96`), built
from the repo the way `tests/test_crew_runner_config_delivery.sh:121-131` does:

```bash
(cd "$PROJECT_DIR" && tar czf "$tarball" .aitask-scripts/ ait packaging/ seed/)
```

`ait` and `.aitask-scripts/*.sh` are mandatory (`set_permissions`,
`install.sh:957-962`, chmods both unconditionally);
`packaging/shim/ait` is mandatory unless `$SHIM_DIR/ait` pre-exists
(`aitask_setup.sh:1029-1042` `die`s otherwise); `.aitask-scripts/lib/python_resolve.sh`
and `lib/github_release.sh` are needed by the `source … aitask_setup.sh --source-only`
at `install.sh:1341`. `seed/` and `skills/` are per-file optional (each installer
warns and returns), but `seed/` is included so the run matches a real release.

### 2b. Cases 2-5 — helper-level pins (fast, branch-precise)

Reusing the `source "$PROJECT_DIR/install.sh" --source-only` pattern
(`test_install_tarball_download.sh:26`; `--source-only` must be the **first**
argument — the parser `break`s on it at `install.sh:57`). Each case runs the
helper under **live errexit**, so a nonzero return kills the subshell exactly as
it kills `main()`:

```bash
run_case() {   # sets rc + out: combined output plus a post-call MARKER
    out="$( set -euo pipefail; FORCE="$1"; \
            show_upgrade_changelog "$2" "$3" </dev/null 2>&1; echo MARKER )"; rc=$?
}
```

`</dev/null` is load-bearing here too: command substitution redirects stdout
only, so stdin stays the caller's terminal and case 5 would **hang** on the
`[[ -t 0 ]]`-guarded `read -r answer` (`install.sh:946-953`) for anyone running
the suite interactively.

| # | scenario | asserts | discriminates? |
|---|---|---|---|
| 2 | empty dir, no `VERSION` anywhere, `FORCE=true` (site 895) | `rc=0` and output contains `MARKER` | **yes** — today `rc=1`, no `MARKER` |
| 3 | `FORCE=false` (site 886) | `rc=0`, `MARKER` present | no — pin only |
| 4 | tarball version == installed version (site 912) | `rc=0`, `MARKER` present | no — pin only |
| 5 | happy path `1.0.0` → `2.0.0` with `CHANGELOG.md` | `rc=0`, output contains `Upgrading: v1.0.0 → v2.0.0` and `- new thing`, and **not** `- old thing` (slicing stops before the current version's section) | no — pin only |

**Cases 1 and 2 are the regression tests; 3-5 pass both before and after the fix**
and are pins protecting the hardening and the display path we are editing. The
plan claims nothing more for them.

Helper-case fixtures use
`tar -czf "$tb" -C "$src" .aitask-scripts/VERSION CHANGELOG.md` — member names
**without** a `./` prefix, matching the release layout and the selective
extraction at `install.sh:902-903`. (`(cd src && tar czf X .)` stores
`./.aitask-scripts/…`; GNU tar still matches, BSD tar is less forgiving.)
CHANGELOG headings are bare `## v<version>`, matching the `^## v` /
exact-string-equality slicing at `install.sh:921-938`.

All scratch state lives under one `mktemp -d` with a `trap … EXIT` cleanup. The
file sources `tests/lib/asserts.sh`, declares `PASS`/`FAIL`/`TOTAL` (the helpers
mutate caller globals), stays BSD/bash-3.2-safe per that file's header, and ends
with the standard `Results: N passed, M failed` summary and `exit 1` on failure.

### 2c. Negative control (mandatory, before declaring the test valid)

With the `install.sh` fix reverted in the working tree, cases **1 and 2 MUST
fail** (case 1: `rc=1` and empty target; case 2: `rc=1`, no `MARKER`) and cases
3-5 MUST pass. Then restore the fix and confirm all five pass. Restore by
re-applying the three-token edit, **not** `git checkout` — `install.sh` shares a
working tree with another session's uncommitted changes.

### Deviation from the task's "Suggested regression test" — flagged

The task suggests adding the case to `tests/test_install_tarball_download.sh`.
Case 1 above *is* the `bash install.sh --force --dir <empty-dir>` run it asks
for, hardened with `HOME`/`SHIM_DIR`/`--local-tarball` containment. Only the
**file** differs: `test_install_tarball_download.sh` is scoped to
`download_tarball()` by its header comment and its
`=== install.sh download_tarball() Tests ===` banner, its curl/wget/git stubs
are irrelevant here, and it does `set +euo pipefail` globally at line 29. Repo
convention is one self-contained file per concern
(`test_install_merge.sh`, `test_install_create_data_dirs.sh`). Say the word and
I'll fold it into the existing file instead.

## Change 3 — convention note (`aidocs/framework/shell_conventions.md`)

One bullet beside the existing "Beware silent `set -e` aborts via `"$(...)"`
capture" bullet (line 12), scoped narrowly:

> **A bare `return` inherits the previous command's status.** In an `else`
> branch that status is the just-failed condition's `1`, so an "early return,
> nothing to do" reads as a failure and — under `set -euo pipefail` — kills any
> unguarded caller with no message. Write `return 0` whenever the branch means
> *success* or *a non-fatal no-op*, especially when the preceding command is a
> conditional that can fail. A bare `return` is correct only where you
> **intend** to forward the previous command's status to the caller; say so in a
> comment when you do. (`install.sh:895`, t1414.)

This is deliberately narrower than "always write `return 0`" — forwarding a
failure is a legitimate idiom and the bullet must not outlaw it. Drop this
change entirely if you'd rather keep the task to code + test.

## Working-tree hygiene

Another session holds uncommitted changes to `.aitask-scripts/aitask_gate.sh`,
`lib/gate_ledger.py`, `lib/gate_orchestrator.py`, `aidocs/gates/*.md`, and
`tests/test_gate_orchestrator.sh`. All commits here stage **only** the three
paths this task touches, explicitly by name — never `git add -A`/`.` — and
`git diff --cached` is checked before each commit.

## Verification

```bash
bash tests/test_install_upgrade_changelog.sh   # new — expect ALL TESTS PASSED
bash tests/test_install_tarball_download.sh    # untouched file, no regression
bash tests/test_install_create_data_dirs.sh    # other install.sh --source-only consumer
shellcheck install.sh                          # no new findings vs. baseline
```

Plus the negative control in §2c, and the task's own minimal repro re-run
against the patched function:

```bash
bash -c 'source install.sh --source-only; set -euo pipefail; FORCE=true;
         show_upgrade_changelog /nonexistent.tar.gz "$(mktemp -d)"; echo REACHED'
# post-fix: prints REACHED, exit 0   (today: prints nothing, exit 1)
```

`project_config.yaml` has no `verify_build` / `test_command`, so Step 9 build
verification is skipped; `risk_evaluated` is the task's only active gate.

## Risk

### Code-health risk: low
- Three-token change confined to one function; sites 886/912 are provably
  status-0 today, so only the genuinely broken site 895 changes behavior ·
  severity: low · → mitigation: covered by the case 3/4 pins, no follow-up
- The new file adds a full-installer subprocess run to the suite — slower than a
  pure unit test and dependent on the repo's own `.aitask-scripts/`, `ait` and
  `packaging/shim/ait` being present to build the fixture · severity: low ·
  → mitigation: none — the same fixture pattern is already used by four existing
  install tests

### Goal-achievement risk: low
- Case 1 drives the real `main()` and asserts the observable failure (empty
  target dir), closing the "helper returns 0 but does `main()` actually get
  past it" gap · severity: low · → mitigation: none needed
- Hermeticity rests on the `SHIM_DIR` / `HOME` overrides; if a future refactor
  moves the shim write off `SHIM_DIR`, the test would touch the real
  `~/.local/bin` · severity: low · → mitigation: none — accepted; the override
  is read at `aitask_setup.sh:9` and any change there would be a deliberate edit
- Case 1 runs the real installer, so a genuine future breakage anywhere in
  `main()` after line 1250 also fails this test, not just the t1414 site ·
  severity: low · → mitigation: none — this is a feature, but it means a failure
  here needs reading before being attributed to this task

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, all three changes.
  1. `install.sh` — `return` → `return 0` at the three sites in
     `show_upgrade_changelog()` (now lines 886, 898, 915 after the added
     comment). Site 895 (pre-edit numbering) carries a three-line comment
     recording *why* the explicit 0 is load-bearing, so a future edit cannot
     "tidy" it away.
  2. `tests/test_install_upgrade_changelog.sh` — new, 14 assertions across the
     5 planned cases (1 hermetic full-installer run + 4 helper-level cases).
  3. `aidocs/framework/shell_conventions.md` — one bullet on the class, placed
     directly after the existing "silent `set -e` aborts via `"$(...)"` capture"
     bullet.

- **Deviations from plan:** None in substance. Two small additions made during
  implementation:
  - Test 1 also asserts the global shim landed in the redirected `SHIM_DIR`
    (`$scratch/bin/ait`). This doubles as a hermeticity self-check: if a future
    change stopped honouring the `SHIM_DIR` override, this assertion fails
    rather than the test silently writing into the developer's `~/.local/bin`.
  - Test 1 dumps the last 20 lines of the installer log when the run exits
    nonzero. This is what made the negative control legible — it showed the
    installer stopping right after its banner, confirming the failure was the
    t1414 abort and not some unrelated fixture problem.
  - A `# shellcheck disable=SC2034` was needed for `FORCE` in `run_case()`
    (shellcheck cannot see that the sourced helper reads it) — the same class of
    disable `tests/test_install_tarball_download.sh:110-115` already uses.

- **Issues encountered:**
  - **The `[[ -t 0 ]]` prompt hazard.** `show_upgrade_changelog`'s tail runs
    `read -r answer` behind `[[ -t 0 ]]`. Command substitution redirects stdout
    only, so stdin stays the caller's terminal: without `</dev/null`, test 5
    would have hung for anyone running the suite interactively (it did not hang
    in the agent sandbox, where stdin is already not a TTY — a bug that would
    only have surfaced on a developer's machine). Every helper case now passes
    `</dev/null`, matching how the existing e2e installer tests invoke
    `bash install.sh`.
  - **An over-attributed safety guard, caught in review.** An earlier draft
    gated the e2e case on `$scratch` not being inside a git work tree, and
    *skipped* the case otherwise — which would have let the suite go green
    without ever running the only assertion proving the task's observable
    outcome. Investigating showed the guard was unnecessary anyway: the
    load-bearing protection is `commit_installed_files`' *second* check, which
    requires `.aitask-scripts/VERSION` to be git-tracked **at the target path**.
    Verified directly: `git -C <fresh subdir of this repo> ls-files
    --error-unmatch .aitask-scripts/VERSION` → rc=1, versus rc=0 at the repo
    root. A freshly created target can never satisfy it, so no commit is
    possible regardless of `TMPDIR`. The precondition and the skip were both
    removed; case 1 is unconditional and fails loudly if its fixture cannot be
    built.

- **Key decisions:**
  - **New test file rather than extending `test_install_tarball_download.sh`**
    (the task's suggested location). That file is scoped to `download_tarball()`
    by its header and banner, its curl/wget/git stubs are irrelevant here, and
    it sets `set +euo pipefail` globally at line 29 — which would defeat the
    live-errexit reproduction. Repo convention is one self-contained file per
    concern. The task's actual assertion (`bash install.sh --force --dir
    <empty-dir>` exits 0 and installs) *is* implemented, as test 1.
  - **Two test surfaces, honestly labelled.** Only tests 1 and 2 discriminate;
    3-5 pass before and after the fix and exist to pin the sibling `return 0`
    hardening and the changelog display path. The file's header comment says so
    explicitly, so a future reader does not mistake the pins for proof.
  - **Hermeticity via `HOME` + `SHIM_DIR` env overrides**, each traced to source
    before being relied on (`aitask_setup.sh:9` for `SHIM_DIR`;
    `ensure_path_in_profile` at `aitask_setup.sh:983-1019` writes only under
    `$HOME`). Confirmed empirically after the run: the real `~/.local/bin/ait`
    mtime predated the test, `.bashrc` was untouched, and no
    "Added by aitasks installer" line appeared in any rc file.
  - **Convention bullet scoped narrowly.** Deliberately *not* "always write
    `return 0`" — forwarding a failure status to the caller is a legitimate
    bash idiom, so the bullet restricts the rule to branches meaning success or
    a non-fatal no-op and asks for a comment when forwarding is intended.

- **Verification performed:**
  - `tests/test_install_upgrade_changelog.sh` — 14 passed, 0 failed.
  - **Negative control** (site 895 reverted to a bare `return`, restored by
    re-applying the edit, not `git checkout`): test 1 failed all 4 assertions
    (exit 1, no `ait`, no `.aitask-scripts/VERSION`, no shim) and test 2 failed
    both (rc=1, no MARKER), while tests 3-5 passed unchanged; suite exit 1.
    The harness discriminates, and fails for the right reason.
  - `tests/test_install_tarball_download.sh` — 28 passed, 0 failed.
  - `tests/test_install_create_data_dirs.sh` — 40 passed, 0 failed (the other
    `--source-only` consumer, and itself an e2e `--local-tarball` runner).
  - `shellcheck install.sh` — 3 findings, all pre-existing (lines 611, 742,
    1344); **zero** new, none inside `show_upgrade_changelog`.
  - `shellcheck tests/test_install_upgrade_changelog.sh` — SC1091 infos only,
    matching the sibling test file's accepted baseline.
  - The task's own minimal repro against the patched function prints `REACHED`
    and exits 0.

- **Upstream defects identified:** None

