---
Task: t581_migrate_refreshcodemodels_to_use_addjson_helper.md
Base branch: main
plan_verified: []
---

# Plan: Migrate refresh-code-models NEW-model append path to `aitask_add_model.sh add-json`

## Context

Task **t581** — `aitasks/t581_migrate_refreshcodemodels_to_use_addjson_helper.md`.

Task **t579_2** (already landed) introduced a reusable helper
`.aitask-scripts/aitask_add_model.sh add-json` that atomically appends a
new model entry to `aitasks/metadata/models_<agent>.json` and syncs the
same entry to `seed/models_<agent>.json`. The helper validates the agent
name, model name, and cli_id; errors if a model with that `name` already
exists in either file; runs `jq .` over the proposed output; and supports
`--dry-run` (prints a unified diff without writing).

The sibling skill `aitask-refresh-code-models` (the web-research-driven
refresher) currently performs the equivalent JSON mutation inline in its
**Step 6**, writing the new entry directly with its own append logic and
an independent seed-copy block. Two code paths now do the same thing,
which is drift-prone. Migrate the NEW-model write to the helper so the
two skills share one write surface.

The UPDATED (change `notes`) and DEPRECATED (optional removal) paths are
intentionally **not** covered by the helper and stay inline.

## Scope

Edit **one file**: `.claude/skills/aitask-refresh-code-models/SKILL.md`.

Nothing else: no helper changes, no JSON schema changes, no sibling skill
mirror edits (those are flagged as follow-up tasks in Step 9 notes).

### Edits within SKILL.md

1. **Step 4 — "NEW" bullet (lines ~66–71):** drop the hard-coded
   `"verified": { "pick": 0, "explain": 0, "batch-review": 0 }` and
   `"verifiedstats": {}` initialization language. Replace with a
   single line stating the helper initializes `verified` and
   `verifiedstats` as empty objects (`{}`), which matches what the
   helper writes at `aitask_add_model.sh:104-111`. The existing
   `name` / `cli_id` / `notes` bullets stay — those are inputs to the
   helper.

   Note: this is a pure documentation alignment — the live
   `models_*.json` files already contain a mix of shapes (empty `{}`
   for untouched new entries, populated objects once the satisfaction
   feedback loop has recorded scores). Rolling-stats reads tolerate
   both shapes, so no runtime change.

2. **Step 6 — restructure from "read/mutate/write" into three
   explicit branches per agent:**

   - **NEW models** — invoke the helper once per new model:
     ```bash
     ./.aitask-scripts/aitask_add_model.sh add-json \
       --agent <a> --name <n> --cli-id <id> --notes "<s>" [--dry-run]
     ```
     Document that the helper:
     - appends the entry to `aitasks/metadata/models_<agent>.json`
     - syncs the same entry to `seed/models_<agent>.json` when `seed/` exists
     - errors out if a model with that `name` already exists in either file
     - validates JSON before writing

   - **UPDATED models (notes change)** — keep inline. Read the
     metadata file, modify the matching entry's `notes`, write back
     with 2-space indent, then — if `seed/models_<agent>.json` exists
     and contains the same model — apply the same `notes` change to
     the seed file.

   - **DEPRECATED removal (only when explicitly approved)** — keep
     inline. Same read/modify/write shape, and same conditional seed
     mirror for the removal.

   Remove the current unconditional "Seed sync (conditional)" block
   at the end of Step 6 — seed sync for NEW is automatic (helper),
   and seed sync for UPDATED/DEPRECATED is folded into each inline
   branch above.

3. **Step 6 — edge-case callout (new short paragraph):** document
   the `name` vs `cli_id` duplicate-check mismatch:
   > If a user has locally renamed an existing entry's `cli_id` while
   > keeping the `name` (so web research re-discovers the original
   > `cli_id` and categorizes it as NEW), the helper will refuse to
   > append because the `name` already exists. The refresher
   > categorizes by `cli_id`; the helper deduplicates by `name`.
   > When this happens, the helper's error message is the signal —
   > resolve by renaming the local entry or skipping the NEW write.

4. **Step 8 (commit block) — no content changes**, but remove the
   narrative claim that seed sync happens in the skill: the code
   commits stay the same shape because the helper already staged
   compatible changes to both metadata and seed files. Keep the two
   commands (metadata via `./ait git`, seed via plain `git`).

5. **Step 9 "Sibling Skill Mirrors" note:** the task file already
   asks to flag follow-up tasks for the Gemini CLI, Codex CLI, and
   OpenCode mirrors. I confirmed:
   - `.gemini/skills/aitask-refresh-code-models/` — does not exist (no follow-up needed)
   - `.agents/skills/aitask-refresh-code-models/SKILL.md` — 24 lines (thin wrapper; follow-up to propose)
   - `.opencode/skills/aitask-refresh-code-models/SKILL.md` — 17 lines (thin wrapper; follow-up to propose)

   The sibling files are minimal wrappers pointing at the main skill,
   so they likely do not need any mutation — but we will surface this
   to the user in Step 9 (post-implementation) and let them decide
   whether to open follow-up tasks.

## Key Files & References

- **Edit:** `.claude/skills/aitask-refresh-code-models/SKILL.md` (Steps 4, 6, 8; ~30 LoC delta)
- **Reuse (read-only):** `.aitask-scripts/aitask_add_model.sh` — `cmd_add_json` at lines 71-147 is the call target; its `--dry-run` uses `print_diff` (lines 59-67); duplicate-check at line 95 uses `any(.models[]?; .name == $n)`.
- **Unchanged:** `seed/models_*.json`, `aitasks/metadata/models_*.json` (no schema edits), `tests/test_add_model.sh` (helper-only tests, untouched).

## Verification

1. `shellcheck .aitask-scripts/aitask_add_model.sh` → exit 0 (no helper changes expected — sanity check).
2. `bash tests/test_add_model.sh` → all PASS (helper-only regression).
3. **Dry-run trace through the updated skill** — walk the updated Step
   6 mentally against a hypothetical one-new-model scenario (e.g.
   `claudecode / opus5_0 / claude-opus-5-0`). Confirm the skill now
   calls `add-json --dry-run` and relies on the helper's diff output
   rather than emitting its own write preview. Confirm the inline
   seed-copy block no longer appears. Confirm the UPDATED and
   DEPRECATED branches still read/modify/write the metadata file and
   conditionally mirror to seed.
4. **Consistency check with Step 4:** confirm the revised Step 4
   `verified` / `verifiedstats` language matches what the helper
   actually writes (`{}` for both).
5. **Follow-up task suggestion (Step 9):** after commit, surface the
   Codex and OpenCode sibling skills to the user for potential
   follow-up tasks per CLAUDE.md "WORKING ON SKILLS" guidance.

## Step 9 Reminder

After user approval of changes, follow the task-workflow SKILL.md
**Step 9 (Post-Implementation)**: no separate branch was created
(profile `create_worktree: false`), so skip merge steps; run the
archive script `./.aitask-scripts/aitask_archive.sh 581`; handle any
structured output lines; then `./ait git push`.
