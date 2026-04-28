---
Task: t691_1_phase1_skill_wrapper_audit_port.md
Parent Task: aitasks/t691_audit_and_port_aitask_wrappers_across_code_agents.md
Sibling Tasks: aitasks/t691/t691_2_phase2_helper_whitelist_audit.md, aitasks/t691/t691_3_website_docs_audit_wrappers.md
Worktree: (current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 11:11
---

# Plan: t691_1 — Phase 1 skill-wrapper audit and port

## Summary

Build the `aitask-audit-wrappers` skill end-to-end with **Phase 1** subcommands only: scan source-of-truth `.claude/skills/aitask-*/SKILL.md` against the four wrapper trees, render missing wrappers from heredoc templates, insert missing `activate_skill` policy entries, self-bootstrap this skill's own wrappers, whitelist the new helper script in all 5 touchpoints, run the helper to close the documented Phase-1 gaps, and verify idempotency.

## Authoritative gap matrix (verified 2026-04-28; closed in this child)

| Skill | `.gemini/commands` | `.agents/skills` | `.opencode/skills` | `.opencode/commands` | gemini policy runtime | gemini policy seed |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| aitask-add-model | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| aitask-contribution-review | OK | OK | OK | OK | MISSING | OK |
| aitask-qa | OK | OK | OK | MISSING | MISSING | MISSING |

## Step 1 — Build `.aitask-scripts/aitask_audit_wrappers.sh` (~450 LOC)

Boilerplate header (matches sibling helper scripts):

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
source "${SCRIPT_DIR}/lib/task_utils.sh"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
```

### Subcommands (Phase 1 scope)

- `discover` — list all source-of-truth `aitask-*` skills, check each of the 4 trees, emit `GAP:<tree>:<skill>` lines.
- `discover-policy` — check both `.gemini/policies/aitasks-whitelist.toml` and `seed/geminicli_policies/aitasks-whitelist.toml` for `activate_skill` rules; emit `POLICY_GAP:<runtime|seed>:<skill>`.
- `render-wrapper <tree> <skill_name>` — write template to stdout. `tree` is one of `gemini`, `agents`, `opencode-skill`, `opencode-command`. Templates inlined as heredocs.
- `apply-wrapper <tree> <skill_name>` `[--force]` — write rendered wrapper to canonical path. Refuses to overwrite unless `--force`. Emits `WROTE:<path>`.
- `apply-policy <runtime|seed> <skill_name>` — insert `[[rule]]` block at alphabetical position (use `awk` to find the right insert point between existing `argsPattern = "..."` lines). Emits `WROTE:<path>:<line>`.

### Frontmatter description extraction

Use the existing `read_yaml_field` from `task_utils.sh`:

```bash
local source_md=".claude/skills/${skill_name}/SKILL.md"
local description
description=$(read_yaml_field "$source_md" "description")
```

For OpenCode/Codex `## Arguments` summary, grep the source SKILL.md for the first paragraph under `## Usage` or `## Arguments`. If neither section exists or the body is empty, emit `ARGS_AMBIGUOUS:<skill_name>` and let the SKILL.md surface it for user confirmation per gap.

### Wrapper templates (heredoc within the helper)

Already documented in t691's task description; render-wrapper builds these strings and emits to stdout. The helper only writes files when the user approves via SKILL.md flow.

### Alphabetical-insert helper (TOML policy)

Implemented as a small awk function for reuse between `apply-policy` and the helper-whitelist subcommand in Phase 2:

```bash
insert_activate_skill_rule() {
  local target_file="$1" skill_name="$2"
  awk -v skill="$skill_name" '
    BEGIN { inserted = 0 }
    /^toolName = "activate_skill"$/ {
      buf = $0
      getline next_line
      if (!inserted && match(next_line, /argsPattern = "([^"]+)"/, m) && m[1] > skill) {
        printf "[[rule]]\ntoolName = \"activate_skill\"\nargsPattern = \"%s\"\ndecision = \"allow\"\npriority = 100\n\n", skill
        inserted = 1
      }
      print buf "\n" next_line
      next
    }
    { print }
    END {
      if (!inserted) {
        printf "\n[[rule]]\ntoolName = \"activate_skill\"\nargsPattern = \"%s\"\ndecision = \"allow\"\npriority = 100\n", skill
      }
    }
  ' "$target_file" > "$target_file.tmp"
  mv "$target_file.tmp" "$target_file"
}
```

(Note: the actual implementation will need to walk back to insert the full `[[rule]]` block before the matching `toolName` line; the awk above is a sketch — final implementation refines it during coding.)

## Step 2 — Build `.claude/skills/aitask-audit-wrappers/SKILL.md` (~200 lines)

Workflow shape (modeled on `aitask-add-model`):

1. **Step 1 — argument parse.** Reserve `--phase=skills|whitelist|all` for child 2; child 1 supports only `--phase=skills` (the default in this child).
2. **Step 2 — discovery.** Run `discover` + `discover-policy`; print matrix.
3. **Step 3 — per-gap diff.** For each `GAP:` line, render the wrapper and show a 2-line preview (first frontmatter line + first content line). Use `AskUserQuestion` with `multiSelect: true` to collect approval. Per-gap option label = `<tree>: <skill_name>`.
4. **Step 4 — apply.** For each approved gap, run `apply-wrapper` / `apply-policy`. Collect `WROTE:` lines.
5. **Step 5 — commit.** Two commits required:
   - Code commit: `git add` the new wrapper files, policy edits, helper script, CLAUDE.md fix.
   - The `--phase=skills` commit message: `feature: Audit and port aitask skill wrappers across code-agent trees (t691_1)`.
6. **Step 6 — idempotency assert.** Re-run `discover` + `discover-policy`; if either emits anything, fail loudly.

## Step 3 — Self-bootstrap wrappers (hand-written)

Because the helper does not yet exist when this child runs, the four wrappers for `aitask-audit-wrappers` itself are written by hand:

- `.gemini/commands/aitask-audit-wrappers.toml`
- `.agents/skills/aitask-audit-wrappers/SKILL.md`
- `.opencode/skills/aitask-audit-wrappers/SKILL.md`
- `.opencode/commands/aitask-audit-wrappers.md`

Description (used in all four):

> "Audit and port aitask skill wrappers across code-agent trees, plus helper-script whitelist coverage."

Add `[[rule]]` `activate_skill` entries for `aitask-audit-wrappers` to:
- `.gemini/policies/aitasks-whitelist.toml`
- `seed/geminicli_policies/aitasks-whitelist.toml`

Alphabetical position: between `aitask-add-model` (after this child closes that gap) and `aitask-changelog`.

## Step 4 — Whitelist `aitask_audit_wrappers.sh` (5 touchpoints)

| # | Touchpoint | Entry shape | Insert position |
|---|---|---|---|
| 1 | `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_audit_wrappers.sh:*)"` in `permissions.allow` | alphabetical between `aitask_archive.sh` and `aitask_board.sh` |
| 2 | `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block with `commandPrefix = "./.aitask-scripts/aitask_audit_wrappers.sh"` | alphabetical position |
| 3 | `seed/claude_settings.local.json` | mirror of #1 | mirror |
| 4 | `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of #2 | mirror |
| 5 | `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_audit_wrappers.sh *": "allow"` | alphabetical position |

(Codex `.codex/config.toml` exception: prompt-only — no entry.)

## Step 5 — First-run gap closure (drives the helper to write the documented gaps)

Once the helper is in place + self-bootstrap is done + helper is whitelisted, drive the helper to close the documented gaps. Practical sequence (any of: invoke helper subcommands, hand-write equivalent files):

- 4 wrappers for `aitask-add-model` (one per tree).
- 1 wrapper for `aitask-qa` in `.opencode/commands/aitask-qa.md`.
- 3 runtime gemini policy entries: `aitask-add-model`, `aitask-contribution-review`, `aitask-qa`.
- 2 seed gemini policy entries: `aitask-add-model`, `aitask-qa`.

After this step, `discover` and `discover-policy` must both produce empty output.

## Step 6 — CLAUDE.md fix

The "Codex CLI" subsection of "WORKING ON SKILLS / CUSTOM COMMANDS" currently says commands live in `.codex/prompts/`. That directory does not exist on disk; codex shares `.agents/skills/` with gemini. Update the sentence to match the actual layout.

## Step 7 — Verification

1. `bash tests/test_opencode_setup.sh` — pass (counts auto-adjust per t679).
2. `bash tests/test_gemini_setup.sh` — pass.
3. `bash .aitask-scripts/aitask_audit_wrappers.sh discover` — empty output.
4. `bash .aitask-scripts/aitask_audit_wrappers.sh discover-policy` — empty output.
5. `shellcheck .aitask-scripts/aitask_audit_wrappers.sh` — clean.
6. Spot-check files exist (see task description verification block).
7. Confirm both gemini policies contain `activate_skill` rules for `aitask-add-model`, `aitask-contribution-review`, `aitask-qa`, `aitask-audit-wrappers`.

## Step 9 — Post-implementation

Standard task-workflow archival:
- Code commit (regular `git`): wrapper files + helper + CLAUDE.md + whitelist edits.
- Plan commit (`./ait git`): this plan file.
- Archive via `./.aitask-scripts/aitask_archive.sh 691_1`.

## Notes for sibling tasks (planning-time)

- The helper script and SKILL.md are extended (not rewritten) by t691_2.
- Web docs (t691_3) describe both Phase 1 and Phase 2 — must wait for t691_2 before finalizing.
- Both t691_1's work and t691_2's work share the same helper script — keep the file structure flexible (clear subcommand dispatch, easy to add new subcommands).

## Final Implementation Notes

- **Actual work done:** Wrote `.aitask-scripts/aitask_audit_wrappers.sh` (385 LOC, shellcheck clean at warning level) with Phase 1 subcommands (`discover`, `discover-policy`, `render-wrapper`, `apply-wrapper`, `apply-policy`). Wrote source-of-truth `.claude/skills/aitask-audit-wrappers/SKILL.md` (121 LOC). Drove the helper to write all 9 wrappers (4 self-bootstrap + 4 for `aitask-add-model` + 1 for `aitask-qa` in opencode-commands) and 7 activate_skill policy entries (4 runtime + 3 seed). Whitelisted the new helper in all 5 touchpoints. Edited CLAUDE.md "Codex CLI" subsections to reflect that codex uses the unified `.agents/skills/` layout and does NOT have a `.codex/prompts/` directory.

- **Deviations from plan:** None of substance. Two `aitask-add-model` wrappers (`.agents/skills` and `.opencode/skills`) initially had `## Arguments: See source skill documentation.` from the auto-extractor fallback because the source-of-truth `aitask-add-model/SKILL.md` uses no `## Usage` or `**Usage:**` heading; hand-edited those two wrappers with concrete CLI flag listings. Future cleanup could add `## Usage` sections to source SKILL.md files lacking them so the auto-extractor finds richer summaries — out of scope here.

- **Issues encountered:** Initial awk pattern for auto-extracting `## Usage` paragraph used `\b` (word boundary) which may not be portable across awk implementations; produced empty bodies until simplified. After the fix the extractor handles `## Usage`, `## Arguments`, `**Usage:**`, and `**Arguments:**` markers, with the "See source skill documentation." fallback when none are present.

- **Key decisions:**
  - Helper kept minimal — emits only structured `KEY:value` lines; UI orchestration (per-gap diff display, AskUserQuestion gates) lives entirely in SKILL.md as designed.
  - `apply-wrapper` refuses to overwrite existing files unless `--force` so a buggy run can't blow away hand-edited wrappers (e.g. the contribution-review or qa wrappers we did not regenerate).
  - Insertion of `[[rule]]` blocks uses `awk` to find the alphabetically-correct insert line, then `head`/`tail` to reassemble; this avoids GNU-vs-BSD `sed -i` portability issues.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t691_2:** the helper's subcommand dispatcher (`main()`) is a flat `case` — add `discover-helpers`, `audit-helper-whitelist`, `apply-helper-whitelist` cases directly. The `insert_activate_skill_rule()` function is the closest pattern to copy/adapt for inserting `commandPrefix` rules; the difference is a one-line regex tweak (`commandPrefix` instead of `argsPattern`) plus a different `toolName` literal. JSON edits in touchpoints 1/3/5 are simpler — `jq` with array-position insertion is appropriate. Stay consistent with the existing exit-0 / structured-output-only convention.
  - **t691_3 (web docs):** the SKILL.md "Output reference" table and "Self-bootstrap" section are good source material to quote/paraphrase. The `## Usage` block in the SKILL.md gives the canonical CLI invocation forms.
  - The auto-extractor improvement (handling `**Usage:**`/`**Arguments:**`) is now in place — future skills that follow either heading style will produce richer wrapper Arguments lines automatically.

- **Verification results:** shellcheck clean at warning level (only SC1091 info-level "source not followed" remains, matching all sibling helpers); `discover` + `discover-policy` produce empty output (idempotent); `tests/test_opencode_setup.sh` 31/31 pass; `tests/test_gemini_setup.sh` 57/57 pass; all 11 expected wrapper/helper files present on disk.
