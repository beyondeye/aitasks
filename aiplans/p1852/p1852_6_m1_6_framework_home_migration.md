---
Task: t1852_6_m1_6_framework_home_migration.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-07 22:11
---

# Plan: t1852_6 — M1.6 Framework home report and migration

## Context

M1.6 of the test-map M1 module (wave H). It delivers `ait engine home
[--migrate]`. This is the explicit verb that reports the legacy per-user root
`~/.aitask/` and moves its tenants into `$AITASKS_HOME` (default `~/.aitasks`),
leaving `~/.aitask -> $AITASKS_HOME` behind. `ait setup` only prints a
`HOME_LEGACY:` hint and never migrates. Flipping the default (reserving
`--no-home-migration` / `AIT_HOME_MIGRATE=0`) is a named follow-up, not v1.
Providers: M1.1 (t1852_1: `lib/aitasks_home.sh`, `AITASKS_HOME_LOCK`) and
M1.5 (t1852_5: `aitask_engine.sh`, `lib/engine_install.sh`), both landed.

Spec: `aidocs/testing_engine/n014_explorer_006_proposal.md`, component
*Framework home report and migration verb (M1.6)* (line ~2056),
`assumption_home_symlink_compatibility` / `assumption_legacy_user_root_coexists`
(~3199), and `tradeoff_two_user_roots` / `tradeoff_split_home_rejected` /
`tradeoff_home_migration_window` (~3672).

## Step 0 — Reality check (outcome, recorded 2026-10-06, main @ a796455b9)

Landed state: `aitask_engine.sh` (t1852_5, 7f412d482) dispatches
`build|test|cross|prune` and carries the placeholder comment
`# home [--migrate] — M1.6 (t1852_6) adds this arm`. `home` currently falls to
`UNKNOWN_VERB`, exit 64, which test E3 in
`tests/test_install_engine_binary.sh:648` pins. `lib/aitasks_home.sh` (t1852_1)
exports `AITASKS_HOME` and `AITASKS_HOME_LOCK=$AITASKS_HOME/.home.lock`, and
nothing takes that lock yet. The grep guard in `tests/test_aitasks_home.sh` T9
scans `aitask_engine.sh` whole and exempts only per-line `# legacy-root-ok:`
markers. After setup, `$AITASKS_HOME/` contains `engine/`, plus
`engine/.locks/` and `engine/v<V>/` once an engine has been installed.

| # | proposal / coarse plan says | repository has | decision |
|---|---|---|---|
| D1 | migration runs "under `flock $AITASKS_HOME/.home.lock`" | `flock` is used nowhere in the tree and is not on stock macOS. The framework's only mutex protocol is `lib/stale_lock.sh` (mkdir lock + `.gc` guard, dead-PID reclaim), already sourced through `engine_install.sh` | **adapt**: take `$AITASKS_HOME_LOCK` with `stale_lock_acquire` (a short retry budget, then refuse `busy`). Fix the lib comment "Taken (flock)" to match, and edit the proposal's component text |
| D2 | "8 framework files / 35 references" to `~/.aitask` | 37 lines in 10 files (29 non-comment lines in 7 files: `aitask_setup.sh` 19, `python_resolve.sh` 3, `aitask_path.sh` 2, and 1 each in `ait`, `aitask_upgrade.sh`, `aitask_codemap.sh` and `claude_hook_status.sh`). No Python file names it | **adapt**: the counts are measurement drift. Correct them in the proposal's assumption and tradeoff text |
| D3 | "no `==`, `-ef`, `realpath`, `samefile` on the home path anywhere" | `lib/claude_hook_status.sh:141` (t1849, 54ed4f620) has `[[ "$py3" == "$HOME/.aitask/bin/python3" ]]`. `$py3` is `command -v python3`, so this compares PATH spellings, and PATH keeps the literal `$HOME/.aitask/bin` entry after migration, so the comparison still matches. It only picks a hint string | **adapt**: the assumption still holds in effect. Record the exception in the proposal's assumption text |
| D4 | known set `{venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine}` | the tenants are re-derived from the scripts: `venv`, `python`, `bin`, `uv`, `dev_tier` (setup), `pypy_venv` (`python_resolve.sh` / setup) and `update_check` (`ait`, `aitask_upgrade.sh`). Nothing writes `~/.aitask/engine` today. This host has the 7 tenants and no `engine` | **keep** the set unchanged (`engine` stays, and after setup it always hits `destination-exists:engine`). No proposal edit needed |
| D5 | the window is sub-millisecond, between `rmdir` and `ln -s` | the window runs from the **first `mv`** to `ln -s`. That is still renames-only, so it lasts milliseconds. Any concurrent `ait` command's `check_for_updates` runs `mkdir -p ~/.aitask` and writes `update_check`. Inside the window that can drop a new file into the legacy root (so `rmdir` fails) or recreate the directory (so `ln -s` creates a link *inside* it) | **adapt**: fail closed. Verify every step after it runs (inode identity per move, `-L` + readlink after the link), roll back on any mismatch, and report. Correct the tradeoff text in the proposal |
| D6 | refusal reasons: `no-legacy-root`, `already-migrated`, `foreign-symlink:<t>`, `cross-device`, `unknown-entry:<n>`, `destination-exists:<n>` | the edges found need more: the lock is held; `AITASKS_HOME` is relative, not normalized, equal to the legacy root, inside it (also through a symlinked ancestor) or containing it; the legacy path is not a directory; an entry is on another device; the D5 races; and a catchable signal mid-migration | **adapt**: add `busy`, `lock-unavailable`, `root-not-absolute`, `root-not-normalized`, `same-root`, `root-inside-legacy`, `legacy-inside-root`, `legacy-not-a-directory`, `cross-device:<name>`, `legacy-root-not-empty:<names>`, `symlink-failed`, `move-failed:<name>` and `interrupted:<SIG>`, plus `HOME_ROLLED_BACK:<n>`, `HOME_FAILED:rollback|<names>` and `HOME_STRANDED:<name>|<now>|<legacy>`. Add them to the proposal's component text |
| D7 | t1852_5's note: treat live engine slot locks as busy; slot writers should refuse during a migration | the migration never touches `$AITASKS_HOME/engine`. The only overlap is a *legacy* `engine` entry, which preflight refuses whenever `$AITASKS_HOME/engine` exists. If the directory appears between the check and the `mv`, the inode check catches the resulting nesting | **decline** the slot-lock coupling: the migration and slot writers never touch the same directory, and the race left is caught after the fact and rolled back. `lib/engine_install.sh` is unchanged |
| D8 | "through a real `install.sh --dir` where a case needs a populated legacy root" | `install.sh` writes nothing under `~/.aitask/`, so fixtures populate the legacy root. A real install is still the honest way to get a real `$AITASKS_HOME/engine/v<V>/` and an installed `aitask_engine.sh` | **adapt**: one case (H-I) runs the *installed* tree's `ait engine home --migrate` after a real `install.sh --dir --local-tarball --local-engine` |

Downstream notes: the named follow-up that flips the default has no task yet
(only t1852 and this child mention it), so there is nothing to note. Files
touched are owned here or are named extensions: the `home` arm, a setup hint
function, the migration cases in `test_aitasks_home.sh`, and E3 (whose update
t1852_5's note hands to this task). There are also comment/doc-only edits to
`lib/aitasks_home.sh`, the proposal, `CLAUDE.md` and the `ait` help line.

## Implementation steps

### 1. `.aitask-scripts/aitask_engine.sh` — the `home` arm

- Header: add the `home [--migrate]` verb to the help block, and widen the
  `-h` `sed -n '4,18p'` range to match. Add interface rows for every
  `HOME_*` shape, each pinned by an `H*` case in `tests/test_aitasks_home.sh`.
  Add `| home [--migrate]` to `usage_line`.
- One spelling of the legacy root, marked for the T9 guard:
  ```bash
  LEGACY_ROOT="$HOME/.aitask"  # legacy-root-ok: the one spelling of the root `home --migrate` empties
  HOME_KNOWN_ENTRIES=(venv pypy_venv python bin uv dev_tier update_check engine)
  ```
  Every other line uses `$LEGACY_ROOT`, so no other line needs a marker.
- Small helpers:
  - `home_entries`: every entry of the legacy root, dotfiles included, by
    name, `LC_ALL=C` sorted.
  - `home_lstat <fmt> <path>`: `stat -c` (GNU) else `stat -f` (BSD), without
    `-L`, for `%d` / `%i`.
  - `home_root_dev`: `engine_dev_id` of `$AITASKS_HOME`, or of its nearest
    existing ancestor when it does not exist yet.
- `home_resolve_root`: the physical path `$AITASKS_HOME` *will* have,
  computed **before anything is created**:
  - Refuse `root-not-normalized` when the path has a `.`, `..` or empty
    (`//`) component, because the lexical remainder below must not reinterpret
    them.
  - Walk up to the nearest existing ancestor, take its physical path
    (`cd -P … && pwd -P`, which follows every symlink in the existing part),
    and append the not-yet-existing remainder.
  - An existing `$AITASKS_HOME` resolves wholly through `cd -P`.

  The legacy root's physical path comes from `cd -P` too.
- `home_preflight`: read-only. It sets `HOME_STATE` (`none`, `migrated`,
  `refuse` or `ready`), `HOME_REASONS[]` and `HOME_MOVE[]`, checking in this
  order:
  1. `$AITASKS_HOME` not absolute → `root-not-absolute`. Not normalized →
     `root-not-normalized`.
  2. Legacy root is a symlink → `already-migrated` when it `-ef`s
     `$AITASKS_HOME`, else `foreign-symlink:<readlink>`.
  3. Absent → `no-legacy-root`. Not a directory → `legacy-not-a-directory`.
  4. Compare the **resolved** root with the legacy root's physical path:
     equal → `same-root`; the root under the legacy root →
     `root-inside-legacy`; the legacy root under the root →
     `legacy-inside-root`. Because the comparison uses the resolved path, a
     symlinked ancestor aliasing into the legacy tree (for example an outside
     `link -> ~/.aitask/venv`, with `AITASKS_HOME=<outside>/link/sub`) is
     refused by the **first, unlocked** preflight, before any `mkdir`.
  5. Legacy root device ≠ `home_root_dev` → `cross-device`.
  6. For each entry: not in the known set → `unknown-entry:<n>`.
     `$AITASKS_HOME/<n>` exists or is a symlink → `destination-exists:<n>`.
     The entry's lstat device ≠ the legacy root's → `cross-device:<n>` (a
     mount point would turn `mv` into a copy). Otherwise append it to
     `HOME_MOVE`.

  Every failing entry is collected, not just the first, so the user fixes
  everything in one pass.
- `ait engine home` (report, lock-free, changes nothing, exit 0) prints:
  - `HOME_ROOT:<AITASKS_HOME>`
  - `HOME_LEGACY:<legacy>|<csv of entries or (empty)>`, or `HOME_LEGACY:none`
    when the legacy root is not a real directory
  - `HOME_SYMLINK:none|<readlink target>`
  - `HOME_NEXT:migrate|<n>|<csv>`, `HOME_NEXT:none|<no-legacy-root|already-migrated>`,
    or one `HOME_NEXT:refuse|<reason>` line per reason
- `ait engine home --migrate`:
  1. Unlocked preflight. `none` or `migrated` → `HOME_SKIPPED:<reason>`,
     exit 0, and **nothing is created** (`$AITASKS_HOME` is not created
     either). `refuse` → one `HOME_SKIPPED:<reason>` line per reason, exit 1.
  2. `mkdir -p "$AITASKS_HOME"` (the lock lives inside it), then
     `stale_lock_acquire "$AITASKS_HOME_LOCK" 3 0.1 "framework home migration"`.
     Failure prints `HOME_SKIPPED:busy` when the lock dir exists, else
     `HOME_SKIPPED:lock-unavailable`, exit 1. Release on every exit path, with
     an EXIT trap as backstop.
  3. Preflight again **under the lock**. Any refusal → `HOME_SKIPPED:*`,
     exit 1, nothing moved. Record every `HOME_MOVE` entry's lstat inode now
     (`HOME_INODE[n]`), before anything moves.
  4. **Phase-aware interruption handling.** `HOME_PHASE` moves through
     `locked` → `moving` → `removed` (after `rmdir`) → `linked` (after the
     link is verified). `trap 'home_on_signal INT' INT`, and likewise for TERM
     and HUP, is installed right after the lock is taken. `home_on_signal`:
     - Ignores further INT/TERM/HUP first, so its own recovery cannot be
       interrupted half-way.
     - `locked`: nothing has moved → `HOME_SKIPPED:interrupted:<SIG>`.
     - `moving` or `removed`: the migration is **incomplete**, so cancel it.
       Recreate the legacy root if `rmdir` already removed it, run
       `home_rollback`, and report `HOME_SKIPPED:interrupted:<SIG>` +
       `HOME_ROLLED_BACK:<n>`, or `HOME_FAILED:rollback|…` as below.
     - `linked`: the migration is **complete**, and the signal only ends the
       command → `HOME_MIGRATED:<n>`. Nothing is undone.

     Then exit 128+signo (130 / 143 / 129). The EXIT trap still releases the
     lock on every path. SIGKILL and power loss are out of scope.
  5. Move each `HOME_MOVE` entry:
     - Re-check that the destination is absent (`destination-exists:<n>` →
       roll back).
     - **Then** call the test seam `pre-mv <n>`. It runs after the final
       absence check and immediately before the `mv`, so an injection there
       reaches the nested-move recovery and not the ordinary refusal.
     - Run `mv -n -- "$LEGACY_ROOT/$n" "$AITASKS_HOME/$n"`.
     - Verify that the source is gone and the destination's lstat inode equals
       `HOME_INODE[n]`. If the destination appeared meanwhile and the entry
       nested into `$AITASKS_HOME/$n/$n` (matched by inode), roll back as
       `destination-exists:<n>`. Any other mismatch → `move-failed:<n>` and
       roll back.
  6. Test seam `AIT_HOME_TEST_HOOK=<exe>`, set only by tests and mirroring the
     `AIT_ENGINE_TEST_*` seams. It is called as `<exe> pre-mv <name>`,
     `<exe> post-moves`, `<exe> pre-link` and `<exe> post-link`. A hook can
     also signal its
     parent (`kill -TERM "$PPID"`). Bash runs the trap as soon as the hook
     returns, which makes the interruption cases deterministic.
  7. `rmdir "$LEGACY_ROOT"`. Failure → roll back as
     `legacy-root-not-empty:<csv of what is there now>`.
  8. `ln -s "$AITASKS_HOME" "$LEGACY_ROOT"`, then verify `-L` and that
     `readlink` equals `$AITASKS_HOME`. On failure:
     - If the legacy root was recreated as a directory, remove only the stray
       link `ln` placed inside it (a symlink whose readlink equals
       `$AITASKS_HOME`).
     - `mkdir` the legacy root if it is missing, roll back, and report
       `symlink-failed`.
  9. Success sets `HOME_PHASE=linked`, prints `HOME_MIGRATED:<n>` and exits 0.
- `home_rollback` is **derived from state, not bookkeeping**, so an
  interruption landing between a `mv` and its record is still covered. For
  every `HOME_MOVE` entry, in reverse:
  - Locate the entry by inode: already at `$LEGACY_ROOT/$n` → in place;
    at `$AITASKS_HOME/$n` or nested at `$AITASKS_HOME/$n/$n` → move it back.
  - A competing `$LEGACY_ROOT/$n` that is *not* our inode marks the entry
    **stranded**. It is never overwritten.
  - Run `mv -n` back and verify the inode.

  Fully restored → `HOME_SKIPPED:<reason>` + `HOME_ROLLED_BACK:<n>`, exit 1.
  Anything stranded → `HOME_FAILED:rollback|<csv>`, plus one
  `HOME_STRANDED:<name>|<current path>|<legacy path>` line per stranded entry
  and a `warn` giving the manual restore (inspect the competing
  `<legacy path>`, then `mv <current path> <legacy path>`), exit 2. Competing
  entries are preserved untouched.
- Dispatcher: replace the placeholder comment with `home) cmd_home "$@" ;;`.
  Arguments other than none or `--migrate` → `usage_line`, exit 64.
- Every legacy-root command lives in its own function, so `set -euo pipefail`
  behaviour is explicit. Each fallible command is checked with `|| rc=$?`
  (shell_conventions).

### 2. `.aitask-scripts/aitask_setup.sh` — the `HOME_LEGACY:` hint

- New function `report_home_legacy`, defined next to `setup_aitasks_home`:
  ```bash
  report_home_legacy() {
      local out line
      out="$(bash "$SCRIPT_DIR/aitask_engine.sh" home 2>/dev/null)" || return 0
      line="$(printf '%s\n' "$out" | grep '^HOME_LEGACY:' | grep -v '^HOME_LEGACY:none$' | grep -v '|(empty)$')" || return 0
      info "  $line"
      info "    Run 'ait engine home --migrate' to move these into $AITASKS_HOME (optional)."
  }
  ```
  It reads the report only, so setup never migrates and never spells the
  legacy path itself. The report stays the single owner of the tenant list.
- In `main()`'s summary, call `report_home_legacy` right after the
  `AITASKS_HOME:` line, which keeps T8's "AITASKS_HOME: is right after Python
  venv:" invariant.

### 3. `tests/test_aitasks_home.sh` — migration cases (named extension)

- Register `aitask_setup.sh:report_home_legacy` in `FEATURE_FUNCTIONS`.
  T9 must still pass with the one marked `LEGACY_ROOT=` line in the engine
  script.
- Fixtures:
  - `mklegacy <home>` builds every known entry (`engine` optional):
    - `venv/`: a **real** `python3 -m venv --without-pip`, skipped with a
      note when that is unavailable.
    - `pypy_venv/bin/python` (a stub script).
    - `python/3.x/bin/python3`, a symlink to the real `python3`.
    - `bin/python3`, a wrapper that execs
      `"$HOME/.aitask/python/3.x/bin/python3"`.
    - `uv/uv`, `dev_tier`, `update_check`.
    - `engine/vX/ait-testmap`.
  - `tree_sig <dir>`: a portable byte-identity signature (`find` + `cksum`
    for files, `readlink` for links, the directory list; `LC_ALL=C` sorted)
    used for "both trees unchanged".
  - `home_eng`: runs `aitask_engine.sh` with a scratch `HOME`, optional
    `AITASKS_HOME` and extra env.
- Cases:
  - **H1**: report with no legacy root (`HOME_LEGACY:none`,
    `HOME_SYMLINK:none`, `HOME_NEXT:none|no-legacy-root`, exit 0).
  - **H2**: report on a populated root (tenant csv, `HOME_NEXT:migrate|8|…`,
    both signatures unchanged, no `.home.lock` created).
  - **H3**: report on a refusing root (`HOME_NEXT:refuse|unknown-entry:junk`).
  - **H4**: `--migrate` with no legacy root → `HOME_SKIPPED:no-legacy-root`,
    exit 0, `$AITASKS_HOME` not created.
  - **H5**: `destination-exists:engine` with a pre-created
    `$AITASKS_HOME/engine/` holding a file → exit 1, both signatures
    byte-identical, no symlink.
  - **H6**: `unknown-entry:<n>` with both trees intact.
  - **H7**: hostile pre-existing symlink `~/.aitask -> elsewhere` →
    `foreign-symlink:<target>`, with the link and `elsewhere` unchanged.
  - **H8**: `cross-device`, using `/dev/shm` as `AITASKS_HOME` when its device
    differs from the scratch dir. Otherwise `SKIP (no second filesystem)`,
    never counted as a pass.
  - **H9**: `busy`. A live holder process takes the lock through
    `stale_lock_acquire`, signals a ready file and sleeps. Expect
    `HOME_SKIPPED:busy` and nothing moved. Then kill the holder.
  - **H10**: `same-root` (`AITASKS_HOME=$HOME/.aitask`) and
    `root-not-absolute`.
  - **H11**: full known-set move into an **`AITASKS_HOME` override** that does
    not exist yet, `pypy_venv` and `engine` included:
    - `HOME_MIGRATED:8`, exit 0.
    - `~/.aitask` is a symlink whose readlink equals the override.
    - Every entry is in the override and the legacy signature equals the
      override's.
    - No `.home.lock` is left behind.
    - Symlink compatibility holds: `~/.aitask/venv/bin/python -c 'print(42)'`
      runs, a script with the absolute shebang `#!$HOME/.aitask/venv/bin/python`
      runs, and the `bin/python3` wrapper runs.
  - **H12**: default `AITASKS_HOME` (env unset) with 7 entries →
    `HOME_MIGRATED:7` into `$HOME/.aitasks`. The report then shows
    `HOME_SYMLINK:<root>` and `HOME_NEXT:none|already-migrated`.
  - **H13**: idempotent re-run → `HOME_SKIPPED:already-migrated`, exit 0,
    signature unchanged.
  - **H14**: rollback on `rmdir`. The hook `post-moves` drops `stray` into the
    legacy root. Expect `HOME_SKIPPED:legacy-root-not-empty:stray` and
    `HOME_ROLLED_BACK:8`, exit 1. The legacy signature equals the original
    plus `stray`, the `AITASKS_HOME` signature is unchanged and no lock dir is
    left.
  - **H15**: symlink race. The hook `pre-link` recreates the legacy directory.
    Expect `symlink-failed`, no stray link inside, and both trees restored.
  - **H16**: nesting race. The hook `pre-mv venv`, which runs **after** the
    final absence check, creates `$AITASKS_HOME/venv` holding a marker file.
    The `mv` then really nests. Expect `destination-exists:venv` and
    `HOME_ROLLED_BACK:`; the legacy signature restored; the competing
    `$AITASKS_HOME/venv` (with its marker) preserved; no `venv/venv` left; and
    no lock dir. A control with the hook made a no-op and the destination
    pre-created instead must report the plain preflight
    `destination-exists:venv` with **no** `HOME_ROLLED_BACK:`. That proves H16
    reaches the recovery path and not the refusal.
  - **H17**: `home --bogus` → exit 64.
  - **H18**: destination aliasing. An outside `link -> $HOME/.aitask/venv`
    and `AITASKS_HOME=<outside>/link/sub` (not existing) →
    `HOME_SKIPPED:root-inside-legacy`, exit 1. The legacy signature is
    byte-identical (no `venv/sub` created) and no lock dir exists anywhere.
    Also `root-not-normalized` for a path with a `..` component, and
    `legacy-inside-root` for `AITASKS_HOME=$HOME`.
  - **H19**: interruption after a move. The hook `pre-mv bin` runs
    `kill -TERM $PPID`, after some entries have moved and before `bin` moves.
    Expect `HOME_SKIPPED:interrupted:TERM` and `HOME_ROLLED_BACK:`, exit 143.
    The legacy signature equals the original, `$AITASKS_HOME` holds no
    moved entry, `~/.aitask` is a real directory and no lock dir is left.
    A sibling run sends INT (exit 130) and expects the same result.
  - **H20**: interruption after `rmdir`, before linking. The hook `pre-link`
    sends TERM. Expect the legacy root recreated and every entry restored
    (signature equal), with no symlink and no lock dir.
  - **H21**: interruption after the link. The hook `post-link` (which runs
    after the link is verified and `HOME_PHASE=linked` is set) sends TERM.
    Expect `HOME_MIGRATED:8`, the symlink kept, every entry still in
    `$AITASKS_HOME`, nothing undone and no lock dir. This is the
    complete-versus-incomplete distinction.
  - **H22**: rollback obstruction (forced `HOME_FAILED:rollback`). The hook
    `post-moves` creates `$LEGACY_ROOT/stray`, so `rmdir` fails, and a
    competing `$LEGACY_ROOT/venv/` with a marker file. Expect, with exit 2:
    - `HOME_FAILED:rollback|venv` and
      `HOME_STRANDED:venv|$AITASKS_HOME/venv|$HOME/.aitask/venv`.
    - The warn text naming the manual `mv`.
    - Every other entry restored into the legacy root.
    - The original venv intact at `$AITASKS_HOME/venv` (same signature).
    - The competing legacy `venv/` and `stray` preserved untouched.
    - No lock dir left.
  - **H-I** (real install):
    - Run `install.sh --dir <t> --local-tarball <tarball> --local-engine <fake>`
      with a scratch HOME, which gives a real `$HOME/.aitasks/engine/v<V>/`.
      This reuses the tarball and fake-engine shape of
      `test_install_engine_binary.sh`.
    - With a legacy root that has `engine`, run
      `<t>/ait engine home --migrate` →
      `HOME_SKIPPED:destination-exists:engine` and both signatures unchanged.
    - Remove the legacy `engine` and run it again → `HOME_MIGRATED:7`, with
      `$HOME/.aitask/venv/bin/python` still running.
  - **S1**: setup `main()` with `report_home_legacy` un-stubbed (run_main
    gains a keep-list) and a populated legacy root. The `HOME_LEGACY:` hint
    line comes right after the `AITASKS_HOME:` summary line, and the legacy
    signature is unchanged (setup never migrates).
  - **S2**: no legacy root → no `HOME_LEGACY:` line.
  - **S3**: already migrated (symlink) → no hint.
- The file's bodies run in the main shell (no `( … )` subshells), so the
  t1207 counter opt-in is not needed. Keep it that way.

### 4. `tests/test_install_engine_binary.sh` — E3

Replace the "home is not an M1.5 verb → 64" assertion with
`eng home` under a scratch HOME → exit 0 plus a `HOME_ROOT:` line, and keep
`home --bogus` → 64.

### 5. Comment / doc touch-ups

- `lib/aitasks_home.sh`: change the lock comment "Taken (flock)" to
  "Taken (stale_lock mutex)". This is comment-only, and T10's
  no-`.aitask/` check stays green.
- Proposal: correct the component text (D1, D6), the assumption text
  (D2, D3) and the tradeoff text (D2, D5). Current-state wording only.
- `CLAUDE.md` Engine section: add the line
  `ait engine home [--migrate]  # report / move the legacy ~/.aitask root into $AITASKS_HOME`.
- `ait` help line 79: add "and migrate the per-user home".

## Verification

- `bash tests/test_aitasks_home.sh` and `bash tests/test_install_engine_binary.sh`
  both report ALL TESTS PASSED.
- `shellcheck .aitask-scripts/aitask_engine.sh .aitask-scripts/aitask_setup.sh`
  is clean.
- Manual check on a scratch HOME, as the task's Verification section asks: a
  populated legacy root plus a pre-created `$AITASKS_HOME/engine/` →
  `HOME_SKIPPED:destination-exists:engine`, with `diff -r` of both trees
  before and after empty. After removing the collision the migration
  completes, `~/.aitask` is a symlink and `~/.aitask/venv/bin/python` runs.
  H5, H11 and H-I cover this, and it is repeated once by hand.
- Never run `--migrate` against the real `~/.aitask` during implementation.
  Every case uses a scratch `HOME`.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9. Current-branch
profile: no worktree, no merge.

## Risk

### Code-health risk: medium
- The new verb renames entries inside the user's real `~/.aitask`, the
  directory holding the venv and Python every `ait` command runs on. A defect
  in the move/verify/rollback sequence could leave a half-migrated home. Bounded
  by: an explicit verb only, a full preflight (resolved-path aliasing
  included) before any `mkdir` or move, per-move inode verification,
  state-derived rollback, INT/TERM/HUP recovery tracked by phase, explicit
  `HOME_FAILED` / `HOME_STRANDED` output with manual restore steps, and every
  test on a scratch HOME. SIGKILL and power loss mid-move still leave a split
  home, which a later run refuses as `destination-exists` without repairing
  it · severity: medium · → mitigation: t1931
- Signal recovery that tracks phases adds state (`HOME_PHASE`,
  `HOME_INODE[]`) and trap code to a `set -euo pipefail` script. It is kept
  readable by making rollback derive from on-disk inodes rather than from
  move bookkeeping, and is pinned by H19–H22 · severity: low · → mitigation: none
- Test seams (`AIT_HOME_TEST_HOOK`) and extra refusal reasons widen the
  verb's surface beyond the proposal's six reasons. Kept bounded by the
  header interface table, where each shape is pinned by a named case · severity: low · → mitigation: none

### Goal-achievement risk: low
- BSD/macOS behaviour (`stat -f`, `mv -n`, `ln -s` onto a recreated directory)
  is coded for but only exercised on Linux here, and the cross-device case
  skips on a single-filesystem host · severity: low · → mitigation: t1931

### Planned mitigations
- timing: after | name: real_host_migration_check | type: manual_verification | priority: medium | effort: low | inline_risk: medium | added_complexity: low | addresses: real-home half-migration risk (code-health) and untested BSD/macOS behaviour (goal-achievement) | desc: Run `ait engine home --migrate` on a real Linux host and a macOS host (macOS also runs tests/test_aitasks_home.sh); then confirm ait board (PyPy venv), ait monitor, ait setup and ait upgrade keep working through the ~/.aitask symlink | created: t1931

## Post-Review Changes

### Change Request 1 (2026-10-08 00:20)
- **Requested by user:** five review findings, all verified valid:
  1. A relative top-level symlink (`venv -> ../external`) migrates silently with a changed target.
  2. A rollback `mv -n` can nest the original inside a competitor that appears after the check; `home_locate` never looked there, so `HOME_STRANDED` named the wrong place.
  3. The manual-restore advice (`mv <now> <legacy>`) would nest the original inside the competitor.
  4. A trailing-slash `AITASKS_HOME` produced an empty basename, so symlink-failure cleanup missed the stray link.
  5. Newline-split entry enumeration let `venv` + LF read as a known entry.
- **Changes made:**
  1. The preflight scans every symlink in the legacy tree (`find -type l -print0`) and refuses `relative-symlink:<path>` when a relative target, resolved lexically from the link's directory, leaves the root. Relative links that stay inside the root still migrate.
  2. `home_locate` gains a `legacy-nested` location. The rollback re-locates each entry after its `mv` and reports where it actually is. There is a new test seam, `pre-restore <name>`, which runs after the rollback's absence check.
  3. Each stranded entry gets two runnable `HOME_RESTORE:<name>|<command>` lines (`printf %q`-quoted). The first sets the competitor aside at a non-existing `<legacy>.competing[.N]`; the second moves the original into place, re-pathed when it was nested inside the competitor.
  4. `cmd_home` normalizes trailing slashes off `AITASKS_HOME` once, for the whole verb.
  5. `home_entries` is NUL-terminated (`sort -z`, `read -d ''`), and names with control characters are `%q`-escaped in protocol lines (`home_show`). `tree_sig` in the test is NUL-safe as well.
- **Tests:**
  - H22 now executes the printed restore steps and checks that the original is restored and the competitor kept.
  - New cases: H23 (reverse nesting during rollback, reported and restorable), H24 (newline name refused before any move), H25 (escaping relative links refused, top-level and nested; inner relative links migrate and resolve), and a trailing-slash H15 variant.
  - Each fix was mutation-tested in an isolated copy, and its case fails when the fix is removed.
  - Suites: `test_aitasks_home.sh` 200/200, `test_install_engine_binary.sh` 201/201. The real host report still shows `HOME_NEXT:migrate|7|…` (no false relative-link refusal).
- **Files affected:** `.aitask-scripts/aitask_engine.sh`, `tests/test_aitasks_home.sh`, `aidocs/testing_engine/n014_explorer_006_proposal.md`

### Change Request 2 (2026-10-08 00:45)
- **Requested by user:** three findings, all verified valid:
  1. The link scan ignored `find`'s exit status and `readlink` failures, so an unreadable directory could hide an outward relative interpreter link and the migration would still succeed.
  2. When the legacy root itself was replaced by a file, the printed restore steps failed ("Not a directory").
  3. A signal between `ln` and the phase advancing reported `HOME_ROLLED_BACK:0` for a completed migration. The reviewer marked this one as follow-up; it was done inline because the fix is small and contained.
- **Changes made:**
  1. `find`'s exit status rides along as a trailing NUL `FIND_RC:` sentinel record, which cannot collide because real records start with the absolute legacy path. A non-zero status refuses `scan-incomplete`, and an unreadable link target refuses `scan-incomplete:<path>`, both before any `mkdir` or move.
  2. When the legacy root is not a directory at rollback time, `home_restore_root_steps` prints the restore steps in order: the obstruction set aside (`HOME_RESTORE:.|mv …`), `mkdir` of the root, then one `mv` per entry. The per-entry two-step form stays for per-entry competitors. A shared `home_aside` helper picks the aside name.
  3. `home_on_signal` recognises a completed layout (the legacy root is a symlink whose readlink equals `$AITASKS_HOME`) while still in the `removed` phase, and reports `HOME_MIGRATED`. `home_locate` never treats a path through a symlinked legacy root as "back". There is a new `post-ln` seam.
- **Tests:**
  - H26: an unlistable `venv/hidden` directory holding an outward link is refused `scan-incomplete`, with nothing created. It is skipped when running as root.
  - H27: the legacy root replaced by a file before linking gives exit 2; running the printed steps restores the tree byte-identically and keeps the obstruction aside.
  - H28: TERM at `post-ln` reports `HOME_MIGRATED:8` and nothing is undone.
  - The test's EXIT trap now runs `chmod -R u+rwx` before `rm -rf`.
  - All three fixes were mutation-tested (each case fails without its fix). Suites: `test_aitasks_home.sh` 220/220, `test_install_engine_binary.sh` 201/201.
- **Files affected:** `.aitask-scripts/aitask_engine.sh`, `tests/test_aitasks_home.sh`, `aidocs/testing_engine/n014_explorer_006_proposal.md`

### Change Request 3 (2026-10-09 00:10)
- **Requested by user:** one finding, verified valid. `home_restore_root_steps` always printed a "set the legacy root aside" `mv`. When the rollback's own `mkdir` had failed (for example, the parent is not writable), the root was absent and that first step failed.
- **Changes made:** the set-aside step is printed only when `home_present "$LEGACY_ROOT"`. An absent root starts with `mkdir`, then the per-entry moves. The warning now distinguishes "replaced (obstruction kept aside)" from "missing and could not be recreated (check the parent is writable)".
- **Tests:** H29. The `pre-link` hook removes the parent's write permission. Expected: exit 2, the originals intact in the new root, a first step of `mkdir` with no `.competing` step, and the "missing" warning. Once the parent is writable again, the printed steps restore the legacy tree byte-identically. It is skipped when running as root. Mutation-tested (an always-printed aside step fails H29). Suites: `test_aitasks_home.sh` 229/229, `test_install_engine_binary.sh` 201/201.
- **Files affected:** `.aitask-scripts/aitask_engine.sh`, `tests/test_aitasks_home.sh`, `aidocs/testing_engine/n014_explorer_006_proposal.md`

### Change Request 4 (2026-10-09 00:30)
- **Requested by user:** one finding, verified valid. `home_restore_steps` always printed "set the legacy entry aside", even when the legacy path was free because the move back itself had failed (a read-only legacy directory). The first printed command then failed.
- **Changes made:**
  - The aside step is printed only when `home_present` finds something at the legacy entry path. A free path gets a single `mv <current> <legacy>`, and its warning says the move failed (check the legacy directory is writable) rather than naming a competitor.
  - The full state space was then checked so this class is closed:
    - **Legacy root:** a directory, an obstruction, or absent.
    - **Entry path:** free or occupied.
    - **Original location:** `AH/n`, `AH/n/n`, `legacy/n/n` or lost.

    Every reachable combination now prints steps that start from the real state.
- **Tests:** H30. The `post-moves` hook adds a competing `update_check` and makes the legacy directory read-only, so every entry is stranded.
  - Expected: a free path gets one step and the occupied `update_check` gets two, with both warnings present.
  - Once the directory is writable again, every printed step runs, the competitor is kept aside, and the legacy tree is restored byte-identically.
  - It is skipped when running as root. Mutation-tested: an always-printed aside fails H30.
  - Suites: `test_aitasks_home.sh` 240/240, `test_install_engine_binary.sh` 201/201.
- **Files affected:** `.aitask-scripts/aitask_engine.sh`, `tests/test_aitasks_home.sh`, `aidocs/testing_engine/n014_explorer_006_proposal.md`

## Final Implementation Notes
- **Actual work done:**
  - `ait engine home` is a lock-free, read-only report (`HOME_ROOT`, `HOME_LEGACY`, `HOME_SYMLINK`, `HOME_NEXT`).
  - `ait engine home --migrate` runs:
    - an unlocked preflight that creates nothing;
    - `mkdir -p` of the root, then the `$AITASKS_HOME_LOCK` stale_lock mutex;
    - a second preflight under the lock, then the dev:inode identity of each entry is recorded;
    - per-entry `mv -n`, each verified by inode;
    - `rmdir`, then `ln -s`, verified by `readlink`.
  - Any failure after the first move, or INT/TERM/HUP before the link is verified, triggers a state-derived rollback. A blocked rollback prints `HOME_FAILED` / `HOME_STRANDED` and runnable `HOME_RESTORE` steps.
  - Setup gained `report_home_legacy`, which echoes the report's `HOME_LEGACY:` line after `AITASKS_HOME:` and never migrates.
  - `tests/test_aitasks_home.sh` gained H1–H30, H-I (a real `install.sh --dir`) and S1–S3: 240 assertions in total, about 6 s.
  - E3 in `tests/test_install_engine_binary.sh` now pins `home` as a verb.
  - Comment and documentation touch-ups: `lib/aitasks_home.sh`, the proposal (component, assumption and tradeoff text), CLAUDE.md, and the `ait` help line.
- **Deviations from plan:**
  - All D1–D8 decisions in Step 0 held.
  - H19 interrupts at `pre-mv python`, not `bin`: `bin` sorts first, so nothing has moved yet at that point.
  - Seam points ended up as `pre-mv`, `post-moves`, `pre-link`, `post-ln`, `post-link` and `pre-restore`.
  - Four review rounds added:
    - the relative-symlink and scan-completeness refusals;
    - NUL-safe enumeration;
    - reverse-nesting location;
    - restore steps that start from the real state (per-entry competitor, free path, obstructed root, absent root);
    - trailing-slash normalization;
    - recognition of a completed layout in the signal handler.
- **Issues encountered:**
  - Bash ignores a SIGINT whose foreground child exited normally (wait-and-cooperative-exit), so the INT interruption test hook also kills itself.
  - `ln -s target existing_dir` silently creates the link inside the directory; that is why the link is verified and the stray link is cleaned up.
  - `mv -n` onto an existing directory still nests; that is why every move is verified by inode.
- **Key decisions:**
  - The lock is the stale_lock mutex, because `flock` is not on stock macOS.
  - Engine slot writers are not coupled to the home lock (D7): the migration never touches `$AITASKS_HOME/engine`.
  - Rollback derives each entry's location from on-disk identity, not from bookkeeping.
  - The legacy path is spelled exactly once (`LEGACY_ROOT=… # legacy-root-ok:`).
  - Setup reads the report rather than spelling the path itself.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - The named follow-up that flips the setup default can call `ait engine home --migrate` and branch on the `HOME_*` protocol lines: exit 0 means migrated or nothing to do, 1 refused or rolled back, 2 stranded with `HOME_RESTORE` steps.
  - The proposal's admission criteria for that follow-up (a real `install.sh --dir` with a working venv and PyPy venv afterwards, re-run, hostile symlink, cross-device, collision, override) are now covered by H-I, H11–H13, H7, H8, H5 and H11.
  - The 18 doc files naming `~/.aitask` remain to be updated.
  - `AIT_HOME_TEST_HOOK` mirrors the `AIT_ENGINE_TEST_*` seams.
  - `tree_sig` in `test_aitasks_home.sh` is a reusable NUL-safe byte-identity signature.
