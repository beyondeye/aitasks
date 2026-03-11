---
Task: t369_aitask_explain_for_aitask_pick.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Integrate aitask-explain Context into aitask-pick (t369)

## Context

When an AI agent picks a task, it lacks historical context about WHY existing code was designed the way it is. The aitask-explain system already maps file lines -> commits -> tasks -> plans via git blame, but this data is only accessible through the codebrowser TUI or the manual `/aitask-explain` skill. This task bridges that gap so implementing agents automatically get relevant architectural context during planning — purely as **informational background** to help the agent make better-informed design decisions for the current task's implementation plan, not as instructions to follow.

## Design Options Considered

### Option A: "Eager Pre-generation" — Parse task description for file paths, run explain pipeline before planning
- **Pro**: Fully automatic, no agent judgment needed
- **Con**: File identification from task text is fragile; task descriptions often don't list specific files

### Option B: "Planning-Phase Hook" — Agent identifies files during planning, then queries explain data (RECOMMENDED)
- **Pro**: Most accurate file identification (agent has already explored); leverages codebrowser cache; minimal context creep
- **Con**: Agent must remember to call the script (mitigated by skill instructions)

### Option C: "Label/Directory Mapping" — Pre-configured label-to-directory mapping
- **Pro**: Fully automatic, fast for cached directories
- **Con**: Requires maintaining mapping config; coarse-grained; misses unlabeled tasks

### Option D: "Hybrid" — Automatic directory-level + agent-triggered file-level
- **Pro**: Best of both worlds
- **Con**: Over-engineered for the value; two scripts, two phases

## Recommended: Option B — Planning-Phase Hook

The agent already explores the codebase during planning (Step 6.1) and naturally identifies which files need modification. We add a hook where it can say "I plan to modify these files — give me historical context." This is:
- **Most accurate**: Agent identifies files, not heuristics
- **Most portable**: Single shell script callable by all agents
- **Cache-friendly**: Reuses existing codebrowser explain data
- **Controlled context**: Extracts full plan content for top-N plans (greedy selection by affected lines), configurable via profile

## Architecture

```
Planning (Step 6.1) → Agent explores codebase → Identifies files to modify →

Calls aitask_explain_context.sh --max-plans N <files>
  ├── Groups files by parent directory
  ├── For each directory:
  │   ├── Computes dir_key (port of _dir_to_key from explain_manager.py)
  │   ├── Checks codebrowser cache (.aitask-explain/codebrowser/<key>__*)
  │   ├── Staleness check (git log timestamp vs run dir timestamp)
  │   └── If missing/stale: calls existing aitask_explain_extract_raw_data.sh
  │       └── (which internally calls aitask_explain_process_raw_data.py)
  └── Calls NEW aitask_explain_format_context.py with reference.yaml paths
      ├── Reads reference.yaml (YAML parsing, reuses existing format)
      ├── Sums line contributions per task_id across target files
      ├── Greedy selection of top N plans by line count
      ├── Reads full plan content from <run_dir>/plans/p<id>.md
      └── Outputs formatted markdown to stdout

Agent reads output → Incorporates into implementation plan
```

**Bash handles**: file system ops, git commands, cache management, pipeline orchestration
**Python handles**: YAML parsing, data aggregation, plan content extraction, markdown formatting
**Fully reused**: extract pipeline (aitask_explain_extract_raw_data.sh + process_raw_data.py), reference.yaml format, plans/ directory

## Implementation — Child Tasks

### t369_1: Create `aitask_explain_format_context.py`

Python helper that reads reference.yaml files, ranks tasks by line contribution, extracts "Final Implementation Notes" from plan files, outputs formatted markdown.

**New file**: `.aitask-scripts/aitask_explain_format_context.py`
**Reference**: `.aitask-scripts/aitask_explain_process_raw_data.py` (YAML parsing), `.aitask-scripts/codebrowser/explain_manager.py` (parse_reference_yaml pattern)

Key behavior:
- Accept: reference.yaml path(s), target file list, `--max-plans N`, run directory path(s)
- **Per-file greedy selection, then deduplicate:**
  1. For each target file: compute line contributions per task_id from its line_ranges
  2. For each target file: greedily select top N plans by line count (the N plans that cover the most lines of that file)
  3. **Union + deduplicate**: combine all selected plans across all files into a single set (each plan appears once)
  4. For each deduplicated plan: record which target files it provides context for
  5. **Sort by file coverage**: order plans by number of affected target files (decreasing); break ties by total line count
- For each plan in output:
  - Header line: "This plan provides historical context for: file1, file2, file3"
  - Read `<run_dir>/plans/p<id>.md` and output **full plan content once** (strip YAML frontmatter)
- Flag plans that don't exist; compute staleness indicator (commit dates vs current)
- Output clean markdown to stdout; no external dependencies beyond Python 3 stdlib + PyYAML
- **Note**: Full plan content is passed because the entire plan captures architectural decisions, patterns, and rationale

### t369_2: Create `aitask_explain_context.sh`

Shell script orchestrating the context gathering: groups files by directory, checks/generates codebrowser cache, calls the Python formatter.

**New file**: `.aitask-scripts/aitask_explain_context.sh`
**Reference**: `.aitask-scripts/aitask_explain_extract_raw_data.sh` (pipeline invocation), `explain_manager.py` (`_dir_to_key()`, `_find_run_dir()` logic)

Key behavior:
- Usage: `./.aitask-scripts/aitask_explain_context.sh --max-plans N <file1> [file2...]`
- `--max-plans N` (required): Maximum number of plans to extract via greedy selection. If 0, exits immediately (no-op).
- Group files by parent directory
- For each directory: compute dir_key, check `.aitask-explain/codebrowser/<dir_key>__*`
- **Staleness check** (ported from `explain_manager.py:_check_stale()`): compare run dir timestamp vs `git log -1 --format=%ct -- <dir>`. If last commit is newer → stale.
- If cached **and not stale**: use existing reference.yaml
- If cached **but stale**: auto-regenerate (delete old run dir, re-run extract pipeline)
- If missing: run extract pipeline with `AITASK_EXPLAIN_DIR=.aitask-explain/codebrowser`
- **Note**: Unlike the codebrowser TUI which only flags staleness for manual refresh, this script auto-regenerates because it runs non-interactively during planning
- Collect all reference.yaml + run_dir paths, call `aitask_explain_format_context.py --max-plans N`
- Follow all shell conventions (set -euo pipefail, portable sed/grep/mktemp)
- Graceful no-op if no explain data can be generated (e.g., new files with no history)

Output format:
```markdown
## Historical Architectural Context

### t166: Add aitask_archive.sh
**Historical context for:** .aitask-scripts/aitask_archive.sh, .aitask-scripts/lib/task_utils.sh, .aitask-scripts/aitask_update.sh
**Staleness:** CURRENT

<full plan content from p166.md, frontmatter stripped>

---

### t209: Fix sed incompatibilities on macOS
**Historical context for:** .aitask-scripts/aitask_archive.sh, .aitask-scripts/lib/task_utils.sh
**Staleness:** CURRENT

<full plan content from p209.md>

---

### Context Notes
- Plans sorted by number of affected files (decreasing)
- 2 of 3 plans found; 1 plan missing (t221_2)
- Each plan appears once, listing all target files it provides context for
```

### t369_3: Update planning skill instructions and profile schema (Claude Code)

Add historical context gathering step to planning workflow, profile schema, and pick skill.

**Modify**: `.claude/skills/task-workflow/planning.md` — Add context gathering instruction in Step 6.1
**Modify**: `.claude/skills/task-workflow/profiles.md` — Add `gather_explain_context` profile key
**Modify**: `.claude/skills/aitask-pick/SKILL.md` — Add Step 0a-bis for `ask` prompt
**Modify**: `aitasks/metadata/profiles/fast.yaml` and `default.yaml` — Add `gather_explain_context` defaults

#### Profile key: `gather_explain_context`

| Value | Meaning |
|-------|---------|
| `0` | Disabled — never gather historical context |
| `N` (positive integer, e.g. `3`, `5`) | Extract at most N plans, greedily ordered by affected line count |
| `"ask"` | Prompt user right after profile selection (Step 0a) for the max number of plans |
| omitted | Treated as `"ask"` — prompt the user for the value |

**Greedy selection**: For each target file, the script picks the top N plans by line contribution. Plans are then deduplicated across files and sorted by number of files covered (decreasing).

**When value is `"ask"`**: Immediately after Step 0a (profile selection), before Step 0b, prompt via `AskUserQuestion`:
- Question: "How many historical plans to extract for context during planning? (0 = disabled)"
- Header: "Context"
- Options:
  - "1 plan" (description: "Extract the single most relevant plan by code contribution")
  - "3 plans" (description: "Extract top 3 most relevant plans — more context, more token usage")
  - "0 (disabled)" (description: "Skip historical context gathering entirely")
- Store the answer as `explain_context_max_plans` for use in Step 6.1

**Sensible defaults for shipped profiles:**
- `fast.yaml`: `gather_explain_context: 0` (disabled — speed priority)
- `fast_with_historical_ctx.yaml` (NEW): Copy of `fast.yaml` with `gather_explain_context: 1` (top 1 plan)
- `default.yaml`: `gather_explain_context: ask`
- `remote.yaml`: `gather_explain_context: 0` (disabled — non-interactive, used by pick-remote/pick-web)

**When omitted from a profile**: Treated as `"ask"` — the user is prompted in Step 0a-bis.

New instruction in planning.md Step 6.1 (after "Explore the codebase" and before "Create a detailed plan"):
```markdown
- **Historical context gathering:**
  Resolve the effective max plans value:
  - If `gather_explain_context` is a number from the profile (or stored from the `ask` prompt): use that value
  - If omitted: treated as `"ask"` — should have been prompted in Step 0a-bis
  - If 0: skip entirely. Display: "Historical context: disabled"

  If max plans > 0, after identifying key files you plan to modify:
  \`\`\`bash
  ./.aitask-scripts/aitask_explain_context.sh --max-plans <N> <file1> <file2> [...]
  \`\`\`
  **IMPORTANT:** The output is **informational context only** — it shows the historical reasoning and design decisions behind the existing code you are about to modify. Use this context to make better-informed decisions when designing your implementation plan (e.g., understand why code is structured a certain way, what patterns were established, what gotchas were encountered). Do NOT treat historical plans as instructions to follow — they describe past work, not current requirements.
```

### t369_4: Update skills for other agents (OpenCode, Codex, Gemini CLI)

Propagate the planning instruction to all agent formats.

**Modify**: OpenCode, Codex CLI, Gemini CLI skill/command files for aitask-pick and task-workflow
- The core instruction is identical (all agents can run shell scripts)
- Adapt wording for each agent's interpretation style

### t369_5: Write tests

**New file**: `tests/test_explain_context.sh`
**Reference**: `tests/test_setup_git.sh` (test pattern)

Tests:
- `aitask_explain_format_context.py` with synthetic reference.yaml and plan files
- `aitask_explain_context.sh` with a temp git repo and known commit history
- Cache reuse (run twice, verify second run uses cache)
- `--max-plans` limiting
- Graceful no-op when no explain data available
- Follow existing test patterns: `assert_eq`/`assert_contains`, PASS/FAIL summary

### t369_6: Update `ait settings` TUI for `gather_explain_context` field

Add the new profile field to the settings TUI so it appears when editing execution profiles.

**Modify**: `.aitask-scripts/settings/settings_app.py`
- Add `gather_explain_context` to `PROFILE_FIELD_TYPES` dict (line ~91 area) with type `"int_or_ask"` — a new type that accepts integer values or the string `"ask"` (or a custom enum `["ask", "0", "1", "2", "3", "5"]`)
- Add description to `PROFILE_FIELD_DESCRIPTIONS` dict (line ~162 area)
- Add to the `PROFILE_FIELD_GROUPS` tuple (line ~266 area) — in the "Planning" group alongside `plan_preference`

### t369_7: Update website documentation for `gather_explain_context`

Document the new profile field and the historical context feature in the website.

**Modify**: `website/content/docs/tuis/settings/reference.md` — Add `gather_explain_context` to the profile schema table (line ~70 area)
**Modify**: `website/content/docs/skills/aitask-pick/_index.md` — Document the historical context gathering step in the pick workflow description
**Possibly modify**: `website/content/docs/tuis/settings/_index.md` — Update the profiles tab description if it lists specific fields

## Verification

After all child tasks:
1. Pick a real task and run `/aitask-pick` — verify the planning phase shows the new context gathering instruction
2. Manually call `./aitask-scripts/aitask_explain_context.sh .aitask-scripts/aitask_archive.sh` and verify output contains relevant plan summaries
3. Run `bash tests/test_explain_context.sh` — all tests PASS
4. Run `shellcheck .aitask-scripts/aitask_explain_context.sh` — clean

## Step 9: Post-Implementation
After all child tasks complete, archive parent task t369 and its plan.
