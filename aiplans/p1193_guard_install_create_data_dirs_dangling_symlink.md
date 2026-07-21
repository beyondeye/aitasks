---
Task: t1193_guard_install_create_data_dirs_dangling_symlink.md
Base branch: main
plan_verified: []
---

# t1193 — Guard `install.sh` `create_data_dirs()` against a dangling data symlink

## Context

`install.sh:338-344` (`create_data_dirs()`) runs five unguarded `mkdir -p`
calls on `aitasks/`, `aiplans/` and `aireviewguides/`. `mkdir -p` **fails**
("File exists") when the leading path component is a *dangling* symlink, and
`install.sh` runs under `set -euo pipefail` — so the whole install aborts with a
confusing message:

```
mkdir: cannot create directory '<dir>/aitasks': File exists
```

Surfaced during t1185 verification: a hand-built `--local-tarball` captured this
repo's own `aitasks -> .aitask-data/aitasks` / `aiplans -> .aitask-data/aiplans`
symlinks; extracted into a fresh install dir, `.aitask-data/` does not exist, so
both links dangle.

**Severity: low / latent.** `git ls-files` confirms both symlinks are
**untracked** (`.gitignore:29-30`) and there is no `.gitattributes`, so a genuine
release tarball (a `git archive`) never carries them. Only a hand-built tarball
reproduces it. It is worth guarding because the failure mode is a *total install
abort* with an opaque diagnostic.

`create_data_dirs()` is load-bearing: every later install step writes through
those roots (`install.sh:396, 411, 424, 439, 452, 479, 524, 553, 572, 601, 629,
652, 664…`). A warn-and-continue guard would only push the same abort downstream
— so for the leftover case the guard must actually *repair* the root.

This is the same defect class t1185 fixed in `aitask_setup.sh`
`ensure_agent_config_seeds()` (`:1657-1665`), which degrades to a warning
because nothing downstream depends on it. Here the disposition differs.

## Design constraint: never unlink a legitimate data-branch symlink

The dangerous case is **not** the hand-built tarball — it is an *existing
branch-mode project* whose `.aitask-data/` worktree is missing or corrupt. There
the symlink is correct and load-bearing; unlinking it would make install write
framework metadata into a real, gitignored `aitasks/` directory that is **not**
the data branch. So the guard must distinguish leftover state from a real
branch-mode layout, and **fail clearly** rather than unlink whenever the layout
looks real.

Three facts make that decision cheap and offline (all verified in this repo):

- `setup_data_branch()` writes exactly one link form —
  `ln -sf .aitask-data/aitasks aitasks` (`aitask_setup.sh:1445-1454`), so
  `readlink` is `.aitask-data/<name>`. Anything else is not a framework-created
  link.
- A registered data worktree survives deletion of its directory:
  `git worktree list --porcelain` still prints `worktree <abs>/.aitask-data`.
- A branch-mode repo has a local `refs/heads/aitask-data`.

## Approach

Add `ensure_data_root()` next to `create_data_dirs()` in `install.sh`, called
once per data root before the `mkdir -p` batch. It acts **only** on a dangling
symlink and decides via this table:

| State of `<root>` | Action |
|---|---|
| not a symlink, or symlink resolves | no-op — the `mkdir -p` batch handles it |
| dangling, `readlink` ≠ `.aitask-data/<name>` | **`die`** — unrecognized link, refuse to unlink or create anything |
| dangling, canonical target, **live** data worktree | `mkdir -p "$INSTALL_DIR/.aitask-data/<name>"` — materialize the target, preserve branch mode |
| dangling, canonical target, branch-mode evidence but worktree not live | **`die`** — "restore the worktree, then re-run" |
| dangling, canonical target, **no** branch-mode evidence | `warn` + `rm -f` — leftover tarball state, replace with a real dir |

Addressing the four review points directly:

- **Never unlink a real branch-mode link.** "Branch-mode evidence" is the union
  of three independent signals — a `.aitask-data/.git` marker (even a stale or
  corrupt one), a registered `.aitask-data` worktree, and a local
  `refs/heads/aitask-data`. Any one of them ⇒ never unlink; `die` instead.
- **Full worktree validation.** "Live" means the marker exists **and**
  `git -C "$data_dir" rev-parse --is-inside-work-tree` succeeds — the same pair
  `commit_installed_data_files()` uses (`install.sh:975-981`). A stale/copied
  `.git` fails `rev-parse`, so it lands in the `die` row, never in the
  materialize row and never in the unlink row.
- **No arbitrary target is ever materialized.** The canonical-form check runs
  *first*, and the path passed to `mkdir -p` is one this function constructs
  itself (`$INSTALL_DIR/.aitask-data/<name>`), never `readlink` output. An
  absolute, `..`-bearing, or custom target cannot reach a `mkdir` or an `rm`.
- **`aireviewguides` is out of the repair path.** `setup_data_branch()` never
  symlinks it (only the `install.sh:963` comment mentions "(when symlinked)"),
  so the framework does not own its canonical target and the destructive branch
  would ship untested. It stays in the `mkdir -p` batch, which now `die`s with a
  clear message instead of a bare `mkdir:` abort — strictly better than today
  with no untested behavior.

### `install.sh` — replace `create_data_dirs()` (lines 338-344)

```bash
# --- Prepare one data root that may be a dangling symlink ---
# In branch mode `aitasks/` and `aiplans/` are symlinks into the .aitask-data/
# worktree. When the target is absent the link DANGLES and `mkdir -p` through it
# fails ("File exists") — under `set -e` that aborts the install. Everything
# below create_data_dirs writes through these roots, so warn-and-skip would only
# move the abort downstream. Repair ONLY provably-leftover state; a link that
# looks like a real branch-mode layout is a hard error, never an unlink.
ensure_data_root() {
    local name="$1"
    local root="$INSTALL_DIR/$name"
    [[ -L "$root" && ! -e "$root" ]] || return 0

    # Only the exact form setup_data_branch writes is recognized. Anything else
    # (absolute, ../…, custom) is user state we do not own — never touched.
    if [[ "$(readlink "$root")" != ".aitask-data/$name" ]]; then
        die "$root is a dangling symlink to an unrecognized target ($(readlink "$root")).
     Remove or repoint it, then re-run the install."
    fi

    local data_dir="$INSTALL_DIR/.aitask-data"
    local has_marker=false
    [[ -d "$data_dir/.git" || -f "$data_dir/.git" ]] && has_marker=true

    # Live worktree: the link is right, its target just is not materialized.
    # Create the target we construct ourselves — never the readlink output.
    if [[ "$has_marker" == true ]] \
       && git -C "$data_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        mkdir -p "$data_dir/$name" 2>/dev/null || \
            die "Cannot create $data_dir/$name (target of $root)"
        return 0
    fi

    # Not live. Refuse to unlink if ANY signal says this repo really uses the
    # data branch — a stale/corrupt marker, a registered worktree, or the branch
    # itself. Deleting the link there would silently redirect framework metadata
    # off the data branch.
    if [[ "$has_marker" == true ]] \
       || git -C "$INSTALL_DIR" worktree list --porcelain 2>/dev/null \
            | grep -qE '^worktree .*/\.aitask-data$' \
       || git -C "$INSTALL_DIR" show-ref --verify --quiet refs/heads/aitask-data; then
        die "$root points at the aitask-data worktree, but .aitask-data/ is missing or unusable.
     Restore it, then re-run the install:
       git worktree prune && git worktree add .aitask-data aitask-data"
    fi

    # No data branch anywhere: the link resolves nowhere and nothing can be
    # written through it (e.g. a hand-built tarball that captured the repo's own
    # gitignored symlinks). Leftover state — replace it with a real directory.
    warn "Replacing dangling symlink $root -> .aitask-data/$name with a real directory"
    rm -f "$root"
}

create_data_dirs() {
    ensure_data_root aitasks
    ensure_data_root aiplans

    local d
    for d in aitasks/metadata aitasks/metadata/profiles aitasks/archived \
             aiplans/archived aireviewguides; do
        mkdir -p "$INSTALL_DIR/$d" 2>/dev/null || \
            die "Cannot create $INSTALL_DIR/$d — check for a broken symlink or permissions"
    done
}
```

**Scope:** only the two framework-owned data roots get the repair. Every other
`mkdir -p` in the install flow (`:396, 524, 601, 629, 652`) sits *below* one of
these roots and runs *after* `create_data_dirs`, so it is covered transitively.
No change to `aitask_setup.sh` — `setup_data_branch()` already self-heals a
dangling link by creating the worktree.

### New `tests/test_install_create_data_dirs.sh`

Modeled on `tests/test_setup_agent_config_seeds.sh` (the t1185 test): source
`install.sh --source-only`, use `tests/lib/asserts.sh`, one `mktemp -d` root
with an EXIT trap. Each scenario runs `create_data_dirs` in a subshell (so a
`die` cannot take the test down) with `INSTALL_DIR` set per fixture, capturing
the exit code.

| # | Fixture | Assertion |
|---|---|---|
| 1 | empty dir | exit 0; all five dirs created |
| 2 | dangling `aitasks`, no git repo / no branch | exit 0; `aitasks` is now a real dir; `metadata/profiles` + `archived` exist |
| 3 | **negative control** — same shape, bare `mkdir -p "$d/aitasks/metadata"` | exits **non-zero** (proves #2 passes because of the guard) |
| 4 | dangling `aiplans`, no evidence | exit 0; repaired |
| 5 | **real** worktree (`git init` + orphan `aitask-data` + `git worktree add .aitask-data`), then `rm -rf .aitask-data/aitasks` | exit 0; `aitasks` still `-L`; `.aitask-data/aitasks/metadata/profiles` exists |
| 6 | healthy symlink (target exists) | link preserved; dirs created through it into `.aitask-data/` |
| 7 | **evidence but not live** — worktree dir deleted, registration + `refs/heads/aitask-data` remain | exits **non-zero**; symlink still present; **no** real `aitasks/` dir created |
| 8 | **stale marker** — `.aitask-data/.git` is a garbage file | exits **non-zero**; symlink preserved (`rev-parse` fails ⇒ not live, marker ⇒ no unlink) |
| 9 | **unrecognized target** — `aitasks -> ../elsewhere/aitasks`, dangling | exits **non-zero**; symlink preserved; `../elsewhere` **not** created |
| 10 | idempotence — re-run `create_data_dirs` on the #2 fixture | exit 0; no change |

End-to-end scenario (the actual reported repro, per
`aidocs/framework/aitasks_extension_points.md` "Test the full install flow"):

11. Build a staging dir with `.aitask-scripts/`, `ait`, `seed/`, `packaging/`
    **plus** `ln -s .aitask-data/aitasks aitasks` and the `aiplans` equivalent;
    `tar czf` it (tar stores the links verbatim). `git init` a scratch install
    dir, then run
    `bash install.sh --dir "$SCRATCH" --local-tarball "$TAR" </dev/null`.
    Assert exit **0** and that the output does **not** contain
    `cannot create directory`. Harness pattern:
    `tests/test_t167_integration.sh:41-80`.

## Verification

```bash
bash tests/test_install_create_data_dirs.sh      # new test (unit + e2e)
shellcheck install.sh
# regressions in the install flow
bash tests/test_t167_integration.sh
bash tests/test_install_tarball_download.sh
bash tests/test_install_merge.sh
bash tests/test_t644_branch_mode_upgrade.sh      # branch-mode install path
```

Manual spot check of the original failure:

```bash
S=$(mktemp -d); (cd "$S" && git init -q)
# tarball with dangling aitasks/aiplans symlinks, then:
bash install.sh --dir "$S" --local-tarball /tmp/ait-dangling.tar.gz </dev/null
# expect: completes, warns about the replaced symlink, no "File exists" abort
```

Step 9 (Post-Implementation) runs the normal merge / gate / archival flow;
`risk_evaluated` is this task's only active gate.

## Risk

### Code-health risk: low
- The `rm -f` branch is now reachable only when *three* independent branch-mode
  signals are all absent and the link matches the exact framework-written form,
  so a misfire would need a repo that uses the data branch while having no
  marker, no worktree registration and no local branch ref · severity: low ·
  → mitigation: TBD (scenarios 5-9 pin every non-destructive branch)
- Five decision branches in one helper is more logic than the one-line `mkdir`
  it replaces; a wrong branch is silent until an install breaks · severity: low
  · → mitigation: TBD (each row of the table has a dedicated test)

### Goal-achievement risk: low
- None identified. The repro, the failing call site, the canonical symlink form,
  and the downstream dependency on these roots are all confirmed against the
  live source; scenario 11 exercises the real entry point
  (`install.sh --local-tarball`) rather than the helper in isolation.

## Post-Review Changes

### Change Request 1 (2026-07-21 07:52)
- **Requested by user:** The leftover-state repair logged its intent and then
  called a raw `rm -f "$root"` under the script's global `set -e`. If removal
  fails (unwritable install dir), the installer aborts on the bare `rm:` error
  instead of the `die`-with-diagnostic contract the rest of the new function
  establishes. Keep the diagnostic contract consistent.
- **Changes made:**
  - `install.sh` — `rm -f "$root" || die "Cannot replace dangling symlink $root
    — check directory permissions"`. Addressed inline rather than deferred: it
    is a one-line change inside code being written in this task, and leaving it
    would ship an inconsistent contract.
  - Added **scenario 9b** (unwritable install dir) pinning the new path: exits
    non-zero, output carries the guard's diagnostic, symlink untouched. Skipped
    under `id -u == 0`, where the permission bits do not bite.
  - **Second defect found by 9b:** the `show-ref` branch-mode probe leaked
    `fatal: not a git repository` when installing into a **non-git** directory
    (a supported install target — see `test_t167_integration.sh` Scenario E).
    Added `2>/dev/null` to match the sibling `worktree list` probe, and extended
    scenario 2 (whose fixture is deliberately not a git repo) to capture output
    and assert the probes stay silent.
- **Files affected:** `install.sh`, `tests/test_install_create_data_dirs.sh`

Test count after this iteration: **40 passed, 0 failed** (was 36).

## Final Implementation Notes

- **Actual work done:** Implemented as planned. `install.sh` gained
  `ensure_data_root()` (5-branch decision table) and a rewritten
  `create_data_dirs()` whose `mkdir -p` batch `die`s with a diagnostic instead
  of aborting bare under `set -e`. New `tests/test_install_create_data_dirs.sh`
  covers 12 scenarios / 40 assertions, including the negative control (#3), a
  case per non-destructive branch (#5-#9), and an end-to-end
  `install.sh --local-tarball` run (#11) with dangling symlinks baked into the
  tarball. Only `aitasks`/`aiplans` get the repair; `aireviewguides` was
  deliberately left out (setup never symlinks it, so the framework does not own
  its canonical target and the destructive branch would ship untested).

- **Deviations from plan:** Two additions during review, both inside the new
  code (see Post-Review Changes above): the `rm -f` failure now `die`s with a
  diagnostic, and the `show-ref` branch-mode probe got `2>/dev/null`. Scenario
  9b and an extension to scenario 2 were added to pin them, taking the count
  from the planned 11 scenarios / 36 assertions to 12 / 40.

- **Issues encountered:**
  - The test initially died at scenario 3 because `source install.sh
    --source-only` leaks the installer's file-scope `set -euo pipefail` into the
    test shell, so the deliberately-failing `mkdir -p` aborted the run. Fixed
    with `set +euo pipefail` after the source, mirroring
    `tests/test_setup_agent_config_seeds.sh:67`.
  - Scenario 9b's first version placed `2>&1` outside the command substitution,
    so `die`'s stderr was never captured — the assertion failed while the guard
    was actually correct. Fixing the capture then exposed the `show-ref` stderr
    leak, which is how that second defect was found.
  - A parallel session (t1194) was editing `install.sh` concurrently. Its hunks
    landed in `86fcebbef` before the commit, so the final staged diff needed no
    hunk surgery — but it was verified hunk-by-hunk (`git diff --cached
    install.sh | grep '^@@'` ⇒ exactly one hunk) before committing, and
    `.claude/settings.local.json` was left unstaged.

- **Key decisions:**
  - **Repair, not warn-and-skip.** Every later install step writes through these
    roots, so a warning would only move the same `set -e` abort downstream.
  - **Never unlink what might be a real layout.** `rm -f` requires *three*
    independent branch-mode signals to be absent (a `.aitask-data/.git` marker,
    a registered worktree, a local `refs/heads/aitask-data`) plus an exact match
    on the link form `setup_data_branch()` writes. Anything else is a hard error
    with a restore command — unlinking a live branch-mode symlink would silently
    redirect framework metadata off the data branch.
  - **Never materialize an unvalidated target.** The canonical-form check runs
    first and the `mkdir -p` argument is constructed locally
    (`$INSTALL_DIR/.aitask-data/<name>`), never `readlink` output, so absolute /
    `..`-bearing / custom targets cannot reach an `mkdir` or an `rm`.
  - **Live-worktree detection is the full pair** (`.git` marker **and**
    `rev-parse --is-inside-work-tree`), matching
    `commit_installed_data_files()`. A stale or copied marker therefore lands in
    the hard-error branch, never in the materialize or unlink branches.

- **Verification against independent ground truth:** `git show HEAD:install.sh`
  (pre-fix) was run against the same dangling-symlink tarball and reproduced the
  report exactly — exit 1, `mkdir: cannot create directory …: File exists`. The
  fixed installer completes and logs the repair for both roots. Regression
  suite: `test_install_create_data_dirs` 40/40, `test_install_tarball_download`
  28/28, `test_install_merge` 37/37, `test_t167_integration` 17/17,
  `test_t644_branch_mode_upgrade` 16/16, `test_seed_manifest_drift` 28/28
  (t1194's guard, re-run because it shares the file). `shellcheck` clean on the
  new code; the three pre-existing `install.sh` findings are on untouched lines.

- **Upstream defects identified:** None. The one sibling candidate was checked
  and cleared: `aitask_setup.sh` `setup_draft_directory()` also runs an
  unguarded `mkdir -p "$project_dir/aitasks/new"`, but it is ordered *after*
  `setup_data_branch()` (`aitask_setup.sh:3487` vs `:3490`), which materializes
  the worktree and so self-heals a dangling link before that call is reached.
  The `install.sh` shellcheck findings (SC2295, SC2043, SC1091) are style/lint
  and out of scope.
