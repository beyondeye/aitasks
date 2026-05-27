---
priority: medium
effort: medium
depends: [t812_2]
issue_type: chore
status: Done
labels: [geminicli, setup, ci]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 12:06
updated_at: 2026-05-27 17:48
completed_at: 2026-05-27 17:48
---

## Context

Third child of t812 (remove all geminicli support). This child strips
geminicli from the **setup/install/release pipeline and tests**. It
removes `aitask_setup.sh` gemini functions, `install.sh` gemini staging,
the GitHub Actions release workflow's gemini packaging steps, the seed
templates, and the gemini-specific test suite.

Does NOT touch agent identity (t812_1), skill rendering (t812_2), or
docs (t812_4).

## Key files to modify

- `.aitask-scripts/aitask_setup.sh` — delete:
  - `setup_gemini_cli()` (line 1716 region)
  - `merge_gemini_policies()` (line 1525 region)
  - `merge_gemini_settings()` (line 1623 region)
  - `install_gemini_global_policy()` (line 1602 region)
  - The `is_agent_installed()` gemini branch (line 103)
  - The `.gemini/` gitignore-skip entry (line 2656)
  - Any orchestration calls that invoke the deleted functions
    (lines 976, 2070, 2266)

- `install.sh` — delete:
  - `install_gemini_staging()` (line 563 region)
  - `install_seed_gemini_config()` (line 623 region)
  - The `.gemini/` gitignore-skip entry (lines 776, 1051, 1054)
  - The orchestration call at line 481

- `.github/workflows/release.yml` — remove all gemini build /
  packaging steps (commands, skills, policies, settings packaging).

## Files / directories to delete

- `seed/geminicli_policies/` (entire directory).
- `seed/geminicli_settings.seed.json`.
- `seed/geminicli_instructions.seed.md`.
- `seed/models_geminicli.json`.
- `tests/test_gemini_setup.sh`.

## Reference files for patterns

- The codex equivalent in `aitask_setup.sh` (search for
  `setup_codex_cli`, `install_codex_*`) is the closest analogue for
  what t814 will add for agy. Note codex's lighter footprint — no
  policy install — because codex (like agy) uses global sandboxing.

## Implementation plan

1. Surgically delete each gemini function and its orchestration
   calls in `aitask_setup.sh`. Run `shellcheck` after each chunk to
   confirm no orphaned references.
2. Same for `install.sh`.
3. Edit `.github/workflows/release.yml` and remove every gemini
   step. Confirm the YAML still parses (`gh workflow view` or
   `actionlint` if available).
4. Delete the seed directory and files.
5. Delete `tests/test_gemini_setup.sh`.
6. Verify:

```bash
grep -n 'gemini\|geminicli' \
  .aitask-scripts/aitask_setup.sh \
  install.sh \
  .github/workflows/release.yml \
  seed/
# Expect: empty
```

## Verification

1. `shellcheck .aitask-scripts/aitask_setup.sh install.sh` — no new
   warnings.
2. Each remaining `tests/test_*setup*.sh` passes (e.g., codex setup
   tests, claude setup tests).
3. Spot-check `bash .aitask-scripts/aitask_setup.sh --dry-run` (or
   equivalent) — no crash on missing gemini functions.
4. `gh workflow view release.yml` parses successfully (or YAML
   parses via `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"`).

## Final implementation notes — REQUIRED subsection

Include a top-level subsection titled exactly:

```
### For t814 (add-agy): inverse instructions
```

Contents:
- **Files re-touched by agy:** repeat the file list with absolute
  line ranges where modified.
- **Pattern removed (anchor example):** function names removed
  (e.g., `setup_gemini_cli`, `install_gemini_staging`).
- **Inverse instruction:** "to add agy: implement
  `setup_agy_cli()` modeled on `setup_codex_cli()` (the lighter
  version — no policy install because agy uses global sandboxing).
  In `install.sh`, mirror `install_codex_*` for agy. In
  `release.yml`, mirror codex packaging steps."
- **Hidden coupling discovered during removal:** any subtle
  ordering constraints, gitignore-skip entries, or
  agent-install-marker writes (`.aitask-installed-<agent>`).
