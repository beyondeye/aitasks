---
Task: t641_fix_release_tarball_missing_skills_and_rename_ait_install.md
Base branch: main
plan_verified: []
---

# Plan — t641: fix release-tarball missing skills and rename `ait install` → `ait upgrade`

## Context

Comparing `../aitasks_mobile` (installed via `ait install` from the v0.17.3 GitHub release) against local at v0.17.4, three `.claude/skills/` directories are missing in the installed target: `ait-git/`, `task-workflow/`, and `user-file-select/`. The `task-workflow/` absence is load-bearing — its `SKILL.md` and 22 sibling `.md` files (`planning.md`, `execution-profile-selection.md`, `task-creation-batch.md`, `satisfaction-feedback.md`, `manual-verification.md`, …) are referenced by nearly every `/aitask-*` skill. Downstream users who upgraded via `ait install` in the last several releases have been running a framework with broken cross-skill references.

Root causes (two independent bugs, both ship-gated):

1. `.github/workflows/release.yml` uses the glob `.claude/skills/aitask-*/` when staging skills into the tarball. Three helper skills that don't share the `aitask-` prefix are silently excluded from every tarball. The same `aitask-*/` glob repeats in the codex and opencode build steps; no non-`aitask-*` skill lives in those trees today, but the exclusion rule is still latent.
2. `install.sh` unpacks the staged `skills/` into `.claude/skills/` with `cp "$skill_dir/SKILL.md" …` — a single-file copy. Every sub-document in a shipped skill directory is silently dropped. This is already observable for `aitask-qa/`: six sub-docs exist locally (`change-analysis.md`, `follow-up-task-creation.md`, `task-selection.md`, `test-discovery.md`, `test-execution.md`, `test-plan-proposal.md`) and are all missing from `../aitasks_mobile/.claude/skills/aitask-qa/`. Once bug #1 is fixed, bug #2 would immediately manifest again for `task-workflow/`'s 22 sub-docs.

Separately, the user flagged that `ait install` is a misnomer — semantically it performs an in-place framework *upgrade* of an existing installation (`ait setup` handles first-time bootstrap). But `ait update <ID>` is already taken for task-frontmatter edits. Recommendation: rename to `ait upgrade`, aligning with `apt upgrade` / `brew upgrade` conventions. Keep `ait install` as a deprecated alias that warns and forwards, so downstream docs and muscle memory don't break.

Not in scope: re-releasing v0.17.3, bumping CHANGELOG (handled at tag time), or touching codex/opencode/gemini skill trees beyond the glob broadening for symmetry. `aitask_install_merge.py` is also not in scope — it was introduced post-v0.17.3 and will ship naturally with v0.17.4.

## Changes

### Part A — release glob (fix bug #1)

**File:** `.github/workflows/release.yml`

1. **Step "Build skills directory from .claude/skills"** — change `.claude/skills/aitask-*/` to `.claude/skills/*/`.
2. **Step "Build codex skills directory from .agents/skills"** — change `.agents/skills/aitask-*/` to `.agents/skills/*/` (no functional change today; prevents the same latent bug if a non-`aitask-*` skill is added later).
3. **Step "Build opencode skills directory from .opencode/skills"** — change `.opencode/skills/aitask-*/` to `.opencode/skills/*/` (same reasoning).

The gemini block uses `cp -r .gemini/commands/. gemini_commands/` (recursive copy, no glob) — no change needed.

### Part B — install.sh full-directory copy (fix bug #2)

**File:** `install.sh`

Three functions share the same broken pattern:

1. **`install_skills()`** (≈ lines 184–204):
   - Change loop glob `"$INSTALL_DIR/skills"/aitask-*/` → `"$INSTALL_DIR/skills"/*/`.
   - Replace the single-file copy:
     ```bash
     cp "$skill_dir/SKILL.md" "$INSTALL_DIR/.claude/skills/$skill_name/SKILL.md"
     ```
     with a full-directory copy:
     ```bash
     cp -r "$skill_dir". "$INSTALL_DIR/.claude/skills/$skill_name/"
     ```
     (`$skill_dir` already ends in `/` from the glob; `"$skill_dir".` → `"dir/".` is the standard "copy contents" form, robust to extra files the skill owns.)

2. **`install_codex_staging()`** (≈ lines 420–445) — same glob + `cp -r` change inside the `.claude/skills/`-equivalent staging at `aitasks/metadata/codex_skills/<name>/`. Current codex skills are flat, so behavior is unchanged today; the change removes the latent trap.

3. **`install_opencode_staging()`** (≈ lines 448–475) — same glob + `cp -r` change inside `aitasks/metadata/opencode_skills/`.

### Part C — release-artifact smoke test (new)

**New file:** `tests/test_release_tarball.sh`

A self-contained bash test following the house pattern (`set -euo pipefail`, local `assert_exists` / counters, `trap` cleanup, PASS/FAIL summary, `exit 1` on any failure). Emulates the two critical release steps in a `mktemp` sandbox and asserts the shipped tree has the previously-missing files:

- Emulate the "Build skills directory from .claude/skills" step (the post-fix glob `.claude/skills/*/`) into `$TMP/skills/`.
- Assert presence of: `skills/task-workflow/SKILL.md`, `skills/task-workflow/planning.md`, `skills/ait-git/SKILL.md`, `skills/user-file-select/SKILL.md`, `skills/aitask-qa/change-analysis.md`, `skills/aitask-pick/SKILL.md` (regression guard for the plain case).
- Emulate the `install.sh install_skills()` post-fix copy (`cp -r "$skill_dir". …`) into `$TMP/target/.claude/skills/`.
- Re-assert the same filenames survive at the install target.

This test is a pure-bash emulation — it does not depend on tar or network. If either the release glob or the install copy regresses, it fails loudly. Lives alongside `tests/test_install_merge.sh` as a release-side counterpart.

### Part D — rename `ait install` → `ait upgrade`

**D.1 — Rename the command script**

- Rename `.aitask-scripts/aitask_install.sh` → `.aitask-scripts/aitask_upgrade.sh` via `git mv` (preserves history).
- Inside, update the comment header, the `show_help()` usage/examples text, and the `# Invoked via:` comment to use `ait upgrade [latest|VERSION]`.

**D.2 — Dispatcher (`ait`)**

- **Line 152** (`no-sync` list): add `upgrade` alongside `install`:
  ```
  help|--help|-h|--version|-v|install|upgrade|setup|git|sync|lock|codeagent|crew|brainstorm|settings|monitor|minimonitor|ide) ;;
  ```
- **Line 160** (dispatch case): replace the single `install)` line with:
  ```bash
  upgrade)      shift; exec "$SCRIPTS_DIR/aitask_upgrade.sh" "$@" ;;
  install)      shift
                echo -e "\033[1;33m[ait]\033[0m 'ait install' is deprecated — use 'ait upgrade' instead."
                exec "$SCRIPTS_DIR/aitask_upgrade.sh" "$@" ;;
  ```
  The alias keeps scripts, docs, and muscle memory working for one-plus release cycles.
- **Line 125** (`check_for_updates` hint): `"Run: ait install latest"` → `"Run: ait upgrade latest"`.

**D.3 — Setup-script user-facing strings**

`.aitask-scripts/aitask_setup.sh` — update five strings:
- Line 1177: `Reinstall aitasks (e.g. 'ait install')…` → `Reinstall aitasks (e.g. 'ait upgrade')…`
- Line 1297: `Run: ait install latest` → `Run: ait upgrade latest`
- Line 1558: `Re-run 'ait install' to get Gemini CLI support files` → `Re-run 'ait upgrade' …`
- Line 1799: same swap for Codex message
- Line 1934: same swap for OpenCode message

**D.4 — Comment references in install.sh and helper**

- `install.sh` (comment inside `merge_seed()`, around line 219): update `ait install --force` → `ait upgrade --force`.
- `.aitask-scripts/aitask_install_merge.py` (docstring at top): update `ait install --force` → `ait upgrade --force`.
  (File name of the Python helper is kept — it's an internal helper, not user-facing, and renaming it would force updating `install.sh`'s call site with no user-visible benefit.)

**D.5 — Docs**

- `README.md:73` — `ait install latest` → `ait upgrade latest`.
- `website/content/docs/installation/_index.md:25` — same swap.
- `website/content/docs/commands/_index.md`:
  - Line 57 (command table): `[\`ait install\`](setup-install/#ait-install) | Update aitasks to latest or specific version` → `[\`ait upgrade\`](setup-install/#ait-upgrade) | Update aitasks to latest or specific version`.
  - Lines 87–88: swap `ait install` → `ait upgrade` in the code fence.
- `website/content/docs/commands/setup-install.md`:
  - Line 5 (page description): `ait setup and ait install commands` → `ait setup and ait upgrade commands`.
  - Line 53 (section heading): `## ait install` → `## ait upgrade` (this changes the anchor used by `_index.md:57` — both edits happen together so the cross-reference stays valid).
  - Lines 58–60: swap verbs in the code fence.
  - Line 74 (no-sync mention): update `help, version, install, and setup` → `help, version, install, upgrade, and setup`.
- **Page filename:** leave `setup-install.md` as-is; renaming the file breaks any bookmarks and external links. The in-page heading change is sufficient.
- `CHANGELOG.md`: do **not** add an entry in this task — CHANGELOG entries are cut at release-tag time, and the next entry (v0.17.5 or whichever) will mention both the tarball fix and the rename together.

## Key files to modify

- `.github/workflows/release.yml` (Part A)
- `install.sh` (Part B, Part D.4)
- `tests/test_release_tarball.sh` (new, Part C)
- `.aitask-scripts/aitask_install.sh` → `.aitask-scripts/aitask_upgrade.sh` (rename + edits, Part D.1)
- `ait` (Part D.2)
- `.aitask-scripts/aitask_setup.sh` (Part D.3, 5 edits)
- `.aitask-scripts/aitask_install_merge.py` (Part D.4, docstring)
- `README.md` (Part D.5)
- `website/content/docs/installation/_index.md` (Part D.5)
- `website/content/docs/commands/_index.md` (Part D.5)
- `website/content/docs/commands/setup-install.md` (Part D.5)

## Verification

1. `grep -rn 'aitask-\*/' .github/workflows/release.yml install.sh` — returns nothing.
2. `grep -rnE "\\bait install\\b" ait .aitask-scripts/ seed/ install.sh README.md website/` — returns only the deprecation-warning string in `ait` and (if present) legacy CHANGELOG entries. No other live references.
3. `bash tests/test_release_tarball.sh` — all assertions pass.
4. End-to-end in a scratch dir:
   ```bash
   cd /tmp && rm -rf aitmob_test && git clone ../aitasks_mobile aitmob_test && cd aitmob_test
   bash /home/ddt/Work/aitasks/install.sh --force --dir "$PWD"  # or build a local tarball and use --local-tarball
   test -f .claude/skills/task-workflow/planning.md
   test -f .claude/skills/ait-git/SKILL.md
   test -f .claude/skills/user-file-select/SKILL.md
   test -f .claude/skills/aitask-qa/change-analysis.md
   ```
   (The `install.sh` script supports `--local-tarball` — running the end-to-end without an actual v0.17.5 tag requires `tar -czf` the working tree's equivalent of the release workflow output first. The unit smoke test in Part C is the primary automated verification; this step is optional manual sanity.)
5. `./ait upgrade --help` — prints the new usage with `ait upgrade …` examples. `./ait install --help` — prints the deprecation warning, then the same usage text.
6. Quick dispatcher sanity: `./ait upgrade 0.17.3 && ./ait upgrade latest` — both resolve and run (manual; may hit network).
7. `shellcheck .aitask-scripts/aitask_upgrade.sh ait install.sh` — no new warnings introduced (baseline may already have some).

## Step 9 cleanup (as per task-workflow Step 9)

After user-approved commit in Step 8: run `./.aitask-scripts/aitask_archive.sh 641`, push via `./ait git push`. No branch/worktree was created (`fast` profile, `create_worktree: false`), so merge cleanup is skipped.
