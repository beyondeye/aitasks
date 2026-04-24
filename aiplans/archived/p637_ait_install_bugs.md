---
Task: t637_ait_install_bugs.md
Base branch: main
plan_verified: []
---

# t637 — Fix `ait install` framework-update bugs

## Context

`ait install` is the update path for an already-installed aitasks framework inside a project repo. Three bugs currently make it hostile to iterative use (observed in `../aitasks-mobile`):

1. **Project settings are clobbered.** Seed config files (e.g., `project_config.yaml`, `codeagent_config.json`, `models_*.json`, `task_types.txt`) are copied over the top of existing user edits. Anything customized via `ait settings` or manually is lost on every update.
2. **Framework updates are not auto-committed.** When a project has previously committed its framework files (the `VERSION` file is tracked), running `ait install` leaves the updated `.aitask-scripts/`, skills, and so on uncommitted — the current `commit_installed_files()` only triggers on untracked files, not modifications of already-tracked ones.
3. **`__pycache__` is not gitignored inside `.aitask-scripts/`.** Python subdirectories (`board/`, `brainstorm/`, `lib/`, `settings/`, `agentcrew/`, `codebrowser/`, `monitor/`) accumulate `__pycache__/` on first use. The top-level repo has `__pycache__/` in its own `.gitignore`, but no `.gitignore` ships into `.aitask-scripts/` on install, so downstream projects end up tracking compiled bytecode.

User confirmed scope decisions (via AskUserQuestion): merge **all user-customizable seed files** (structured deep-merge for YAML/JSON, line-union for text lists, keep-existing for review-guide `.md` files); **commit only, no push** on auto-commit; scoped `.gitignore` inside `.aitask-scripts/`; deliver as a **single combined commit**.

## Design summary

- **New helper `.aitask-scripts/aitask_install_merge.py`** — small Python CLI with three subcommands: `yaml`, `json`, `text-union`. Reuses `lib/config_utils.deep_merge` for YAML/JSON. Invoked from `install.sh` as `python3 "$INSTALL_DIR/.aitask-scripts/aitask_install_merge.py" <mode> <src> <dest>`. Safe because `tar -xzf` extracts `.aitask-scripts/` before any `install_seed_*` runs, so the helper is always available by the time it's called.
- **Modify `install.sh`** — replace the `cp` under `FORCE=true` with merge calls in `install_seed_project_config`, `install_seed_codeagent_config`, `install_seed_models`, `install_seed_task_types`, `install_seed_reviewtypes`, `install_seed_reviewlabels`, `install_seed_reviewenvironments`. Switch `install_seed_reviewguides` to never-overwrite (keep-existing even under FORCE).
- **Template seed files stay as straight overwrite** — `install_seed_claude_settings`, `install_seed_codex_config`, `install_seed_gemini_config`, `install_seed_opencode_config` copy `*.seed.*` files into `aitasks/metadata/` purely as templates. These must be overwritten each install and stay out of the merge logic.
- **New `install_seed_aitask_scripts_gitignore()`** — copies `seed/aitask_scripts_gitignore.seed` → `.aitask-scripts/.gitignore` unconditionally (framework-owned, user doesn't edit it).
- **Rewrite `commit_installed_files()`** — gate on `git ls-files --error-unmatch .aitask-scripts/VERSION`. If untracked: no-op. If tracked: stage the full framework path list, `git rm -r --cached` any now-ignored `__pycache__/` paths, commit with `ait: Update aitasks framework to v<VERSION>`. No push.

## Files to modify

| File | Change |
|---|---|
| `install.sh` | Swap `cp` for merge-helper calls in 7 `install_seed_*` functions (1). Rewrite `commit_installed_files()` (2). Add `install_seed_aitask_scripts_gitignore()` and wire into `main()` (3). |
| `.aitask-scripts/aitask_install_merge.py` | **NEW** — merge CLI (yaml/json/text-union) reusing `lib/config_utils.deep_merge`. |
| `seed/aitask_scripts_gitignore.seed` | **NEW** — one-line `__pycache__/` (plus `*.pyc`, `*.pyo`). |
| `tests/test_install_merge.sh` | **NEW** — unit test bash suite for `aitask_install_merge.py` (yaml, json, text-union happy paths + edge cases). |
| `CHANGELOG.md` | Entry under next version: the three bug fixes. |
| `.aitask-scripts/VERSION` | Bump patch version (currently `0.17.3` → `0.17.4`). |

## Detailed steps

### Step 1 — Create the merge helper `.aitask-scripts/aitask_install_merge.py`

CLI: `python3 aitask_install_merge.py {yaml|json|text-union} <src> <dest>`

- `yaml`: load `src` + `dest` YAML, call `deep_merge(existing_dest, src)` so **existing values win** and only new keys from `src` are added. Dump back to `dest`. Import `deep_merge` from `config_utils` (script lives alongside `lib/`, so prepend `lib/` to `sys.path`).
- `json`: same as yaml, but JSON I/O.
- `text-union`: read `dest` lines (treat missing as empty), read `src` lines, append any `src` line not already present in `dest` (preserve order: existing lines first, then new). Blank lines and comment-only lines (`#`-prefix) pass through untouched.
- If `dest` doesn't exist: straight copy.
- Exit code 0 on success; 1 + stderr message on parse error.

Note on YAML comment preservation: PyYAML drops comments. Acceptable for `project_config.yaml` (no meaningful comments in the seed). Flag in commit message if needed.

### Step 2 — Patch `install.sh` seed installers

For each of the 7 affected `install_seed_*` functions, replace the `FORCE=true` branch with a merge call. Pattern:

```bash
install_seed_project_config() {
    local src="$INSTALL_DIR/seed/project_config.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/project_config.yaml"
    [[ -f "$src" ]] || { warn "No seed/project_config.yaml in tarball — skipping"; return; }
    mkdir -p "$(dirname "$dest")"
    if [[ ! -f "$dest" ]]; then
        cp "$src" "$dest"
        info "  Installed project config: project_config.yaml"
    elif [[ "$FORCE" == true ]]; then
        if python3 "$INSTALL_DIR/.aitask-scripts/aitask_install_merge.py" yaml "$src" "$dest"; then
            info "  Merged project config (kept existing values, added new keys): project_config.yaml"
        else
            warn "  Merge failed for project_config.yaml — leaving existing file untouched"
        fi
    else
        info "  Project config exists (kept): project_config.yaml"
    fi
}
```

Mode mapping:
| Function | Mode |
|---|---|
| `install_seed_project_config` | `yaml` |
| `install_seed_codeagent_config` | `json` |
| `install_seed_models` (loop) | `json` |
| `install_seed_task_types` | `text-union` |
| `install_seed_reviewtypes` | `text-union` |
| `install_seed_reviewlabels` | `text-union` |
| `install_seed_reviewenvironments` | `text-union` |

`install_seed_reviewguides`: change so that even when `FORCE=true`, if `dest` exists, **keep existing**. User edits to review guides are intentional. New guides (dest doesn't exist) still get installed.

Leave `install_seed_profiles` alone unless current behavior differs — inspect during implementation; likely already safe (profiles are user-owned YAMLs).

### Step 3 — Rewrite `commit_installed_files()` around the VERSION heuristic

```bash
commit_installed_files() {
    git -C "$INSTALL_DIR" rev-parse --is-inside-work-tree &>/dev/null || return

    # Heuristic: only auto-commit if the project has previously committed framework files.
    # .aitask-scripts/VERSION is the sentinel — it's always present after extraction
    # and its tracked-ness tells us whether this project opts into tracking framework code.
    if ! git -C "$INSTALL_DIR" ls-files --error-unmatch .aitask-scripts/VERSION &>/dev/null; then
        info "  .aitask-scripts/VERSION is not git-tracked — skipping auto-commit of framework updates."
        return
    fi

    local version="unknown"
    [[ -f "$INSTALL_DIR/.aitask-scripts/VERSION" ]] && version="$(cat "$INSTALL_DIR/.aitask-scripts/VERSION")"

    local paths_to_add=()
    local check_paths=(
        ".aitask-scripts/" "aitasks/metadata/" "aireviewguides/" "ait"
        ".claude/skills/" ".agents/" ".codex/" ".gemini/" ".opencode/"
        ".gitignore" ".github/workflows/" "CLAUDE.md" "GEMINI.md" "AGENTS.md" "opencode.json"
    )
    for p in "${check_paths[@]}"; do
        [[ -e "$INSTALL_DIR/$p" ]] && paths_to_add+=("$p")
    done
    [[ ${#paths_to_add[@]} -eq 0 ]] && return

    info "Committing framework update (v${version}) to git..."
    (
        cd "$INSTALL_DIR"
        # Stage adds + modifications.
        git add "${paths_to_add[@]}" 2>/dev/null || true
        # Remove tracked __pycache__ dirs that are now gitignored (one-time cleanup).
        git ls-files '.aitask-scripts/**/__pycache__/**' 2>/dev/null \
            | xargs -r git rm --cached --quiet 2>/dev/null || true
        if ! git diff --cached --quiet 2>/dev/null; then
            git commit -m "ait: Update aitasks framework to v${version}"
        fi
    ) && success "Framework update committed to git" \
      || warn "Could not commit framework update (non-fatal)."
}
```

Key behavior changes vs. current code:
- Gate on `git ls-files --error-unmatch .aitask-scripts/VERSION` (not on untracked-file presence).
- Commit on any staged diff (additions **or** modifications), not only when untracked.
- Commit message includes target version.
- Stage cleanup of now-ignored tracked `__pycache__/`.
- No `git push` — user pushes manually.

### Step 4 — Ship scoped `.gitignore` into `.aitask-scripts/`

**New file** `seed/aitask_scripts_gitignore.seed`:
```
__pycache__/
*.pyc
*.pyo
```

**New installer** in `install.sh`:
```bash
install_seed_aitask_scripts_gitignore() {
    local src="$INSTALL_DIR/seed/aitask_scripts_gitignore.seed"
    local dest="$INSTALL_DIR/.aitask-scripts/.gitignore"
    [[ -f "$src" ]] || { warn "No seed/aitask_scripts_gitignore.seed in tarball — skipping"; return; }
    cp "$src" "$dest"
    info "  Installed .aitask-scripts/.gitignore"
}
```

Wire into `main()` right after `install_skills` (ensures it's in place before `commit_installed_files` runs).

### Step 5 — Tests

`tests/test_install_merge.sh`:
- yaml merge: existing keys win, new seed-only keys added, nested dicts deep-merged, lists replaced wholesale (matches `config_utils.deep_merge` semantics).
- json merge: same coverage as yaml.
- text-union: existing order preserved, missing seed lines appended, duplicates not re-added, empty dest bootstrapped from seed.
- dest-absent fallback: plain copy for all three modes.
- Invalid YAML/JSON: non-zero exit, dest untouched.

Run with `bash tests/test_install_merge.sh`; assertions use the existing `assert_eq`/`assert_contains` helpers from other test files.

### Step 6 — Bump VERSION and add CHANGELOG entry

- `.aitask-scripts/VERSION`: `0.17.3` → `0.17.4`.
- `CHANGELOG.md`: one entry `## v0.17.4` covering all three fixes, with user-visible phrasing.

### Step 7 — Commit

Single combined commit per user preference:
```
bug: Fix ait install framework-update regressions (t637)

- Preserve existing project settings via deep-merge / line-union instead of
  overwriting seed files on ait install --force.
- Auto-commit framework updates only when .aitask-scripts/VERSION is
  git-tracked; include version in commit message.
- Ship .aitask-scripts/.gitignore so __pycache__ no longer leaks into
  downstream project repos.
```

## Verification

1. **Unit tests**: `bash tests/test_install_merge.sh` → all PASS.
2. **Lint**: `shellcheck .aitask-scripts/aitask_*.sh install.sh` → no new warnings.
3. **End-to-end smoke in `aitasks-mobile`** (separate worktree, non-destructive):
   - Before: snapshot `aitasks/metadata/project_config.yaml` (copy to `/tmp/pc.before`).
   - Hand-edit `project_config.yaml` to add a distinctive key (e.g., `tmux.default_session: aitasks_mob_smoke`).
   - Run `bash /path/to/dev/install.sh --force --dir /path/to/aitasks-mobile` (pointing at the dev tarball via env override — exact invocation worked out during implementation).
   - After: diff `project_config.yaml` — the smoke key must survive, any brand-new seed keys must be present.
   - Confirm `.aitask-scripts/.gitignore` was installed and `git check-ignore .aitask-scripts/board/__pycache__` returns exit 0.
   - Confirm `git log -1 --oneline` shows `ait: Update aitasks framework to v0.17.4`.
4. **Negative test — no auto-commit when VERSION untracked**: in a throwaway repo where `.aitask-scripts/VERSION` is gitignored / not added, run install and confirm no commit is created and the info line "VERSION is not git-tracked — skipping" is printed.
5. **Post-Implementation (Step 9 of task-workflow)**: normal archive + merge flow. No worktree (profile `fast` set `create_worktree: false`), so work happens on `main`.

## Out of scope / deferred

- Comment preservation in YAML (PyYAML limitation — would require ruamel.yaml dep; not warranted for current YAML content).
- `board_config.json`, `code_areas.yaml`, `crew_runner_config.yaml` — not currently touched by `install_seed_*` functions; leave alone.
- Cleaning up already-tracked `__pycache__` dirs in projects predating this fix — handled opportunistically by the one-time `git rm --cached` during the next auto-commit (step 3), no separate migration needed.

## Final Implementation Notes

- **Actual work done:** All seven planned changes landed — merge helper `aitask_install_merge.py` with yaml/json/text-union subcommands, eight `install_seed_*` functions patched to merge-or-keep via a new `merge_seed` bash helper, `commit_installed_files()` rewritten around the VERSION-tracked heuristic with inline one-time `__pycache__` cleanup, new seed `aitask_scripts_gitignore.seed` + installer function wired into `main()`, `tests/test_install_merge.sh` (20/20 PASS), VERSION bumped 0.17.3 → 0.17.4, CHANGELOG entry for v0.17.4.
- **Deviations from plan:**
  - **Profiles added to merge scope.** The plan said "leave `install_seed_profiles` alone unless current behavior differs". On inspection it had the same `FORCE=true → cp` overwrite bug, so it now uses `merge_seed yaml ...` — consistent with the other structured seed configs. Updated "Out of scope" to remove `profiles` from the list.
  - **`merge_seed` bash helper.** Plan showed inline merge branches per function. Extracted the common 10-line pattern into a single `merge_seed` helper defined just before `install_seed_profiles`. Each `install_seed_*` function is now a short wrapper around it. Reduces the diff footprint in install.sh by ~40 lines and keeps the fallback/warn message consistent across all 8 callers.
- **Issues encountered:**
  - `grep -qF "- b"` emitted a stderr usage warning in the test harness on the list-replacement test (dash prefix parsed as a flag). Fixed by adding `--` to the `grep -qF -- "$pattern"` calls in `assert_contains`/`assert_not_contains`. All 20 tests pass cleanly.
  - Pre-existing `shellcheck` findings on install.sh (SC2295, SC2015, SC1091) were verified as NOT introduced by this task. Left them alone per scope.
- **Key decisions:**
  - Helper lives at `.aitask-scripts/aitask_install_merge.py`, not in `seed/`. Rationale: by the time `install_seed_*` runs in install.sh, the tarball has already been extracted to `$INSTALL_DIR/.aitask-scripts/`, so the helper is on disk. Placing it in `seed/` would have worked too, but then the user-facing project would see a transient file disappear at `rm -rf seed/` at end of `main()`.
  - `merge_seed` calls `python3 ... 2>/dev/null` so merge-helper stderr (e.g. PyYAML warning messages on future YAML versions) doesn't pollute the install log. Merge failures still warn the user via the `else` branch.
  - `commit_installed_files` uses `git ls-files --error-unmatch` (silent success/fail) rather than `git ls-files | grep VERSION` — cleaner and avoids shell-quoting gotchas.
  - No `git push` in the auto-commit path. User pushes manually; keeps install safe to run without network or with a detached HEAD.
