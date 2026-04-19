---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [framework, skill, task_workflow, verification]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 08:29
updated_at: 2026-04-19 09:41
---

## Context

First child of t583 (manual-verification module). This task builds the **foundational state primitive** — a Python helper (plus thin bash wrapper) that parses and mutates the `## Verification Checklist` section in a manual-verification task body. All subsequent children depend on this.

The user explicitly requested Python over bash during planning review: markdown parsing with `sed`/`grep` is error-prone across macOS (BSD) and Linux (GNU). Python follows the existing `.aitask-scripts/aitask_*.py` pattern (see `aitask_codemap.py`, `aitask_stats.py`).

## Key Files to Modify

- `.aitask-scripts/aitask_verification_parse.py` — **new file**, main logic.
- `.aitask-scripts/aitask_verification_parse.sh` — **new file**, one-line dispatcher: `exec python3 "$SCRIPT_DIR/aitask_verification_parse.py" "$@"`.
- `.claude/settings.local.json` — whitelist `aitask_verification_parse.sh`.
- `.gemini/policies/aitasks-whitelist.toml` — whitelist entry.
- `seed/claude_settings.local.json` — mirror.
- `seed/geminicli_policies/aitasks-whitelist.toml` — mirror.
- `seed/opencode_config.seed.json` — mirror.

## Reference Files for Patterns

- `.aitask-scripts/aitask_stats.py` — existing Python helper structure (argparse, `main()`).
- `.aitask-scripts/aitask_codemap.sh` + `aitask_codemap.py` — bash-wrapper + Python pattern.
- `.aitask-scripts/lib/terminal_compat.sh` — `sed_inplace()`, `die()`, `warn()`, `info()`.
- `aitasks/t571/t571_7_manual_verification_structured_brainstorming.md` — real-world checklist format the parser must handle.

## Implementation Plan

1. **CLI subcommands:**
   - `parse <task_file>` — emit `ITEM:<index>:<state>:<line_number>:<text>` per item (1-indexed). `<state>` ∈ `pending|pass|fail|skip|defer`.
   - `set <task_file> <index> <state> [--note <text>]` — mutate body in place: flip checkbox, append ` — <STATE> YYYY-MM-DD HH:MM [<note>]`; refresh frontmatter `updated_at`.
   - `summary <task_file>` — one line: `TOTAL:N PENDING:A PASS:B FAIL:C SKIP:D DEFER:E`.
   - `terminal_only <task_file>` — exit 0 if all items are terminal (`pass`/`fail`/`skip`); else exit 2 with `PENDING:<count>` and/or `DEFERRED:<count>` lines.
   - `seed <task_file> --items <file>` — insert a `## Verification Checklist` H2 at end of body with one `- [ ]` item per line in the items file. If section exists, error.

2. **Parser rules:**
   - Locate first H2 matching (case-insensitive) regex `^## (verification( checklist)?|checklist)\s*$`.
   - Scan lines until next H2 or EOF; match items via `^[ \t]*- \[([ x]|fail|skip|defer)\]\s+(.*)$`.
   - Suffix parsing: split on ` — ` literal; everything after is state annotation (timestamp + note).

3. **Frontmatter handling:** Use simple line-based YAML parsing for `updated_at` field update; do not pull in PyYAML. Write atomic: `file.replace()` on a temp copy.

4. **Bash wrapper:** Single-line dispatcher so call sites use the `.sh` name.

5. **Whitelist updates (all 5 touchpoints):** Follow the parent plan's Cross-Cutting section exactly. Codex: skip.

## Verification Steps

- Manually: create a synthetic task file with `## Verification Checklist` and 5 items of varying states; run each subcommand; inspect output + file mutations.
- Unit tests live in t583_6 (they depend on this helper landing first).
- `./.aitask-scripts/aitask_verification_parse.sh parse <file>` should round-trip through `set` and back to `parse` without drift.

## Step 9 reminder

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for post-implementation merge/archival. Commit format: `feature: Add verification parser (t583_1)`.
