---
Task: t2184_anchor_setup_gitignore_task_data_entries.md
Base branch: main
Output branch: main
---

# t2184 — Anchor setup's task-data `.gitignore` entries to the repo root

## Context

`setup_data_branch` Step 7 (`.aitask-scripts/aitask_setup.sh:2023-2033`) appends the
"# Task data (lives on aitask-data branch, accessed via symlinks)" block with **bare**
`.aitask-data`, `aitasks`, `aiplans` lines. In gitignore syntax a pattern with no slash
matches **at any depth**, so every nested `aitasks/` / `aiplans/` / `.aitask-data/`
directory in a consumer project is silently ignored (t2179_1 lost five fixture files
this way in aitasks_go). The bare form was chosen (t699, t1711) only because a
trailing slash matches directories and misses the root **symlinks**; a leading slash
keeps symlink matching and confines the rule to the root: `/aitasks`.

Writers/readers of this block, verified by grep:
- the only writer is Step 7 (`aitask_setup.sh:2027`); `install.sh` never writes it — for
  existing installs it calls `setup_data_gitignore_symlink_safe` (install.sh:1910-1912),
  so a migration in the shared rewriter reaches both `ait setup` and `ait upgrade`;
- the only reader is Step 7's presence guard (`grep -qxF "$AIT_DATA_DIR_NAME"`, :2024);
- the data branch's own `.aitask-data/.gitignore` (`aitasks/new/`,
  `aitasks/metadata/…`) needs no change: every entry has an inner slash, so it is
  already root-anchored;
- names come from `AIT_DATA_DIR_NAME` / `AIT_DATA_LINKS` in
  `.aitask-scripts/lib/data_symlinks.sh` — keep deriving from them, no new literals.

Anchoring is relative to the `.gitignore`'s own directory, so it stays correct in linked
worktrees (`aiwork/<t>/.gitignore` → `aiwork/<t>/aitasks`) and in the "installed in a
subdirectory" layout.

## Implementation

1. **Writer — `aitask_setup.sh` Step 7 (≈:2003-2033).** Write the block from the
   names: `echo "/$AIT_DATA_DIR_NAME"` then `printf '/%s\n' "${AIT_DATA_LINKS[@]}"`.
   Presence guard checks the anchored form `"/$AIT_DATA_DIR_NAME"` (LF and CRLF, as
   today). Update the comments ("bare entries match both" → anchored: leading slash
   matches the root file/dir/symlink only; trailing slash would miss symlinks) and the
   `warn` text "Could not rewrite trailing-slash data entries" → "Could not rewrite
   legacy data entries".

2. **Migration — `_ait_render_data_gitignore` + `_ait_rewrite_data_gitignore_lines`
   (≈:2886-2930).** Keep the function names and the 0/1/2 exit contract (callers and
   tests branch on it).
   - Detection: a name is legacy when the file has the exact line `name/` **or** `name`
     (each LF or CRLF): `grep -qxF -e "$name/" -e "$name/"$'\r' -e "$name" -e "$name"$'\r'`;
     grep rc 2 still → return 2.
   - Renderer awk: `want[a[i]] = "/" a[i]; want[a[i] "/"] = "/" a[i]`; CR kept as today.
     Whole-line exact match only — `aitasks/new/`, `docs/aitasks`, `!aitasks`,
     `# aitasks`, `aitasksx`, `/aitasks` pass through byte-for-byte.
   - Same whole-file scope as the existing trailing-slash rewrite (t699/t1711), not
     "inside the block": the header line is user-editable, and a bare data-name line
     anywhere in the root `.gitignore` has the same defect. A file holding both `aitasks`
     and a hand-added `/aitasks` ends up with two `/aitasks` lines — harmless, no dedupe.
   - Rewrite the header comment block (≈:2864-2885) to describe both legacy forms.

3. **Re-run repair messages — `setup_data_gitignore_symlink_safe` (≈:2944-2955).**
   rc 0: "Rewrote legacy data entries in .gitignore to the root-anchored form
   (/.aitask-data, /aitasks, /aiplans)" (built from the names). rc 1: "Data entries in
   .gitignore already symlink-safe and root-anchored" (keeps the `already symlink-safe`
   substring test D pins). rc 2: keep "Could not rewrite …"; second line says trailing
   slashes leave linked worktrees showing `?? .aitask-data` and bare names also hide
   nested directories of those names; fix-by-hand hint → change `.aitask-data/` or
   `.aitask-data` to `/.aitask-data` (likewise aitasks, aiplans).

4. **This repo's `.gitignore` (:59-61)** → `/.aitask-data`, `/aitasks`, `/aiplans`
   (otherwise the next `ait setup` rewrites it under `commit_framework_files`). This
   un-hides two stray untracked dirs in this checkout — see "Stray paths" below.

5. **Tests.**
   - `tests/test_gitignore_data_symlinks.sh` (git-asked, no hand-rolled matcher):
     - `porcelain_for` also creates a real file `ait_t2184_nested/<name>/f` per data
       name; `check_gitignore` asserts each nested file **is** reported (`?? …/f`)
       while the root symlinks are not. Applies to Case A (repo `.gitignore`), C, F.
     - New negative control: the bare block (`printf '%s\n' "${NAMES[@]}"`) hides the
       nested files (assert not reported) — proves the nested check can fail.
     - Case C stays trailing-slash → expected now `/name`. New Case C2: the bare block
       plus non-rewritable lookalikes (`aitasks/new/`, `docs/aitasks`, `!aitasks`,
       `# aitasks`, `aitasksx`) → exact expected bytes, rc 0; second run rc 1; an
       already-anchored file → rc 1 and byte-identical.
     - Case E greps `/.aitask-data`; Case F expected bytes `/name\r`; new Case F2: bare
       CRLF lines → anchored CRLF, byte-exact, second run rc 1.
     - Header comment: add the anchoring rule (t2184) and `ait_t2184_nested`.
   - `tests/test_data_branch_setup.sh`:
     - `assert_data_symlinks_ignored` gains the same nested-dir check.
     - Test 1 (real `setup_data_branch`): assert `/.aitask-data`, `/aitasks`, `/aiplans`
       present and bare `aitasks`/`aiplans` absent; then in the real repo create
       `docs/aitasks/t1.md` and `docs/aiplans/p1.md` and assert via
       `git status --porcelain --untracked-files=all` that both are reported while no
       `?? aitasks` / `?? aiplans` line appears (the task's acceptance test).
     - Test 12 (legacy trailing-slash fixture): expectations → anchored; "exactly one"
       counts on `/aitasks`, `/aiplans`, `/.aitask-data`; bare lines absent.
     - New Test 12b: fixture with the **bare** block already committed (a project set up
       between t699 and now, cloned onto a new PC) → after `setup_data_branch` the lines
       are anchored, exactly one `# Task data` header (no second block appended), symlinks
       ignored, `.gitignore` committed.
     - Test 18 (:1195): `assert_gitignore_line … ".aitask-data"` → `"/.aitask-data"`.
     - Test 33 (:1644-1673): its fixture is **derived** from setup's output
       (`sed 's#^\.aitask-data$#.aitask-data/#'`). Once setup writes `/.aitask-data`,
       that sed matches nothing, the `commit -- .gitignore` that follows has nothing
       to commit, and the repair is never exercised. Build the legacy fixture
       **explicitly** instead. Drop the anchored data lines (`grep -vxF` with the
       names taken from `AIT_DATA_DIR_NAME` / `AIT_DATA_LINKS`), append a literal
       legacy block, and commit. Then assert the precondition before any repair
       runs: every legacy line is present, no anchored data line remains, and
       `git diff --quiet HEAD -- .gitignore` passes after a commit that really
       changed the file (HEAD's `.gitignore` holds the legacy line). Run it as two
       variants:
       - `trailing`: `.aitask-data/`, `aitasks`, `aiplans`, the block committed in
         the t699 era;
       - `bare`: `.aitask-data`, `aitasks`, `aiplans`, the t1711-era block, which is
         the new legacy form.

       The assertions for both: the `setup_data_branch` re-run still cannot reach
       the line, the repair reports `Rewrote legacy data entries`, every legacy line
       is gone, every anchored line is present, and a second run prints
       `already symlink-safe`.
     - Test 34 (:1704): the on-disk check becomes `"/.aitask-data"`, plus `"/aitasks"`.
       In the clean case, also assert that HEAD holds the exact line `/aitasks`. The
       dirty-case `.aitask-data/`-in-HEAD check does not change, since its fixture is
       already a literal.
     - Test 36 (:1819): the on-disk check becomes `"/.aitask-data"`. The clean case's
       substring check `assert_contains ".aitask-data"` tightens to an exact
       `/.aitask-data` line in HEAD. The dirty case's `assert_not_contains
       ".aitask-data"` still holds, so it stays. Test 37 (:1865) is a substring check
       that still holds and stays.
     - Inventory method: grep the whole file for every literal the change alters (all
       `assert_(no_)?gitignore_line` calls, `grep -c?xF` calls, `"Rewrote"` and
       `"trailing-slash"` messages) and for every fixture built by transforming
       setup's output. Every hit is listed above. A grep of the other 21 test files
       that mention both `.gitignore` and the data names finds no more bare-line
       expectations: their hits are data-branch paths such as
       `.aitask-data/aitasks/…`.
   - `tests/test_install_upgrade_dirty_baseline.sh` (the `ait upgrade` route):
     `LEGACY_GITIGNORE` becomes mixed — `.aitask-data/`, bare `aitasks`, `aiplans/` — so
     one fixture drives both legacy forms through install.sh; A/B assertions → anchored
     (`/.aitask-data`, `/aitasks`), bare `aitasks` gone; "B HEAD still legacy" unchanged.
   - `tests/test_task_worktree_helper.sh` 23a already runs the repo's real `.gitignore`
     in a linked worktree — no edit; it now proves anchoring holds there.

6. **Docs — `website/content/docs/commands/setup-install.md:114`.** Replace the
   "rewrites the trailing-slash data entries … to the bare form" sentence with: it
   rewrites the data entries `.aitask-data`, `aitasks`, `aiplans` (trailing-slash or bare)
   to the root-anchored form `/.aitask-data`, `/aitasks`, `/aiplans`, which matches the
   symlinks at the repository root and in linked task worktrees without ignoring nested
   directories of the same name; committed only when `.gitignore` was clean.
   Current-state wording only; the v0.19.0 blog post and the shadow_q pilot report are
   historical and stay as they are. Add one clause that the run lists any nested
   paths the old rules hid (post-phase below).

7. **Stray paths (this checkout) — user chose delete.** Step 4 makes two untracked,
   long-stale dirs visible: `.aitask-scripts/board/aitasks/` (board_config json,
   2026-04-26) and `website/aiplans/` (one p355_7 plan copy, 2026-03-16). Before
   deleting, confirm with `git ls-files -- <dir>` that neither holds tracked files,
   then `rm -rf` exactly those two dirs. After step 4, `git status --porcelain` shows
   neither.

### Post-phase (risk mitigations)

1. [report_unhidden_nested_data_paths] Add a read-only, never-fatal helper
   `_ait_report_unhidden_nested_data_paths <project_dir>` next to the rewriter in
   `aitask_setup.sh`. It runs `git -C "$project_dir" ls-files -o --exclude-standard`
   (files, **not** `--directory`, which would collapse a wholly-untracked `docs/` and
   hide the nested component) and pipes it to awk. The data names go in as awk data
   (`-v`), the same "no regex built from names" rule the renderer follows. For each
   path, awk takes the first component at index ≥2 that equals a data name, prints
   the prefix through that component plus `/`, and dedupes. Any git failure (not a
   repo) → print nothing, return 0. When non-empty, `info` one line, then at most 10
   paths and "… and N more". The line's wording is **neutral**: "After anchoring the
   data entries in .gitignore, these nested aitasks/aiplans/.aitask-data paths show
   as untracked — review them before a broad 'git add':". It makes no claim that the
   paths were hidden before. The scan runs only after the rewrite, and rc 0 is not
   proof of where a path came from: a mixed file (`.aitask-data/`, `/aitasks`,
   `/aiplans`) rewrites only `.aitask-data`, while a `docs/aitasks/f` was visible all
   along. Exact provenance would need a scan before the rewrite and one after; that
   is not needed for an advisory list. Call the helper only on a successful rewrite
   (rc 0): in Step 7's `0)` arm with `$project_dir`, and in
   `setup_data_gitignore_symlink_safe`'s `0)` arm with `$SCRIPT_DIR/..`.
2. [report_unhidden_nested_data_paths] Test — new Case G in
   `tests/test_gitignore_data_symlinks.sh`, with two fixtures. Each is a real git repo
   with `SCRIPT_DIR` pointed at `<repo>/.aitask-scripts`, runs
   `setup_data_gitignore_symlink_safe`, and restores `SCRIPT_DIR` afterwards.
   - **G1 (bare block).** Contents: `docs/aitasks/t1.md`, `x/y/aiplans/p.md`, a
     control `notdata/f`, and a root `aitasks` symlink. The output lists
     `docs/aitasks/` and `x/y/aiplans/` and never names `notdata` or the root
     `aitasks`. A second run (rc 1) prints no list.
   - **G2 (mixed rules: `.aitask-data/`, `/aitasks`, `/aiplans`).** First assert the
     precondition with git: `docs/aitasks/t1.md` already shows as untracked before
     the repair. The repair then returns rc 0, the list includes
     `docs/aitasks/` under the neutral wording, and the output contains neither
     `hidden` nor `old unanchored`. This pins that the message claims nothing
     about provenance.

   Test 12b (Step 7 route) adds `docs/aitasks/t1.md` to its fixture, keeps the
   output of `setup_data_branch` instead of discarding it, and asserts the path is
   listed.

## Verification

- `bash tests/test_gitignore_data_symlinks.sh`
- `bash tests/test_data_branch_setup.sh`
- `bash tests/test_install_upgrade_dirty_baseline.sh`
- `bash tests/test_task_worktree_helper.sh`
- `bash tests/test_setup_git.sh`, `bash tests/test_data_branch_migration.sh` (regression)
- `shellcheck .aitask-scripts/aitask_setup.sh`
- `cd website && python3 check_links.py --build`
- `git check-ignore -v aitasks aiplans .aitask-data` in this repo → `/…` rules; a
  scratch nested `x/aitasks/f` is not ignored.
- Leftover-expectation sweep:
  `grep -nE '"(\.aitask-data|aitasks|aiplans)"|Rewrote trailing|trailing-slash data' tests/test_data_branch_setup.sh tests/test_install_upgrade_dirty_baseline.sh tests/test_gitignore_data_symlinks.sh`.
  Review every hit: it must be an anchored-form expectation, a deliberate legacy
  fixture, or a substring check that still holds.

## Step 9 (Post-Implementation)

Current-branch mode: commit code (`bug: … (t2184)`) and plan separately, then archive
via the standard Step 9 flow.

## Risk

### Code-health risk: low
- Every consumer's committed root `.gitignore` gets an exact-line rewrite on the next
  `ait setup` / `ait upgrade` (whole-file, not block-scoped), so a hand-written bare
  `aitasks` meant to ignore nested dirs is anchored too. Same policy, guards and atomic
  writer as the existing trailing-slash rewrite; mode/symlink/CRLF/failure paths stay
  covered by Cases D–F · severity: low · → mitigation: none
- Test churn across four test files and the repo `.gitignore` (Case A) · severity: low ·
  → mitigation: none
- The post-phase helper lists every untracked file once, on a successful rewrite only. On a
  huge untracked tree that run costs time, but it never fails setup, it adds no
  steady-state cost, and its output is advisory · severity: low · → mitigation: none

### Goal-achievement risk: low
- Nested data-name dirs that the bare rules hid (stray artifacts like the two found in
  this checkout) become untracked after the upgrade, silently: a broad `git add -A` in
  some session could then commit them · severity: low (residual — addressed by inline
  post-phase report_unhidden_nested_data_paths, which names them at the moment they
  appear) · → mitigation: inline post-phase report_unhidden_nested_data_paths

### Planned mitigations
- timing: post-phase | name: report_unhidden_nested_data_paths | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — nested dirs silently un-hidden by the anchoring migration | desc: after a successful data-entry rewrite, list (capped, neutral wording, no provenance claim) the untracked nested data-name paths
