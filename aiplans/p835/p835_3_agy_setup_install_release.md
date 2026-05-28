---
Task: t835_3_agy_setup_install_release.md
Parent Task: aitasks/t835_add_agy_antigravity_cli_support.md
Sibling Tasks: aitasks/t835/t835_1_*.md, aitasks/t835/t835_2_*.md, aitasks/t835/t835_4_*.md, aitasks/t835/t835_5_*.md, aitasks/t835/t835_6_*.md
Archived Sibling Plans: aiplans/archived/p835/p835_1_*.md, aiplans/archived/p835/p835_2_*.md (after they archive)
Inverse Blueprint: aiplans/archived/p812/p812_3_remove_geminicli_setup_install_release_tests.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Overview

Wire `agy` into runtime install (`install.sh`), project setup
(`aitask_setup.sh`), release packaging (`release.yml`), seed files
(`seed/`), and test infrastructure. Modeled on existing **codex**
install path with agy-specific simplifications per
`aidocs/geminicli_to_agy.md`: no local-policy install (global
`~/.gemini/policies/`), no `agy_settings.seed.json`, likely no
separate `agy_skills/` staging dir.

The full file-by-file plan lives in the task description. The
**load-bearing reference** is the `### For t814 (add-agy): inverse
instructions` subsection in
`aiplans/archived/p812/p812_3_remove_geminicli_setup_install_release_tests.md`.

## Order of operations

1. **Author `setup_agy_cli()`** in `aitask_setup.sh`, modeled on
   `setup_codex_cli()` (L1718-1793). Drop codex's
   `merge_codex_settings` / `merge_codex_rules` equivalents (agy uses
   global sandboxing). Copy any agy-specific helper docs only if
   t835_2 produced them.

2. **Wire orchestration:** `_is_agent_installed()` case for agy;
   "Other agents" block adds
   `if _is_agent_installed agy; then setup_agy_cli; fi`. Update
   `assemble_aitasks_instructions()` docstring agent_type enum and
   `update_agentsmd()` doc comment.

3. **`check_paths` decision:** Determine whether agy introduces any
   new dotdir (e.g. `.agy/`). Per `aidocs/geminicli_to_agy.md`
   probably none — verify and skip if so.

4. **Author `install_agy_staging()` + `install_seed_agy_config()`**
   in `install.sh`, modeled on the codex equivalents. The staging
   function may be a thin no-op if agy fully reuses `codex_skills/`
   via shared root (decided in t835_2). Wire orchestration calls in
   main install flow.

5. **Release packaging:** `.github/workflows/release.yml` — update
   helper-doc copy loop only if agy ships distinct helper docs;
   tarball args usually unchanged.

6. **Author seed files:**
   - `seed/agy_instructions.seed.md` — adapt codex's seed with
     tool-name updates from `aidocs/geminicli_to_agy.md`.
   - `seed/models_agy.json` — stub (real catalog from t835_5).
   - Skip `agy_config.seed.toml`, `agy_rules.default.rules`,
     `agy_policies/`.

7. **Author `tests/test_agy_setup.sh`** modeled on the codex setup
   test. Cover: idempotence, expected files/dirs after setup,
   no-local-policy assertion.

8. **End-to-end smoke:** Run `bash install.sh` in a clean throwaway
   dir; run `./ait setup --reinstall` in another throwaway dir with
   agy on PATH; verify both flows succeed without regression for
   claude/codex/opencode.

## Verification

- `bash tests/test_agy_setup.sh` passes.
- `./ait setup --reinstall` in a clean test dir detects agy when binary is on PATH and runs `setup_agy_cli()` cleanly.
- `bash install.sh` end-to-end in a throwaway dir succeeds.
- After setup, `ls ~/.agy/ 2>&1` shows the directory does NOT exist (agy uses global config).
- Release workflow dry-check (read workflow file; optional `act` run) shows no broken paths.

## Step 9 reference

Standard task-workflow Step 9 archive after Step 8 approval.
