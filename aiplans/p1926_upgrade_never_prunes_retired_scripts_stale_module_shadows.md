---
Task: t1926_upgrade_never_prunes_retired_scripts_stale_module_shadows.md
Base branch: main
Output branch: main
---

# t1926 — Prune retired `.aitask-scripts/` files on upgrade/setup; guard lib-module shadowing

## Context

`install.sh` extracts the release tarball additively, so a script the framework
deleted or moved stays in every upgraded project and is committed there.
t1217 moved `board/task_yaml.py` → `lib/task_yaml.py`; `aitask_board.py` puts
`board/` ahead of `lib/` on `sys.path`, so the stale copy wins and every fresh
`ait board` in thinking_app / thinking_backend (v0.36.1) dies with
`ImportError: cannot import name 'normalize_board_idx'`. The only retirement
cleanup today is the skills pruner.

Outcome: upgrade (and `ait setup`) removes pristine retired scripts by
content-hash ownership and commits the removal; modified copies are kept and
named; and a stale/foreign module that shadows a `lib/` module fails the TUI
with a clear diagnostic instead of an opaque ImportError.

## Findings that shape the design

- `aitask_prune_retired_skills.sh` already implements everything needed
  generically: `--manifest <file>`, `FILE`/`DIR` records, flat `SHA` set,
  `git hash-object` ownership, all-or-nothing DIRs, `PRUNED:`/`KEPT:` stdout,
  missing manifest ⇒ no-op. Only its human-facing wording is skill-specific.
- `install.sh` `prune_retired_skills()` (L966) runs after extraction, before
  `commit_installed_files()`; setup's `prune_retired_skills()` (L3539) runs from
  `setup_code_agents`, after `snapshot_pre_setup_dirty` and before
  `commit_framework_files`. Both commit paths discover changes with
  `git ls-files --modified`, which reports deletions, and stage with
  `git add -- <path>`, which stages a deletion — so no staging change is needed.
- `ait upgrade` runs the **target** tag's `install.sh` → the new release's
  helper + manifest run even in an old project. "Already up to date" projects
  are covered by the same prune in `ait setup` (runs from the project's own,
  current scripts).
- Retired-path audit (ever-added under `.aitask-scripts/` minus HEAD; agrees
  with the `--diff-filter=DR` list): **20 paths**, ~52 distinct blobs:
  `aitask_brainstorm_apply_{detailer,patcher}.sh`, `aitask_codex_plan_invoke.py`,
  `aitask_install.sh`, `aitask_zip_old_v2.sh`, `board/task_yaml.py`,
  `brainstorm/templates/{crew_meta_template.yaml,detailer.md,patcher.md}`,
  `lib/archive_{iter_v2.py,scan_v2.sh,utils_v2.sh}`, `lib/attachment_backend.sh`,
  `lib/attachment_backends/local.sh`,
  `lib/attachment_cache.sh`, `lib/attachment_utils.sh`, `lib/codex_plan_policy.sh`,
  `lib/task_resolve_v2.sh`, `skill_templates/_detailer_rules.md`,
  `stats/stats_data.py`. None is re-added in HEAD.
- Shadowing: no framework `.py` in any `.aitask-scripts/` subdir shares a
  basename with `lib/*.py` today (checked), nor does any `tests/*.py`. TUIs that
  leave their own dir ahead of `lib/`: `board/aitask_board.py`,
  `board/trails_app.py`, `syncer/syncer_app.py`, `settings/settings_app.py`
  (parent dir). monitor/brainstorm/stats/codebrowser end with `lib/` first.
- Concurrency: `aitask_setup.sh` carries uncommitted t1852_6 hunks (L2398,
  L4968). Mine are elsewhere; commit must stage only my hunk.

## Implementation

### 1. Manifest — `.aitask-scripts/retired_scripts_manifest.txt` (new)
Same format as `retired_skills_manifest.txt`: header explaining why hashes,
record types, and the **regenerate recipe** (fast form):
```
comm -23 <(git log -m --format= --name-only --diff-filter=A -- .aitask-scripts/ | sort -u) \
         <(git ls-files .aitask-scripts/ | sort -u) | grep -v __pycache__      # paths
git log -m --no-renames --raw --no-abbrev --format= -- <paths> \
  | awk '{print $3; print $4}' | grep -v '^0\{40\}$' | sort -u              # SHAs
```
Records: **20 `FILE` lines** (incl. `lib/attachment_backends/local.sh`), then
the SHA set. Generated, not hand-typed. **No `DIR` record**: the helper's DIR
check is content-only against the flat SHA set, so a user-added
`attachment_backends/my_backend.sh` copied from `local.sh` would hash as
"known" and the whole dir would be deleted (reproduced by review). FILE
removes only the historically shipped filename; the emptied
`lib/attachment_backends/` dir is left behind (untracked by git, inert) —
stated in the manifest header.

### 2. Helper — `aitask_prune_retired_skills.sh` (small generalization)
- Add `--label <noun>` (default `skill`) used only in human wording: closing
  warning "N retired <label> path(s) were KEPT", "your own <label> at that
  name". Print the rendered-closure sentence only when STEM records were
  loaded (always true for the skills manifest ⇒ skills output unchanged).
- Update the header comment: the helper serves both manifests. Name kept (a
  rename would itself be a retirement; old installers never call it).

### 3. Wiring
- `install.sh`: factor `prune_retired_skills()` body into
  `_prune_retired <manifest> <noun> <none-msg>`; keep `prune_retired_skills`
  (identical messages) and add `prune_retired_scripts` (manifest
  `retired_scripts_manifest.txt`, label `script`, "No retired framework
  scripts present."). Call it right after `prune_retired_skills` in `main`
  ("Pruning retired framework scripts..."). Comment why: extraction is additive.
- `aitask_setup.sh`: same factoring for its `prune_retired_skills`; add
  `prune_retired_scripts "$SCRIPT_DIR/.."` called from `main` right before
  `commit_framework_files` (after the snapshot ⇒ deletion is committed, never
  treated as pre-existing dirt). `main` has no `project_dir` and the script
  runs under `set -u`, so the root is passed explicitly — the same expression
  `commit_framework_files` / `snapshot_pre_setup_dirty` use internally.

### 4. Shadow guard — `.aitask-scripts/lib/module_shadow_guard.py` (new)
`assert_lib_not_shadowed()`: lib dir = own dirname; lib module names = `*.py`
stems + packages in lib. Two checks:
1. each `sys.path` entry **before the first lib entry** (abspath-normalized,
   `''` = cwd) containing `<name>.py` or `<name>/__init__.py`;
2. any already-imported module in `sys.modules` with a lib name whose
   `__file__` is not under lib.
On a hit: print to stderr, naming each shadowing file and the lib module, the
likely cause (a file a framework release retired, left by an upgrade), and the
fix (`ait setup` prunes retired files; or `git rm <path>` then commit it by
name), then `raise SystemExit(1)`. Pure stdlib, no side effects otherwise.
Call it immediately after the `sys.path` block (before any other local
import) in `aitask_board.py`, `trails_app.py`, `syncer_app.py`,
`settings_app.py`. Add a short note to `aidocs/framework/tui_conventions.md`
"The board package" section: own-dir-first TUIs call the guard; no TUI-dir
module may share a `lib/` basename.

### 5. Docs
- `aidocs/framework/aitasks_extension_points.md`: new short section "Retiring
  or moving a file under `.aitask-scripts/`": add it to
  `retired_scripts_manifest.txt` (regenerate recipe), which the manifest test
  enforces. Website docs left untouched (`setup-install.md` is dirty from
  another session); offer a follow-up instead.

### 6. Tests
- `tests/test_retired_scripts_manifest.sh` (fast, no install):
  - every `FILE`/`DIR` path absent from `git ls-files` (a listed live path
    would be deleted after extraction — the catastrophic case);
  - completeness: every ever-added-minus-HEAD path under `.aitask-scripts/`
    is covered by a FILE or DIR record, and every blob from the recipe is in
    the SHA set (skip with a note on a shallow clone);
  - helper unit cases on a temp project: pristine retired file → PRUNED;
    modified → KEPT `unrecognized-content` + stderr names it with `rm` hint;
    unrelated user file untouched; manifest carries no `DIR` record (pinned,
    with the reason); `--label script` wording; second run prunes nothing.
- `tests/test_lib_shadow_guard.py`: synthetic `lib/` + `board/` tree in a tmp
  dir, run in a subprocess: board-first with stale `task_yaml.py` ⇒ exit 1 +
  stderr names `board/task_yaml.py`; lib-first ⇒ passes; no collision ⇒
  passes; pre-imported shadow in `sys.modules` ⇒ caught. Structural test: no
  git-tracked `.py` under `.aitask-scripts/<subdir>/` shares a basename with
  `lib/*.py`.
- `tests/test_upgrade_prunes_retired_scripts.sh` (acceptance, offline):
  - tarball built from this checkout like release.yml (ait, .aitask-scripts,
    packaging, skills/seed etc. as test_t644 does); a second tarball with
    `retired_scripts_manifest.txt` removed = **negative-control release**.
  - **setup `main()` wiring (W-style, as in `test_install_engine_binary.sh`
    `run_main`)**: source `aitask_setup.sh --source-only`, stub every function
    except `main`/loggers, with `snapshot_pre_setup_dirty`,
    `prune_retired_scripts` and `commit_framework_files` stubs echoing
    `CALL:<name>:<args>`; run `main` with `set -u` **kept on** (only `-e`
    relaxed) so an unbound variable aborts. Assert the prune call exists, its
    argument resolves to the project root, and the order is
    snapshot < prune < commit.
  - Fixtures = temp git repos, `HOME`/`AITASKS_HOME` redirected to temp,
    `AIT_TESTMAP_FETCH=0`: `git archive v0.31.0` and `git archive v0.36.1`
    framework trees (`.aitask-scripts`, `ait`, skills) + every retired path the
    tag does not ship, with byte content from the last tag that shipped it
    (`git show <tag>:<path>`) — reproduces the registry-scan shapes. Plus a
    locally modified `lib/codex_plan_policy.sh` and a user-authored
    `.aitask-scripts/my_tool.sh`. All committed; `.aitask-scripts/VERSION`
    tracked.
  - Run `install.sh --force --dir <fixture> --local-tarball <tarball>`. Assert
    per fixture: pristine leftovers gone from tree **and** from
    `git ls-files`; `git status --porcelain -- .aitask-scripts/` clean for
    them; the removal is in the commit install.sh created (`git show --stat
    HEAD`); modified file kept, output names it with cleanup hint; user file
    untouched; board import with `board/` first on `sys.path`
    (`~/.aitask/venv` python captured before HEAD redirect; skip only that
    sub-assert if no textual venv) succeeds.
  - Re-run install.sh and the setup path ⇒ no PRUNED, HEAD unchanged.
  - Setup path for already-current projects: fixture on the new release with
    leftovers re-added + committed; source fixture's `aitask_setup.sh
    --source-only`, run `snapshot_pre_setup_dirty`, `prune_retired_scripts`,
    `commit_framework_files` (non-interactive) ⇒ leftovers pruned & committed.
    (Behavioural half; the W test above pins that production `main` makes
    this call, in this order.)
  - Helper case for the DIR hole: `lib/attachment_backends/` with pristine
    `local.sh` + user `my_backend.sh` copied byte-for-byte from it ⇒ `local.sh`
    pruned, `my_backend.sh` and the dir kept.
  - Negative control: v0.36.1 fixture + no-manifest tarball ⇒
    `board/task_yaml.py` survives; raw `import task_yaml` with board first
    lacks `normalize_board_idx` (defect reproduced); board import exits 1 with
    the guard diagnostic (never an opaque ImportError).

### Post-phase (risk mitigations)
- **real_project_copy_check** (inline post-phase). **Not `cp -a`**: the
  original's `.aitask-data/.git` is `gitdir: /home/ddt/Work/thinking_app/.git/
  worktrees/-aitask-data` (absolute), so a copy's data commits would write the
  original's index and branch; its `origin` is the real GitHub remote. Instead
  **rebuild** an isolated copy in the scratchpad:
  1. `git clone --no-local --no-hardlinks <thinking_app> <copy>`; fetch the
     `aitask-data` branch into a local branch; `git -C <copy> remote remove
     origin` (no remote at all ⇒ nothing can be pushed anywhere);
     `git -C <copy> worktree add .aitask-data aitask-data`; create the
     `aitasks`/`aiplans` relative symlinks as the original has them.
  2. **Verify isolation before installing — abort the post-phase on any
     failure:** `git rev-parse --path-format=absolute --git-common-dir` for the
     copy and for `<copy>/.aitask-data` both under `<copy>`; every
     `git -C <copy> worktree list` path under `<copy>`; `git -C <copy> remote`
     empty; `find <copy> -type l -lname '/*'` empty (no absolute symlink back
     to the original); the 8 leftovers present and tracked.
  3. Run with `HOME=<scratch>/home AITASKS_HOME=<scratch>/aitasks_home
     AIT_TESTMAP_FETCH=0` (shim lands in the scratch HOME's `.local/bin`):
     `install.sh --force --dir <copy> --local-tarball <tarball>`.
  4. Confirm the 8 leftovers pruned and committed in the copy, the board
     imports, and that the original's HEAD, `aitask-data` HEAD and
     `git status --porcelain` are byte-identical to readings taken before
     step 1. Report the result; never modify the real project.

## Verification
- `bash tests/test_retired_scripts_manifest.sh`,
  `bash tests/test_upgrade_prunes_retired_scripts.sh`,
  `bash tests/test_prune_retired_skills.sh` (unchanged skills behaviour),
  `bash tests/test_t644_branch_mode_upgrade.sh`, `bash tests/test_setup_git.sh`
- `bash tests/run_all_python_tests.sh` (guard must not fire under any loader;
  read the last line verdict)
- `shellcheck` on the edited scripts.
- Commit: code by path; `aitask_setup.sh` staged via `git apply --cached` of
  my hunk only (t1852_6 hunks remain unstaged). Step 9: archive per workflow.

## Risk

### Code-health risk: medium
- The pruner deletes files in users' projects; a manifest entry for a path the release still ships would delete a live file after extraction · severity: medium · → mitigation: covered in-plan (manifest test asserts no listed path is in HEAD; completeness check)
- Editing two load-bearing installers, one with another session's uncommitted hunks (t1852_6) · severity: medium · → mitigation: covered in-plan (hunk-only staging; existing install/setup tests rerun)
- Startup shadow guard could false-positive under a test loader / flat sweep path and block a TUI · severity: low · → mitigation: covered in-plan (structural no-collision test + full python suite)

### Goal-achievement risk: medium
- Fixture fidelity: `git archive <tag>` approximates a real installed project (no real tarball, real projects may carry other drift) · severity: medium · → mitigation: inline post-phase real_project_copy_check
- The real-project copy check itself could write to the original repo (absolute data-worktree gitdir, real remote) · severity: high if unhandled · → mitigation: covered in-plan (rebuild as isolated clone, remove remote, verify isolation + compare original's state before/after)
- Pre-existing upstream defect: the skills pruner's DIR check is content-only, so a user-added file copied from a shipped blob inside a retired DIR is deleted with it · severity: low (no live trigger) · → mitigation: recorded as an upstream defect in Final Implementation Notes (follow-up offered at Step 8b), not fixed here
- A full `install.sh` run in a test may touch `$HOME` or the network · severity: low · → mitigation: covered in-plan (HOME/AITASKS_HOME redirect, AIT_TESTMAP_FETCH=0, local tarball)

### Planned mitigations
- inline post-phase · real_project_copy_check · inline_risk: low · added_complexity: low · Upgrade a scratch copy of thinking_app with this checkout and confirm prune + board import
