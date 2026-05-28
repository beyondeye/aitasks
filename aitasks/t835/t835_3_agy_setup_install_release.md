---
priority: medium
effort: high
depends: [t835_2]
issue_type: feature
status: Ready
labels: [codeagent]
created_at: 2026-05-28 12:18
updated_at: 2026-05-28 12:18
---

## Context

Inverse counterpart of t812_3. Wires `agy` into the runtime install,
project setup, release packaging, and test infrastructure. Modeled on
the existing **codex** install path, with agy-specific simplifications
per `aidocs/geminicli_to_agy.md`:

- No local-policy install (agy reads `~/.gemini/policies/` globally —
  framework MUST NOT install local policies).
- No `agy_settings.seed.json` (agy has no per-project settings file).
- Likely no separate `agy_skills/` staging dir (shared root with
  codex via t834 — verify in t835_2 outcome).

Primary inverse reference: `aiplans/archived/p812/p812_3_remove_geminicli_setup_install_release_tests.md`
→ `### For t814 (add-agy): inverse instructions`.

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh`:
  - `_is_agent_installed()` case (L103) — add agy.
  - `assemble_aitasks_instructions()` docstring agent_type enum
    (~L974).
  - `update_agentsmd()` doc comment (~L1053).
  - "Other agents" orchestration block (~L1960) — add
    `if _is_agent_installed agy; then setup_agy_cli; fi`.
  - `commit_framework_files()::check_paths` (~L2340) — likely no
    `.agy/` entry needed (shared root).
  - **NEW** `setup_agy_cli()` modeled on `setup_codex_cli()`
    (L1718-1793) — lighter (no policy/settings merge).
- `install.sh`:
  - **NEW** `install_agy_staging()` modeled on
    `install_codex_staging()` (L466-489) — may be a thin stub if
    agy fully reuses codex staging.
  - **NEW** `install_seed_agy_config()` modeled on
    `install_seed_codex_config()` (L530-548) — copies
    `seed/agy_instructions.seed.md` and `seed/models_agy.json`.
  - Orchestration in main flow (L969-972) — add the two calls.
  - `commit_installed_files()::check_paths` (L700) — mirror setup
    decision.
- `.github/workflows/release.yml`:
  - Codex build step (L47-94) — add agy helper docs to copy loop
    only if agy ships distinct helper docs.
  - Tarball args (L94) — typically no new entry needed.
- `seed/`:
  - **NEW** `seed/agy_instructions.seed.md` — adapt codex's
    instructions seed with tool-name updates from
    `aidocs/geminicli_to_agy.md`.
  - **NEW** `seed/models_agy.json` — stub entry (replaced by t835_5).
  - Skip `agy_config.seed.toml`, `agy_rules.default.rules`,
    `agy_policies/`.
- `tests/test_agy_setup.sh` — **NEW** modeled on existing codex
  setup test.

## Reference Files for Patterns

- `setup_codex_cli()` and `install_codex_*` — direct mirror.
- `aidocs/adding_a_new_codeagent.md` §§ 17, 18, 19, 20, 21, 22 —
  setup/install/release playbook.
- `aidocs/geminicli_to_agy.md` §§ on global sandboxing and tool-name
  updates.

## Implementation Plan

1. Author `setup_agy_cli()`. Skip codex's policy/settings helpers
   (no equivalents needed). Copy any agy-specific helper docs only
   if t835_2 produced them.
2. Author `install_agy_staging()` and `install_seed_agy_config()`.
   Wire orchestration calls in `install.sh` main flow.
3. Update `_is_agent_installed` and the "Other agents" orchestration
   in `aitask_setup.sh`.
4. Update `assemble_aitasks_instructions()` docstring and
   `update_agentsmd()` comment.
5. Update `commit_framework_files()` / `commit_installed_files()`
   check_paths if agy introduces any new dotdir (probably not).
6. Update `release.yml` codex build step helper-doc copy loop (only
   if agy ships distinct helper docs). Verify tarball args.
7. Write `seed/agy_instructions.seed.md` and stub `seed/models_agy.json`.
8. Write `tests/test_agy_setup.sh` covering: idempotence, expected
   files/dirs after setup, no-policy-installed assertion.
9. Run install.sh end-to-end in a throwaway dir and confirm no
   regression for claude/codex/opencode.

## Verification Steps

- `bash tests/test_agy_setup.sh` passes.
- `./ait setup --reinstall` in a clean test dir detects agy when
  binary is on PATH and runs `setup_agy_cli()` cleanly.
- `bash install.sh` end-to-end in a throwaway dir succeeds.
- The release workflow can be dry-checked via
  `act` or by reading the workflow file; no broken paths.
- `ls -la ~/.agy/` after setup → directory does NOT exist (agy uses
  global config).
