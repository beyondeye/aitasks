---
priority: medium
effort: medium
depends: [t583_1]
issue_type: feature
status: Implementing
labels: [framework, skill, task_workflow, verification]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 08:29
updated_at: 2026-04-19 11:50
---

## Context

Third child of t583. Implements the follow-up helper script that creates a bug task when a manual-verification item is marked `Fail`. Depends on t583_1 (uses the parser to extract the failing item text) and indirectly t583_2 (uses the `verifies:` list to disambiguate origin).

## Key Files to Modify

- `.aitask-scripts/aitask_verification_followup.sh` — **new file**, the helper.
- `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json` — whitelist entries.

## Reference Files for Patterns

- `.aitask-scripts/aitask_issue_update.sh` — `detect_commits()` at ~line 246 (we reuse this via `source` or direct reimplementation of the `git log --oneline --grep "(t<id>)"` call).
- `.aitask-scripts/aitask_create.sh --batch` — the task creation backend.
- `.aitask-scripts/lib/task_utils.sh` — `resolve_task_id_to_file()`, `read_frontmatter_field()`.

## Implementation Plan

1. **CLI:**
   ```
   aitask_verification_followup.sh --from <task_id> --item <index> [--origin <feature_task_id>]
   ```

2. **Behavior:**
   - Resolve `--from` task file; parse via `aitask_verification_parse.sh parse <file>`; extract item `<index>`.
   - Read `verifies:` from the task's frontmatter.
   - If `--origin` provided, use it.
   - If `--origin` omitted and `verifies:` has exactly one entry, use that.
   - If `--origin` omitted and `verifies:` has 2+ entries, **emit structured output** `ORIGIN_AMBIGUOUS:<csv_of_ids>` and exit 2 — the calling procedure (t583_4) handles the `AskUserQuestion` prompt and re-invokes the script with `--origin`.
   - If `verifies:` empty and `--origin` omitted, use `--from` as origin.

3. **Resolve commits for origin:**
   - Call `detect_commits()` by sourcing `aitask_issue_update.sh` (guard against side effects) OR replicate its `git log --oneline --grep "(t${origin})"` incantation directly. Pick whichever preserves `aitask_issue_update.sh` stability.
   - Parse output: each line `<hash> <message>`.

4. **Resolve touched files:**
   - For each commit hash: `git show --name-only --format= <hash>` → list files.
   - Dedupe across commits.

5. **Compose task description** (write to temp file):
   - Heading: `## Failed verification item from t<origin>`
   - Verbatim failing-item text.
   - `### Commits that introduced the failing behavior:` with bullet list of `<hash> <message>`.
   - `### Files touched by those commits:` with bullet list.
   - `### Next steps:` one-line stub directing the implementer to reproduce and fix.

6. **Create the bug task:**
   ```
   aitask_create.sh --batch \
     --type bug --priority medium --effort medium \
     --labels verification,bug \
     --deps <origin> \
     --desc-file <tmp> --commit
   ```
   Note: there is no `--related` flag on `aitask_create.sh`; use `--deps <origin>` to express the relationship (the followup can be worked on once origin's behavior is stable; dependencies express the right semantic). Alternative: extend `aitask_create.sh` to accept a `--related` frontmatter field — out of scope here, use `--deps`.

7. **Annotate the failing item:**
   `./.aitask-scripts/aitask_verification_parse.sh set <from_file> <index> fail --note "follow-up t<new_id>"`

8. **Back-reference origin's archived plan** (optional, best-effort):
   - If `aiplans/archived/p<origin_parent>/p<origin>_*.md` exists, append a line under its `## Final Implementation Notes` section:
     `- **Manual-verification failure:** item "<text>" failed; follow-up task t<new_id>.`
   - If origin's plan is not archived, skip silently.

9. **Structured output:**
   - `ORIGIN_AMBIGUOUS:<csv>` (exit 2) — caller must supply `--origin`.
   - `FOLLOWUP_CREATED:<new_task_id>:<path>` on success.
   - `ERROR:<message>` (exit 1) on failure.

## Verification Steps

- Prepare a synthetic manual-verification task with `verifies: [X]` where X is a real feature task that has at least one commit like `feature: foo (tX)`.
- Run the helper; inspect the new bug task's description includes commit hash, files, failing text.
- Run with `verifies: [X, Y]` and no `--origin` → expect `ORIGIN_AMBIGUOUS:X,Y` exit 2.
- Run with `--origin X` → expect `FOLLOWUP_CREATED`.
- Confirm source task's item line now reads `- [fail] ... — FAILED 2026-04-19 HH:MM (follow-up: tN)`.

## Step 9 reminder

Commit: `feature: Add verification followup helper (t583_3)`.
