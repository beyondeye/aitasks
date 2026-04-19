---
Task: t583_1_verification_parser_python_helper.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_2_*.md through aitasks/t583/t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_1 — Verification Parser (Python Helper)

## Context

First child of t583 (manual-verification module for `/aitask-pick`). Foundational state primitive — all other children depend on the parser subcommands it exposes.

Parent plan: `aiplans/p583_manual_verification_module_for_task_workflow.md` (full Integration Story and Cross-Cutting sections).

## Files to create/modify

**New:**
- `.aitask-scripts/aitask_verification_parse.py`
- `.aitask-scripts/aitask_verification_parse.sh` (one-line dispatcher: `exec python3 "$SCRIPT_DIR/aitask_verification_parse.py" "$@"`)

**Modify (whitelist — 5 touchpoints):**
- `.claude/settings.local.json`
- `.gemini/policies/aitasks-whitelist.toml`
- `seed/claude_settings.local.json`
- `seed/geminicli_policies/aitasks-whitelist.toml`
- `seed/opencode_config.seed.json`

Codex: skip (prompt-only model).

## Parser spec

**CLI subcommands** (see task file for full detail):
- `parse <task_file>` → `ITEM:<index>:<state>:<line_number>:<text>` per item (1-indexed).
- `set <task_file> <index> <state> [--note <text>]` → mutate in-place; append ` — <STATE> YYYY-MM-DD HH:MM [<note>]`; update `updated_at`.
- `summary <task_file>` → `TOTAL:N PENDING:A PASS:B FAIL:C SKIP:D DEFER:E`.
- `terminal_only <task_file>` → exit 0 if all terminal; exit 2 with `PENDING:<n>` / `DEFERRED:<n>`.
- `seed <task_file> --items <file>` → insert `## Verification Checklist` H2 with `- [ ]` items.

**Parser rules:**
- First H2 matching (case-insensitive) `^## (verification( checklist)?|checklist)\s*$`.
- Items match `^[ \t]*- \[([ x]|fail|skip|defer)\]\s+(.*)$`.
- Suffix: split on literal ` — `.

**Frontmatter:** simple line-based YAML update for `updated_at` only; no PyYAML dep. Atomic write via temp file + `os.replace()`.

## Implementation order

1. Write Python script with all 5 subcommands; use `argparse` subparsers.
2. Write bash wrapper.
3. `chmod +x` both.
4. Manual smoke test with a synthetic task file containing one of each state.
5. Update all 5 whitelist touchpoints. Commit the parser, wrapper, and whitelists together.

## Reference infrastructure

- Pattern: `.aitask-scripts/aitask_stats.py`, `aitask_codemap.sh` + `aitask_codemap.py`.
- `.aitask-scripts/lib/terminal_compat.sh` for any bash-side helpers.

## Verification

- Manual: synthetic task file → run each subcommand; inspect outputs and file mutations.
- Round-trip: `parse` → `set` → `parse` preserves state across mutations.
- Full unit tests land in t583_6.

## Final Implementation Notes

_To be filled in during implementation._
