---
Task: t1964_install_upgrade_dirty_baseline_and_symlink_safe_repair.md
Base branch: main
Output branch: main
---

# t1964 — Baseline-aware upgrade commit + symlink-safe `.gitignore` repair on upgrade

## Context

`ait upgrade` runs the target version's `install.sh --force`. Two defects:

1. `install.sh` `commit_installed_files` (line ~1167) commits every untracked/modified
   framework path after extraction. It has no pre-install dirty baseline, so a user's
   uncommitted edit under a framework path (e.g. `.gitignore`, a skill, a script) rides
   into `ait: Update aitasks framework to v<V>`. `commit_installed_data_files` has the
   same hole for `aitasks/metadata/` / `aireviewguides/` on the data branch.
2. Upgrade never runs setup, so `setup_data_gitignore_symlink_safe` (t1711) reaches
   existing installs only through `ait setup`. Upgraded-only projects keep the legacy
   `.aitask-data/` / `aitasks/` / `aiplans/` lines and linked task worktrees show
   `?? .aitask-data`.

The repair must be wired **after** a baseline exists, otherwise a dirty `.gitignore`
would ride into the upgrade commit with the repair. Model: setup's
`snapshot_pre_setup_dirty` / `commit_framework_files` / `commit_framework_data_files`
(`.aitask-scripts/aitask_setup.sh:4060-4380`), which since t1959 scans absent paths too.

install.sh runs stand-alone (curl|bash) and the snapshot must happen **before
extraction**, when the new `aitask_setup.sh` is not on disk yet — so install.sh keeps
self-contained copies of the helpers (the path list is already duplicated, by design).

Current-branch mode (profile `fast`): no worktree.

## Implementation

### 1. `install.sh` — self-contained baseline helpers (new, placed just above `commit_installed_files`)

- Globals: `AIT_INSTALL_DIRTY_BASELINE=""`, `AIT_INSTALL_DATA_DIRTY_BASELINE=""`,
  `AIT_INSTALL_BASELINE_ARMED=0` (distinct names from setup's `AIT_SETUP_*`, which get
  reassigned when main() sources `aitask_setup.sh`).
- `_install_framework_paths <dir> [include_absent]` — the existing `check_paths` list
  moved out of `commit_installed_files` (same 14 entries; the list is unchanged).
  `include_absent=1` prints every entry; default existence-filtered. Comment: duplicated
  with `_ait_framework_paths` in aitask_setup.sh (setup additionally lists `install.sh`,
  `.gitlab-ci.yml`, `bitbucket-pipelines.yml` — install never commits those, unchanged).
- `_install_list_changes <workdir> <extra_exclude_re> <paths...>` — untracked + modified
  + staged (`diff --cached --name-only`), `sort -u`, minus cache-artifact regex and the
  extra regex. Mirror of `_ait_list_framework_changes`.
- `_install_subtract` / `_install_intersect` — mirrors of `_ait_subtract` / `_ait_intersect`.
- `_install_data_branch_exclude_re <dir>` — `^(aitasks|aiplans)/` when `.aitask-data/.git`
  exists (the logic currently inline in `commit_installed_files`).
- `snapshot_pre_install_dirty` — sets ARMED=1, then captures the two baselines
  **independently**, each gated only on its own repository's state:
  - **Data baseline first**, whenever the `.aitask-data` worktree exists and
    `git -C .aitask-data rev-parse --is-inside-work-tree` succeeds — regardless of the
    main repo's HEAD / VERSION state. `commit_installed_data_files` has no main-repo
    tracking guard (it commits whenever the data worktree exists), so a data baseline
    hidden behind the main bootstrap guard would leave an existing install with an
    untracked `.aitask-scripts/VERSION` sweeping dirty data-branch content.
    Paths: `aitasks/metadata/ aireviewguides/`, all listed (absent included).
  - **Main baseline** whenever `_install_commit_eligible "$INSTALL_DIR"` is true — the
    **same predicate** `commit_installed_files` uses to decide whether to commit at all,
    so the snapshot can never be skipped in a state the committer acts in. Value =
    `_install_list_changes "$INSTALL_DIR" <data-re> $(_install_framework_paths "$INSTALL_DIR" 1)`.
    **No HEAD requirement**: the committer needs none (`ls-files --error-unmatch` reads
    the index), so a `git init` repo with no first commit but a staged VERSION is
    commit-eligible and must be baselined too.
- `_install_commit_eligible <dir>` — new: `git -C <dir> rev-parse --is-inside-work-tree`
  AND `git -C <dir> ls-files --error-unmatch -- .aitask-scripts/VERSION`. Exactly the two
  checks at the top of today's `commit_installed_files`, extracted; the committer keeps its
  two distinct messages by calling the checks through this helper's parts (or re-checking
  VERSION for the "not git-tracked — skipping" notice, which t167 Scenario A asserts).
- `_install_list_changes` staged term on an unborn HEAD: diff the index against
  `HEAD` when `git rev-parse --verify -q HEAD` succeeds, otherwise against the empty tree
  (`git hash-object -t tree /dev/null`, which respects the repo's object format), so
  staged content in a HEAD-less repo is listed in both the snapshot and the commit pass.
  All `|| true`-guarded: install.sh is `set -euo pipefail`.
  **Deliberate deviation from setup**: `snapshot_pre_setup_dirty` returns before its data
  baseline on the same bootstrap guard, so setup has the identical hole in
  `commit_framework_data_files`. Out of scope here (different script, own ordering
  contract) — record it under "Upstream defects identified" for the Step 8b follow-up.

Rename avoidance verified: aitask_setup.sh defines only `_install_modern_python_*`
with that prefix.

### 2. `install.sh` — `commit_installed_files` uses the baseline

- Warn to stderr when `AIT_INSTALL_BASELINE_ARMED != 1` (direct test invocation =
  legacy commit-all), as setup does.
- Paths from `_install_framework_paths "$INSTALL_DIR"`; changes from
  `_install_list_changes` (adds the staged term; data-branch filter unchanged).
- `changed_files` = changes − baseline; `excluded_files` = changes ∩ baseline. When any
  excluded: warn "Pre-existing uncommitted changes under framework paths — left alone
  (not committed by the upgrade):" + up to 20 paths + "Review and commit them yourself
  when ready."
- "already committed" short-circuit keyed on `changed_files` empty and no stale pycache.
- Path-scoped add / diff guard / commit unchanged. Post-commit "still untracked" check
  subtracts the baseline (a left-alone file is not a commit failure).

### 3. `install.sh` — `commit_installed_data_files` uses the data baseline

Same shape: changes via `_install_list_changes "$data_dir" "" <data paths>`, subtract
`AIT_INSTALL_DATA_DIRTY_BASELINE`, report excluded with a data-branch-worded warning,
commit only the remainder path-scoped (unchanged commit message).

### 4. `install.sh` `main()` — wiring

- Call `snapshot_pre_install_dirty` immediately before the CHANGELOG/VERSION preserve +
  `tar -xzf` block (after `show_upgrade_changelog`; nothing before it writes into
  `INSTALL_DIR`).
- Immediately before `commit_installed_files` (after `cleanup_packaging_leftover`, with
  `aitask_setup.sh` already sourced):
  ```bash
  if [[ "$EXISTING_INSTALL" == true ]]; then
      info "Checking .gitignore data entries..."
      setup_data_gitignore_symlink_safe
  fi
  ```
  Gated on `EXISTING_INSTALL` (always true under `ait upgrade`, which passes `--force`) so
  a fresh install prints no misleading "already symlink-safe". The function commits
  nothing and never fails (returns 0, warns on rc 2); `.gitignore` then lands in the
  upgrade commit only if it was not in the baseline. Comment the ordering contract
  (must follow the snapshot and precede the commit), mirroring setup's comment.

### 5. `aitask_setup.sh` — comment only

Update the two "duplicated in install.sh commit_installed_files()" notes to name
`_install_framework_paths` / `snapshot_pre_install_dirty`.

### 6. Docs — `website/content/docs/commands/setup-install.md` `## ait upgrade`

Extend step 5 ("Performs the full installation") in current-state prose: the upgrade
commits only the framework files it changed — framework files that already had
uncommitted changes (edited, staged or deleted) are left uncommitted and listed — and it
rewrites legacy trailing-slash data entries in `.gitignore` (`.aitask-data/`, `aitasks/`,
`aiplans/`) to the symlink-safe bare form. Run `python3 check_links.py --build`.

### 7. Tests — new `tests/test_install_upgrade_dirty_baseline.sh`

Fixture pattern from `tests/test_upgrade_prunes_retired_scripts.sh`: `build_tarball`
(release layout from this checkout), `run_install` with `HOME=$FAKE_HOME`,
`AITASKS_HOME`, `AIT_TESTMAP_FETCH=0`, `--force --local-tarball`, stdin `/dev/null`.
Tarball variant bumps `.aitask-scripts/VERSION` and appends a comment to `ait`, so the
upgrade has real changes. Each case: fresh git repo → first install → commit all → apply
the case's dirty state → upgrade → assert. Counters per `tests/lib/asserts.sh`.

- **A clean `.gitignore` + legacy line** (`.aitask-data/`, `aitasks/` committed): after
  upgrade, disk has bare lines, `git show HEAD:.gitignore` has bare lines, `.gitignore`
  not in `git status --porcelain`, and the upgrade commit (`git show --stat HEAD`) lists
  `.gitignore`.
- **B dirty `.gitignore` + legacy line** (extra uncommitted user line): disk has bare
  lines AND the user line; `HEAD:.gitignore` still has `.aitask-data/` and lacks the user
  line; `.gitignore` still ` M`; output contains "left alone" and `.gitignore`. Other
  framework changes (VERSION) still committed.
- **C foreign staged file never swept (regression control — passes pre-fix too)**:
  staged edit to `README.md` (outside framework paths) and a staged-only new file
  `.claude/skills/my_skill/SKILL.md`: neither in the upgrade commit's file list; both
  still staged afterwards (`git diff --cached --name-only`). The pre-fix installer lists
  only untracked + worktree-modified files, so this guards the new staged term against
  regressing, not the old bug.
- **C2 untracked custom skill (negative control)**: untracked
  `.claude/skills/my_untracked_skill/SKILL.md` before the upgrade → not in the upgrade
  commit, still `??` afterwards, reported as left alone.
- **D unstaged deletion of a top-level framework file** (`rm ait`): extraction
  recreates `ait` with new content; `ait` NOT in the upgrade commit and reported left
  alone (this is the include-absent case: existence-filtered, `ait` would be dropped
  from the baseline).
- **E fresh install** (installer behaviour only — no fixture commit between install and
  asserts): `.aitask-scripts/VERSION` exists and is untracked, commit count unchanged
  (no installer commit; the existing t637 sentinel contract that
  `tests/test_t167_integration.sh` Scenario A pins), and no "Checking .gitignore data
  entries" line (the `EXISTING_INSTALL` gate).
- **F branch mode data baseline** (t644-style `.aitask-data` worktree + symlinks):
  uncommitted edit to `aitasks/metadata/labels.txt` before upgrade → not in the data
  branch's upgrade commit, still modified; and no "beyond a symbolic link" in output.
- **F2 data baseline independent of the main bootstrap guard**: same branch-mode layout,
  but `.aitask-scripts/VERSION` untracked in the main repo (`git rm --cached` + commit)
  and an uncommitted edit to `aitasks/metadata/labels.txt` → the main commit is skipped
  (sentinel notice), and the edit is still not committed on the data branch (data
  branch HEAD's `labels.txt` unchanged, file still modified).

### Post-phase (risk mitigations)

1. [install_errexit_edges] In `tests/test_install_upgrade_dirty_baseline.sh`, add cases
   that run the real installer where `snapshot_pre_install_dirty` takes its early-return
   branches: (G1) `--dir` a plain non-git directory; (G2a) a `git init`-ed repo with no
   commit (no HEAD), fresh install. Each asserts exit status 0 and "aitasks installed
   successfully" in the output, so an unguarded pipeline under `set -euo pipefail`
   cannot abort silently.
   (G2b — the eligibility-mismatch case) a HEAD-less repo with an existing install where
   `.aitask-scripts/VERSION` is staged (commit-eligible with no HEAD) and a staged
   `.gitignore` carrying a legacy `.aitask-data/` line plus a user rule; then upgrade.
   Assert exit 0; `.gitignore` is not in any commit the installer made (`git log --all
   --name-only` lacks it, or HEAD is still unborn); `git show :.gitignore` (index) still
   holds the user rule and the legacy line; the worktree `.gitignore` has the bare
   `.aitask-data` line; output reports `.gitignore` as left alone. Negative control
   (verification only, not shipped): a scratch copy of the fixed install.sh whose
   snapshot additionally returns early on an unborn HEAD, run via `INSTALL_SH`, must
   fail G2b.
2. [framework_path_list_parity] In the same file, source `install.sh --source-only` and
   `aitask_setup.sh --source-only` in a subshell and assert
   `_install_framework_paths <dir> 1` equals `_ait_framework_paths <dir> 1` minus
   `install.sh`, `.gitlab-ci.yml`, `bitbucket-pipelines.yml` (order-insensitive).

## Verification

- `bash tests/test_install_upgrade_dirty_baseline.sh` — all pass.
- **Negative control**: run the same file against the pre-fix installer
  (`git show HEAD:install.sh > $scratch/install_prefix.sh`, via an env override
  `INSTALL_SH` the test honours, default `$PROJECT_DIR/install.sh`): cases A (repair),
  B, C2, D, F, F2 must fail; C and E are regression controls and pass on both.
- Regression: `tests/test_t644_branch_mode_upgrade.sh`, `tests/test_t167_integration.sh`,
  `tests/test_upgrade_prunes_retired_scripts.sh`, `tests/test_setup_git.sh`,
  `tests/test_gitignore_data_symlinks.sh`, `tests/test_data_branch_setup.sh`,
  `tests/test_session_hook_install.sh`.
- `shellcheck install.sh tests/test_install_upgrade_dirty_baseline.sh`.
- `cd website && python3 check_links.py --build`.

## Risk

### Code-health risk: low
- install.sh is `set -euo pipefail` and is the upgrade path for every consumer project; a non-guarded failing pipeline in the new snapshot/list helpers would abort an upgrade after extraction, leaving the framework update uncommitted · severity: low (residual — addressed by inline post-phase install_errexit_edges) · → mitigation: inline post-phase install_errexit_edges
- The framework path list and change-listing helpers are now duplicated between install.sh and aitask_setup.sh; the two can drift silently (one side gains a path the other never baselines/commits) · severity: low (residual — addressed by inline post-phase framework_path_list_parity) · → mitigation: inline post-phase framework_path_list_parity

### Goal-achievement risk: low
- None identified.

### Planned mitigations
- timing: post-phase | name: install_errexit_edges | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: errexit abort in new install.sh helpers | desc: run the real installer into a non-git dir and a HEAD-less repo; assert exit 0 + success banner
- timing: post-phase | name: framework_path_list_parity | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: install.sh/setup path-list drift | desc: assert _install_framework_paths matches _ait_framework_paths minus the three setup-only entries

## Step 9 (Post-Implementation)

Commit code (`bug: … (t1964)`, path-scoped) and plan separately; archive via the
task-workflow Step 9 flow.
