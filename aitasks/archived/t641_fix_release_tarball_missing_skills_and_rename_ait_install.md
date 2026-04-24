---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [release, install, skills, refactor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-24 11:18
updated_at: 2026-04-24 15:57
completed_at: 2026-04-24 15:57
---

## Symptom

After running `ait install` in `../aitasks_mobile` (upgrading from an existing v0.17.x install), several framework files that exist locally are missing in the target project. Comparison of `.claude/skills/` between local (v0.17.4) and `../aitasks_mobile` (v0.17.3):

- `.claude/skills/ait-git/` — missing
- `.claude/skills/task-workflow/` — missing (critical: 23 sub-docs referenced by nearly every `/aitask-*` skill)
- `.claude/skills/user-file-select/` — missing

(`.aitask-scripts/aitask_install_merge.py` is also missing, but that is expected — it was introduced post-v0.17.3 in commit a69844e6 for t637 and will ship with v0.17.4. Not in scope for this task.)

## Root cause — two separate bugs

### Bug 1: release glob excludes helper skills

`.github/workflows/release.yml` (the "Build skills directory from .claude/skills" step) iterates with the glob `.claude/skills/aitask-*/`. The glob only matches names starting with `aitask-`, so `ait-git/`, `task-workflow/`, and `user-file-select/` are silently dropped from every tarball — they have never shipped. The same `aitask-*/` pattern is used in the codex, opencode, and gemini build steps, and in `install.sh` when unpacking the tarball; the codex/opencode/gemini trees currently don't hold non-`aitask-*` skills, so this is latent there.

### Bug 2: install.sh copies only `SKILL.md`, losing sub-docs

`install.sh:198` does:

```bash
cp "$skill_dir/SKILL.md" "$INSTALL_DIR/.claude/skills/$skill_name/SKILL.md"
```

For skills that ship sub-documents alongside `SKILL.md`, only the top-level file lands on the target. Today this is already observably broken for `aitask-qa/` (6 sub-docs — `change-analysis.md`, `follow-up-task-creation.md`, `task-selection.md`, `test-discovery.md`, `test-execution.md`, `test-plan-proposal.md` — are all absent from `../aitasks_mobile/.claude/skills/aitask-qa/`). Once Bug 1 is fixed and `task-workflow/` is included, the same issue will drop its 23 sub-docs unless Bug 2 is also fixed.

The same `cp "$skill_dir/SKILL.md"` pattern repeats for codex (`install.sh:432`) and opencode (`install.sh:460`). Should be fixed in all three places for symmetry, even though current codex/opencode skills are flat.

## Fixes

1. **`.github/workflows/release.yml`** — change the "Build skills directory from .claude/skills" step glob from `.claude/skills/aitask-*/` to `.claude/skills/*/`. Apply the same change to the codex (`.agents/skills/aitask-*/`), opencode (`.opencode/skills/aitask-*/`), and gemini `gemini_skills` build steps for consistency (no functional change today for those trees, but prevents the same drift next time a helper skill is added).

2. **`install.sh`** — in `install_skills()`, replace:
   ```bash
   cp "$skill_dir/SKILL.md" "$INSTALL_DIR/.claude/skills/$skill_name/SKILL.md"
   ```
   with:
   ```bash
   cp -r "$skill_dir"/. "$INSTALL_DIR/.claude/skills/$skill_name/"
   ```
   and broaden the loop glob from `"$INSTALL_DIR/skills"/aitask-*/` to `"$INSTALL_DIR/skills"/*/`. Apply matching changes in the codex skills block (around line 427) and opencode skills block (around line 455).

3. **Release-artifact smoke test** — add a new `tests/test_release_tarball.sh` (or extend an existing release-side test) that:
   - Runs the release workflow's tar-build steps against the working tree (or unpacks a fixture tarball).
   - Asserts `skills/task-workflow/planning.md`, `skills/task-workflow/SKILL.md`, `skills/ait-git/SKILL.md`, `skills/user-file-select/SKILL.md`, and `skills/aitask-qa/change-analysis.md` exist in the staged tarball.
   - Asserts `install.sh --local-tarball` produces `.claude/skills/task-workflow/planning.md` and `.claude/skills/aitask-qa/change-analysis.md` in the target directory.

4. **Rename `ait install` → `ait upgrade`**. Rationale: `ait install` is misleading — it updates an existing framework installation, not performs a first-time install (`ait setup` does that). But `ait update` is already taken for task-frontmatter edits (`aitask_update.sh`). `upgrade` is unambiguous, matches the verbs users know from `apt upgrade` / `brew upgrade` / `gem upgrade`, and is distinct from both `update` (task) and `setup` (bootstrap).

   Implementation:
   - Rename `.aitask-scripts/aitask_install.sh` → `.aitask-scripts/aitask_upgrade.sh`. Inside, adjust the help/usage text to use `ait upgrade`.
   - Update the `ait` dispatcher (`ait:159-160`): add an `upgrade` case dispatching to `aitask_upgrade.sh`; keep an `install` case that emits a one-line warning (`"ait install is deprecated — use 'ait upgrade' instead"`) and then `exec`s the same script. Mark the alias for removal in a follow-up (see Post-Review Changes note below).
   - Also update line 152 (`help|--help|-h|--version|-v|install|setup|...`) to include `upgrade` alongside `install` in the no-sync list.
   - Update `aitask_install.sh`'s self-reference to `aitask_upgrade.sh` if anything under `.aitask-scripts/` or `seed/` invokes it by filename (grep first).
   - Update `check_for_updates` output string in `ait` (the "update available" hint currently suggests running `ait install`; point it at `ait upgrade`).
   - Update user-facing docs: `website/`, `README.md`, `CHANGELOG.md` entry.
   - Surface as **Post-Review Changes** any references in seed/ that point at `ait install`.

## Out of scope

- Re-releasing v0.17.3. The fix lands in v0.17.4 (or the next release), and downstream users run `ait upgrade` (née `ait install`) to receive it.
- Changes to codex/opencode/gemini skill trees. Current helper skills are Claude-only by design; if they become shared later, the release workflow already has the broadened glob waiting.
- `aitask_install_merge.py` shipping — already handled by the v0.17.4 tag.

## Verification steps

- `grep -rn 'aitask-\*/' .github/workflows/release.yml install.sh` returns nothing after the fix.
- Run `tests/test_release_tarball.sh` — passes.
- On a scratch copy of a downstream project, build the tarball locally, run `install.sh --local-tarball ./aitasks-*.tar.gz --force`, and confirm:
  - `.claude/skills/task-workflow/planning.md` exists
  - `.claude/skills/ait-git/SKILL.md` exists
  - `.claude/skills/user-file-select/SKILL.md` exists
  - `.claude/skills/aitask-qa/change-analysis.md` exists
- `ait upgrade` works; `ait install` still works but prints the deprecation warning.
