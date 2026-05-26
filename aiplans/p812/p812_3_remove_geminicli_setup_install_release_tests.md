---
Task: t812_3_remove_geminicli_setup_install_release_tests.md
Parent Task: aitasks/t812_remove_gemini_support.md
Sibling Tasks: aitasks/t812/t812_1_*.md, aitasks/t812/t812_2_*.md, aitasks/t812/t812_4_*.md, aitasks/t812/t812_5_*.md
Archived Sibling Plans: aiplans/archived/p812/p812_1_*.md, aiplans/archived/p812/p812_2_*.md (after archived)
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified: []
---

# Plan: Remove geminicli from setup/install/release + tests (t812_3)

## Context

Third child of t812. Strips geminicli from the
**setup / install / release pipeline and tests**. The codex
equivalent functions (`setup_codex_cli`, `install_codex_*`) are the
nearest analogue — note codex's lighter footprint (no policy install)
because codex (like agy) uses global sandboxing.

## Key files to modify

### `.aitask-scripts/aitask_setup.sh` — delete

- `setup_gemini_cli()` (line 1716 region)
- `merge_gemini_policies()` (line 1525 region)
- `merge_gemini_settings()` (line 1623 region)
- `install_gemini_global_policy()` (line 1602 region)
- The `is_agent_installed()` gemini branch (line 103)
- The `.gemini/` gitignore-skip entry (line 2656)
- Any orchestration calls invoking the deleted functions (lines 976,
  2070, 2266)

### `install.sh` — delete

- `install_gemini_staging()` (line 563 region)
- `install_seed_gemini_config()` (line 623 region)
- The `.gemini/` gitignore-skip entries (lines 776, 1051, 1054)
- The orchestration call at line 481

### `.github/workflows/release.yml`

- Remove every gemini build/packaging step (commands, skills,
  policies, settings packaging).

## Files / directories to delete

- `seed/geminicli_policies/` (entire dir).
- `seed/geminicli_settings.seed.json`.
- `seed/geminicli_instructions.seed.md`.
- `seed/models_geminicli.json`.
- `tests/test_gemini_setup.sh`.

## Step-by-step

1. In `aitask_setup.sh`, delete each `*_gemini_*` function and its
   orchestration calls. `shellcheck` after each chunk.
2. In `install.sh`, same — delete the two staging/install functions
   and their orchestration call.
3. Edit `.github/workflows/release.yml`. Confirm YAML still parses:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
   ```
4. Delete the seed directory and files.
5. Delete `tests/test_gemini_setup.sh`.
6. Final grep check:
   ```bash
   grep -n 'gemini\|geminicli' \
     .aitask-scripts/aitask_setup.sh \
     install.sh \
     .github/workflows/release.yml
   ls seed/ | grep -i gemini  # expect empty
   ```

## Verification

1. `shellcheck .aitask-scripts/aitask_setup.sh install.sh` — no new
   warnings.
2. Remaining `tests/test_*setup*.sh` (codex setup, claude setup) pass.
3. Spot-check setup script syntax: `bash -n .aitask-scripts/aitask_setup.sh`.
4. `.github/workflows/release.yml` parses successfully (Python YAML
   check above).
5. `ls seed/ | grep -i gemini` — empty.

## Step 9 (Post-Implementation)

Standard archival. Final Implementation Notes **must** include the
`### For t814 (add-agy): inverse instructions` subsection.

## Final Implementation Notes (template)

- **Actual work done:** …
- **Deviations from plan:** …
- **Issues encountered:** …
- **Key decisions:** …
- **Upstream defects identified:** None (or list)
- **Notes for sibling tasks:** …

### For t814 (add-agy): inverse instructions

- **Files re-touched by agy:** (file list + line ranges of deletions).
- **Pattern removed (anchor example):** function names removed
  (`setup_gemini_cli`, `install_gemini_staging`, etc.).
- **Inverse instruction:** to add agy, implement `setup_agy_cli()`
  modeled on `setup_codex_cli()` (lighter — no policy install
  because agy handles policies globally). In `install.sh`, mirror
  `install_codex_*` for agy. In `release.yml`, mirror codex
  packaging steps. Add `seed/agy_instructions.seed.md` (adapt
  geminicli's Layer-2 instructions with the tool-name updates per
  `aidocs/geminicli_to_agy.md`) and `seed/models_agy.json`.
- **Hidden coupling discovered during removal:** ordering
  constraints, gitignore-skip entries, agent-install markers
  (`.aitask-installed-<agent>`), etc.
