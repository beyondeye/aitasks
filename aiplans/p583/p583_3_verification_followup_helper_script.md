---
Task: t583_3_verification_followup_helper_script.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md, aitasks/t583/t583_2_*.md, aitasks/t583/t583_4_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_1_*.md, aiplans/archived/p583/p583_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 12:33
---

# Plan: t583_3 — Verification Follow-up Helper

## Context

Creates a bug task when a manual-verification item is marked `Fail`. Drives the "Fail → follow-up" flow described in t583 so that failing a manual check produces a pre-populated, traceable bug task (commits, touched files, verbatim failing text, `deps: [origin]`) instead of a free-form note. Depends on t583_1 (verification parser) and t583_2 (`verifies:` frontmatter plumbing); both are already landed and archived. The workflow procedure in t583_4 will call this helper when a manual-verification item transitions to `fail`.

## Verify-path divergences from the draft plan

Plan re-verified against the current codebase. Corrections applied below:

1. **`resolve_task_file()`, not `resolve_task_id_to_file()`** — the helper in `lib/task_utils.sh:275` is `resolve_task_file()`. It handles parent (`583`) and child (`583_3`) IDs and also archive fallback; no replacement needed.
2. **`read_yaml_field()`, not `read_frontmatter_field()`** — the reader in `lib/task_utils.sh:126` is `read_yaml_field <file> <field>`.
3. **Do NOT `source aitask_issue_update.sh`** — the file has an unguarded `main "$@"` at line 535 and would run on source. Replicate `detect_commits()`'s single-line incantation inline instead: `git log --oneline --all --grep="(t${origin})"`.
4. **`aitask_create.sh --silent`** — on success the script echoes just `<filepath>`. Invoke with `--silent` and parse the filename for the new task ID (`aitasks/t<id>...md` → `<id>`). Without `--silent` it prints `Created: <filepath>` instead.
5. **`parse_yaml_list()` + `format_yaml_list()`** are in `lib/task_utils.sh` at lines 106 and 116; use `parse_yaml_list` to turn the `verifies:` bracketed list into a CSV.

## Files to create / modify

**New:**
- `.aitask-scripts/aitask_verification_followup.sh` — the helper script (bash, sources `lib/task_utils.sh`).

**Modify — whitelist touchpoints (5 files, mirror `aitask_verification_parse.sh` placement):**
- `.claude/settings.local.json` — add `"Bash(./.aitask-scripts/aitask_verification_followup.sh:*)"` insertion-ordered near line 55 (next to the `aitask_verification_parse.sh` entry).
- `.gemini/policies/aitasks-whitelist.toml` — append a `[[rule]]` block near lines 297–299.
- `seed/claude_settings.local.json` — insert **alphabetically** near line 55 (`followup` < `parse` → goes before the parse entry).
- `seed/geminicli_policies/aitasks-whitelist.toml` — append at end of `aitask_*.sh` run, near lines 302–305.
- `seed/opencode_config.seed.json` — insert **alphabetically** near line 44.

**Codex:** skip (no `.codex/` shell-script whitelist).

## CLI

```
aitask_verification_followup.sh --from <task_id> --item <index> [--origin <feature_task_id>]
```

- `--from` — required — ID of the manual-verification task containing the failing item (e.g., `571_7`).
- `--item` — required — 1-indexed item number within the task's `## Verification Checklist` section.
- `--origin` — optional — feature task ID to attribute the failure to; used when `verifies:` has 2+ entries.

## Behavior (numbered steps)

1. **Parse args.** Require `--from` and `--item` (integer ≥ 1). Default `--origin` to empty. Emit `ERROR:<msg>` + exit 1 on bad args.

2. **Resolve `--from` task file** via `resolve_task_file "$from_id"` (from `lib/task_utils.sh`).

3. **Extract the failing item text.**
   ```bash
   item_line=$(./.aitask-scripts/aitask_verification_parse.sh parse "$from_file" \
       | awk -F: -v idx="$item_index" '$1 == "ITEM" && $2 == idx { print; exit }')
   [[ -n "$item_line" ]] || { echo "ERROR:item $item_index not found in $from_file"; exit 1; }
   item_text=$(echo "$item_line" | cut -d: -f5-)
   ```
   Note `parse` output is `ITEM:<idx>:<state>:<line_no>:<text>`; item_text is everything after the 4th colon.

4. **Resolve origin task ID.**
   ```bash
   verifies_raw=$(read_yaml_field "$from_file" "verifies")
   verifies_csv=$(parse_yaml_list "$verifies_raw")   # "t571_4,t571_5" or ""
   if [[ -n "$origin" ]]; then
       :  # user-supplied
   elif [[ -z "$verifies_csv" ]]; then
       origin="$from_id"
   elif [[ "$verifies_csv" != *","* ]]; then
       origin="$verifies_csv"
   else
       echo "ORIGIN_AMBIGUOUS:$verifies_csv"
       exit 2
   fi
   # Strip any leading 't' so origin is a bare ID (aitask_create accepts both but downstream lookups are cleaner bare).
   origin="${origin#t}"
   ```

5. **Resolve commits for origin** (replicate `detect_commits()` inline — do NOT source `aitask_issue_update.sh`):
   ```bash
   commits=$(git log --oneline --all --grep="(t${origin})" 2>/dev/null || true)
   ```
   Each line is `<hash> <message>`.

6. **Resolve touched files** from those commits:
   ```bash
   touched_files=$(
       printf '%s\n' "$commits" \
           | awk 'NF { print $1 }' \
           | while read -r h; do git show --name-only --format= "$h" 2>/dev/null; done \
           | sort -u
   )
   ```

7. **Compose the bug task description** to a temp file (use `mktemp "${TMPDIR:-/tmp}/followup_XXXXXX.md"` — BSD-portable; no `--suffix`).

   Body template:
   ```markdown
   ## Failed verification item from t<origin>

   > <verbatim item_text>

   ### Commits that introduced the failing behavior

   <bullet list of "- <hash> <message>", or "_(none detected — no commits matched (t<origin>))_" if empty>

   ### Files touched by those commits

   <bullet list of "- <path>", or "_(none)_" if empty>

   ### Next steps

   Reproduce the failure locally, identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t<from_id> item #<item_index>.
   ```

8. **Create the bug task** — use `--silent` to capture the path cleanly:
   ```bash
   new_path=$(./.aitask-scripts/aitask_create.sh --batch --silent \
       --type bug --priority medium --effort medium \
       --labels verification,bug \
       --deps "$origin" \
       --desc-file "$tmp" --commit)
   ```
   Extract the new ID from the filename with the same regex used across the codebase:
   ```bash
   new_id=$(basename "$new_path" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*\.md$/\1/')
   [[ -n "$new_id" && "$new_id" != "$(basename "$new_path")" ]] || { echo "ERROR:could not parse task id from $new_path"; exit 1; }
   ```

9. **Annotate the failing item in the source task:**
   ```bash
   ./.aitask-scripts/aitask_verification_parse.sh set "$from_file" "$item_index" fail \
       --note "follow-up t${new_id}"
   ```

10. **Back-reference origin's archived plan** (best-effort, silent on failure):
    ```bash
    # Parent-part of origin id (e.g. t571_4 → 571)
    if [[ "$origin" == *_* ]]; then origin_parent="${origin%%_*}"; else origin_parent="$origin"; fi
    # Glob for origin's archived plan
    origin_plan=$(ls "aiplans/archived/p${origin_parent}/p${origin}_"*.md 2>/dev/null | head -n1 || true)
    # Parent tasks archive to aiplans/archived/p<N>_*.md (no subdirectory)
    [[ -z "$origin_plan" ]] && origin_plan=$(ls "aiplans/archived/p${origin}_"*.md 2>/dev/null | head -n1 || true)
    if [[ -n "$origin_plan" && -f "$origin_plan" ]]; then
        # Append a bullet under "## Final Implementation Notes" if the section exists;
        # otherwise, append the section + bullet at EOF.
        note="- **Manual-verification failure:** item \"${item_text}\" failed; follow-up task t${new_id}."
        if grep -q '^## Final Implementation Notes' "$origin_plan"; then
            # Append at the end of the file — section is conventionally last.
            printf '%s\n' "$note" >> "$origin_plan"
        else
            printf '\n## Final Implementation Notes\n\n%s\n' "$note" >> "$origin_plan"
        fi
        ./ait git add "$origin_plan" 2>/dev/null || true
        ./ait git commit -m "ait: Back-reference manual-verification failure on t${origin}" 2>/dev/null || true
    fi
    ```
    Skip silently if the plan file cannot be found or `./ait git` fails — this is best-effort only.

11. **Structured output on success:**
    ```
    FOLLOWUP_CREATED:<new_id>:<new_path>
    ```
    Clean up the temp file with `trap 'rm -f "$tmp"' EXIT` set early.

## Exit codes

- `0` — success; stdout ends with `FOLLOWUP_CREATED:...`.
- `1` — usage error, file-not-found, or `aitask_create.sh` failure; `ERROR:<msg>` to stdout/stderr.
- `2` — ambiguous origin; `ORIGIN_AMBIGUOUS:<csv>` to stdout; no mutation performed.

These codes are what the t583_4 workflow procedure will switch on — it catches exit 2, prompts the user via `AskUserQuestion`, and re-invokes this helper with `--origin`.

## Script skeleton

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

FROM_ID=""
ITEM_INDEX=""
ORIGIN=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)   FROM_ID="$2"; shift 2 ;;
            --item)   ITEM_INDEX="$2"; shift 2 ;;
            --origin) ORIGIN="$2"; shift 2 ;;
            -h|--help) show_help; exit 0 ;;
            *) die "Unknown arg: $1" ;;
        esac
    done
    [[ -n "$FROM_ID" ]] || die "--from is required"
    [[ "$ITEM_INDEX" =~ ^[0-9]+$ ]] || die "--item must be a positive integer"
}

main() {
    parse_args "$@"
    local tmp; tmp=$(mktemp "${TMPDIR:-/tmp}/followup_XXXXXX.md")
    trap 'rm -f "$tmp"' EXIT

    local from_file; from_file=$(resolve_task_file "$FROM_ID")
    # Steps 3–11 as described above.
}

main "$@"
```

Use `die`, `warn`, `info` from `lib/terminal_compat.sh` for error paths.

## Verification (manual smoke — executed by implementer after coding)

Use a throwaway real feature-task commit as origin (e.g. `b17f8c54 feature: Add verifies frontmatter field (t583_2)`):

1. **Minimal happy path (single-origin via `verifies:`):**
   - Create a synthetic manual-verification task:
     ```bash
     tmpdesc=$(mktemp "${TMPDIR:-/tmp}/mvtask_XXXXXX.md")
     cat > "$tmpdesc" <<'EOF'
     ## Verification Checklist

     - [ ] sanity check 1
     - [ ] sanity check 2
     EOF
     new_mv=$(./.aitask-scripts/aitask_create.sh --batch --silent \
         --type chore --name smoke_mv --priority low --effort low \
         --verifies 583_2 --desc-file "$tmpdesc" --commit)
     mv_id=$(basename "$new_mv" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*\.md$/\1/')
     ```
   - Run helper:
     ```bash
     ./.aitask-scripts/aitask_verification_followup.sh --from "$mv_id" --item 1
     ```
   - Expect stdout ends with `FOLLOWUP_CREATED:<new_id>:<path>`; the new task description mentions commit `b17f8c54`, includes a bullet for the touched files of that commit, and verbatim "sanity check 1".
   - Inspect `$new_mv`: item 1 line now reads `- [fail] sanity check 1 — FAIL YYYY-MM-DD HH:MM follow-up t<new_id>`.

2. **Ambiguous origin:**
   - Update the MV task: `./.aitask-scripts/aitask_update.sh --batch "$mv_id" --verifies 583_1,583_2`.
   - Re-run the helper (same args). Expect exit code 2 and stdout line `ORIGIN_AMBIGUOUS:583_1,583_2`; the task is NOT mutated.
   - Re-run with `--origin 583_2`. Expect `FOLLOWUP_CREATED:...`.

3. **Empty `verifies:`** (fallback to `--from` as origin):
   - Update: `./.aitask-scripts/aitask_update.sh --batch "$mv_id" --remove-verifies 583_1 --remove-verifies 583_2`.
   - Re-run on a fresh `--item 2`. Expect `FOLLOWUP_CREATED:...` with origin resolved to `$mv_id`. (Commit list will likely be empty — spec: still succeed, with the `_(none detected…)_` placeholder in the description.)

4. **Back-reference (best-effort):**
   - For the `--origin 583_2` run above, inspect `aiplans/archived/p583/p583_2_verifies_frontmatter_field_three_layer.md` — expect an appended `- **Manual-verification failure:** …` bullet under `## Final Implementation Notes`. If the commit happens, it's an `ait:` commit.

5. **Cleanup:** archive / delete the smoke tasks (`$new_mv`, the generated follow-up, and revert the archived-plan bullet if it was appended).

## Out of scope (explicit)

- **Unit tests** — bash integration tests for this helper land in t583_6 as `tests/test_verification_followup.sh` (there is no pre-existing pattern for `aitask_create.sh --batch` integration tests; t583_6 will establish it). This task does NOT ship tests.
- **Workflow procedure wiring** — the t583_4 procedure that invokes this helper and handles `ORIGIN_AMBIGUOUS` via `AskUserQuestion` is a separate task.
- **`--related` field on tasks** — use `--deps <origin>` instead (dependency expresses the right semantic: follow-up can be worked on once origin's behavior is stable).
- **Extending `aitask_issue_update.sh`** — do NOT refactor `detect_commits()` out of it; replicate the one-liner to preserve that script's stability.

## Step 9 reminder

Standard post-implementation flow per `.claude/skills/task-workflow/SKILL.md` Step 9. Commit format for code: `feature: Add verification followup helper (t583_3)`. Plan file commits use `ait:` prefix.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/aitask_verification_followup.sh` implementing the full spec: arg parsing, `resolve_task_file()` lookup of the `--from` task, failing-item extraction via `aitask_verification_parse.sh parse`, origin disambiguation (via `--origin`, or `verifies:` with 0/1/2+ entries → fallback / auto / `ORIGIN_AMBIGUOUS`), commit detection via the replicated `git log --oneline --all --grep="(t${origin})"` one-liner, touched-file dedup via `git show --name-only`, description composition to a temp file, bug-task creation with `aitask_create.sh --batch --silent --commit`, task-ID parsing from the returned filename, annotation of the failing item via `aitask_verification_parse.sh set`, and best-effort back-reference commit on the origin's archived plan. Added the helper to all 5 whitelist touchpoints (`.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`).
- **Deviations from plan:**
  - `aitask_create.sh --batch` requires `--name` — the plan's command template omitted it. Helper now derives a name `fix_failed_verification_t<from>_item<index>` and passes `--name` alongside the other batch flags.
  - Added a `### Source` section to the generated bug description (MV task file path + item number, origin task ID, and origin archived plan path when found) after a user review pointed out that the prose-only trail was too thin for a follow-up reviewer. The section makes the failure's provenance a single click/glance instead of a text scan.
  - `trap 'rm -f "$tmp"' EXIT` with `set -u` raised `tmp: unbound variable` at trap-fire time because the `local tmp` in `main()` was out of scope. Moved `tmp` to script scope and wrote the trap as `trap 'rm -f "${tmp:-}"' EXIT` so `set -u` doesn't trip on the cleanup.
  - Consumed `aitask_create.sh --silent --commit` output by taking the last non-empty line (the path), since `--commit` prints the git commit summary before the path even in silent mode.
- **Issues encountered:**
  - `aitask_update.sh --remove-verifies <id>` is a no-op in practice — removing `t583_1`/`t583_2` from the `verifies:` list via `--remove-verifies` left the list unchanged, even when the stored form had a `t` prefix. `--verifies ""` (full replace) works as a workaround and was used to reach the "empty verifies" test case. Not fixed here — noted for a dedicated follow-up against `process_verifies_operations()` in `aitask_update.sh`.
- **Key decisions:**
  - Did **not** source `aitask_issue_update.sh` — its `main "$@"` runs on source. Replicated the one-liner `git log --oneline --all --grep="(t${origin})"` inline per the plan's guidance.
  - `read_yaml_field()` (not `read_frontmatter_field()`) and `resolve_task_file()` (not `resolve_task_id_to_file()`) — naming drift from the draft plan, corrected during verify.
  - Used `--deps <origin>` on the follow-up task rather than a new `--related` field. Matches the semantic: the bug can be worked on once the origin's behavior is stable.
  - Back-reference commit on the origin archived plan is best-effort and silenced on failure — `./ait git` may not be configured in every environment (e.g., fresh clones). The bullet is still appended to the file even if the commit fails, so subsequent runs of `./ait git status` will surface it.
- **Notes for sibling tasks:**
  - **t583_4 (workflow procedure)** should shell out to this helper with `--from`/`--item`, catch exit code 2 (`ORIGIN_AMBIGUOUS:<csv>`), drive the user through the ambiguity via `AskUserQuestion`, and re-invoke with `--origin`. Exit 0 on `FOLLOWUP_CREATED:<id>:<path>` ends the fail flow.
  - **t583_6 (unit tests)** — bash integration tests for this helper should be added as `tests/test_verification_followup.sh`. There is no pre-existing pattern for `aitask_create.sh --batch` integration tests in the repo; t583_6 establishes it. Synthetic fixtures should seed a sandbox git repo with at least one `feature: ... (tN)` commit so `detect_commits()` has something to match.
  - **Follow-up bug candidate (separate task, not yet created):** `aitask_update.sh --remove-verifies <id>` does not remove entries from `verifies:` as documented. `process_verifies_operations()` in `.aitask-scripts/aitask_update.sh` needs a root-cause fix — likely a mismatch between the prefixed/bare-ID forms being compared during removal.
  - The helper stores the bug-task name as `fix_failed_verification_t<from>_item<N>` — short enough to grep, with full traceability in the name.
- **Smoke validation results:**
  - Scenario 1 (happy path, single-origin via `verifies: [583_2]`): helper created `t589` with `deps: [583_2]`, bug body contained commit `b17f8c54`, 5 touched files, verbatim failing text. Source MV item flipped to `[fail]` with `follow-up t589` note. Back-ref bullet appended to `p583_2`'s archived plan and committed.
  - Scenario 2 (ambiguous `verifies: [t583_1, t583_2]`): exit code 2, stdout `ORIGIN_AMBIGUOUS:t583_1,t583_2`, no mutation. Re-run with `--origin 583_1` → `FOLLOWUP_CREATED:590:...`.
  - Scenario 3 (empty `verifies:`): origin fell back to `--from`, `FOLLOWUP_CREATED:591:...` with empty-commit-list placeholder in the description.
  - Retest after adding the `### Source` section: `t592 → t593` round-trip confirms MV-task path, origin ID, and archived-plan path all render correctly.
