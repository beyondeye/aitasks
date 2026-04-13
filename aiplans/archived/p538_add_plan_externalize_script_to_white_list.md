---
Task: t538_add_plan_externalize_script_to_white_list.md
Base branch: main
---

# Plan: Add fold + plan-externalize scripts to code-agent whitelists (t538)

## Context

Four new `.aitask-scripts` entries have landed on `main` in recent commits but were never added to the seed whitelist files shipped by `ait setup`, nor to the local Claude Code settings that the aitasks meta-repo itself uses. As a result, on fresh setups these scripts will prompt the user for permission on every invocation, breaking the intended "run without manual approval" experience for the skills that call them.

Newly added scripts that must be whitelisted:

- `aitask_plan_externalize.sh` — added in commit `40959eb3` (t440). Called from the Plan Externalization Procedure during Step 6 and Step 8.
- `aitask_fold_content.sh` — added in commit `3acd0e3d` (t522_1). Called from the Ad-Hoc Fold Procedure in `planning.md` and from `aitask-fold`.
- `aitask_fold_mark.sh` — same commit, same callers.
- `aitask_fold_validate.sh` — same commit, same callers.

These scripts currently appear nowhere in any `seed/` whitelist file (verified via grep) and are absent from the user's `.claude/settings.local.json`.

## Source of truth flow (for reference)

`seed/claude_settings.local.json` → packaged into release tarball → `install.sh` copies it to `aitasks/metadata/claude_settings.seed.json` → `aitask_setup.sh` merges that into the target project's `.claude/settings.local.json`. Same pattern for the Gemini and OpenCode seeds. So fixing `seed/` fixes all future installs. The aitasks repo's own `.claude/settings.local.json` must be patched directly — it won't re-run setup against itself.

## Files to modify

### 1. `seed/claude_settings.local.json`
Add four entries to `permissions.allow`, alphabetically placed between existing neighbors:

```json
"Bash(./.aitask-scripts/aitask_fold_content.sh:*)",
"Bash(./.aitask-scripts/aitask_fold_mark.sh:*)",
"Bash(./.aitask-scripts/aitask_fold_validate.sh:*)",
"Bash(./.aitask-scripts/aitask_plan_externalize.sh:*)",
```

Insert `fold_*` entries right after `aitask_find_files.sh` (line 41) and `plan_externalize` right after `aitask_pick_own.sh` (line 49).

### 2. `seed/geminicli_policies/aitasks-whitelist.toml`
Append four new `[[rule]]` blocks (TOML allows any order, but place near related scripts for readability). Pattern to match existing entries:

```toml
[[rule]]
toolName = "run_shell_command"
commandPrefix = "./.aitask-scripts/aitask_fold_content.sh"
decision = "allow"
priority = 100
```

Plus the three other scripts with the same shape. Insert after the `aitask_find_files.sh` block (around line 467).

### 3. `seed/opencode_config.seed.json`
Add four entries to `permission.bash`, matching existing format (`"allow"` value, trailing space-star glob):

```json
"./.aitask-scripts/aitask_fold_content.sh *": "allow",
"./.aitask-scripts/aitask_fold_mark.sh *": "allow",
"./.aitask-scripts/aitask_fold_validate.sh *": "allow",
"./.aitask-scripts/aitask_plan_externalize.sh *": "allow",
```

Place the `fold_*` entries right after `aitask_find_files.sh` (line 30) and `plan_externalize` right after `aitask_pick_own.sh` (line 38) to keep the file roughly alphabetical.

### 4. `.claude/settings.local.json` (this repo's own local settings)
Add the same four Claude Code entries directly. This is the user's active working-copy settings; `ait setup` is not re-run against the aitasks repo itself, so the file needs manual patching. Place the entries alphabetically — roughly next to `aitask_find_files.sh` (line 85) and `aitask_pick_own.sh` (line 51).

## Not modified

- **`seed/codex_config.seed.toml`** — Codex CLI's `prefix_rules` only support `"prompt"` or `"forbidden"` decisions (see inline comment at line 13). There is no allow-list concept, so no action needed.
- **`aitasks/metadata/claude_settings.seed.json`** — This is the per-project installed copy, gitignored, not tracked. Regenerated on next `ait install`.
- **`CLAUDE.md` / docs** — No structural change; no documentation update needed.

## Verification

1. `git diff` the four edited files and confirm only the four new entries per agent are added (16 new lines total across seeds, plus 4 lines in the repo's `.claude/settings.local.json`).
2. `jq . seed/claude_settings.local.json > /dev/null` — validates JSON.
3. `jq . seed/opencode_config.seed.json > /dev/null` — validates JSON.
4. `jq . .claude/settings.local.json > /dev/null` — validates JSON.
5. `grep -c 'aitask_fold_\|aitask_plan_externalize' seed/geminicli_policies/aitasks-whitelist.toml` — expect `8` (4 rules × 2 lines each containing the name in `commandPrefix`/the rule comment, or just the 4 `commandPrefix` lines).
6. After the edits, invoking `aitask_plan_externalize.sh` / `aitask_fold_*.sh` in a fresh Claude Code session that has merged the seed should no longer trigger permission prompts. (Cannot fully test in this session because the allow list is cached at launch, but we verify the entries exist.)

## Step 9 (Post-Implementation)

Follow the standard task-workflow Step 9: commit as `bug: Add fold and plan_externalize scripts to code-agent whitelists (t538)` per the `issue_type: bug` in the frontmatter, then run `aitask_archive.sh 538` and push.

## Final Implementation Notes

- **Actual work done:** Added four new whitelist entries (`aitask_fold_content.sh`, `aitask_fold_mark.sh`, `aitask_fold_validate.sh`, `aitask_plan_externalize.sh`) to three seed whitelists (`seed/claude_settings.local.json`, `seed/opencode_config.seed.json`, `seed/geminicli_policies/aitasks-whitelist.toml`) and to the aitasks repo's own `.claude/settings.local.json`. JSON validated with `jq` on all three JSON files.
- **Deviations from plan:** None for the task-scoped changes. The aitasks repo's local `.claude/settings.local.json` also carried 2 pre-existing uncommitted additions (`Bash(tmux list-sessions:*)`, `Bash(./ait create:*)`) that were already in the working tree before the task started. Per user approval, these were bundled into the same t538 commit rather than leaving them dangling.
- **Issues encountered:** None. The `seed/codex_config.seed.toml` file was intentionally not modified because Codex CLI `prefix_rules` only support `prompt` / `forbidden` decisions and have no allow-list concept (documented inline in that file).
- **Key decisions:** Alphabetical placement of the new entries inside each whitelist file to keep them grouped with their nearest neighbors (e.g., `aitask_fold_*` inserted right after `aitask_find_files.sh`, `aitask_plan_externalize.sh` right after `aitask_pick_own.sh`). Same placement logic applied uniformly across all three Claude/OpenCode/Gemini seed files.
