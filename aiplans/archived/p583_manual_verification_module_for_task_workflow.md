---
Task: t583_manual_verification_module_for_task_workflow.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583 — Manual-Verification Module for `/aitask-pick`

## Context

Many tasks produce behavior that automated tests cannot fully validate: TUI flows, live agent launches, on-disk artifact inspection, multi-screen navigation. Today the burden is handled ad-hoc — a "Verification" section in the plan file, or (for parent tasks with multiple TUI-heavy siblings) an aggregate sibling like `aitasks/t571/t571_7_manual_verification_structured_brainstorming.md`. Both approaches tend to get skipped and have no state tracking.

This task turns the pattern into a first-class module with **two integrated flows**:

1. **Generation flow** — during planning, `/aitask-pick` (and `/aitask-explore`) proactively detects tasks whose behavior needs manual verification and offers to create the verification task (an aggregate sibling for parent tasks, a follow-up for standalone tasks).
2. **Running flow** — when a manual-verification task is picked, `/aitask-pick` runs an interactive `Pass`/`Fail`/`Skip`/`Defer` loop per checklist item, persists state in the task body, refuses archival until all items are terminal, and auto-creates follow-up bug tasks on `Fail`.

Both flows share one data model: `issue_type: manual_verification`, a `verifies: [task_id, ...]` list frontmatter field, and a `## Verification Checklist` markdown section in the task body.

## Design Decisions (confirmed with user)

1. **State format: inline markdown checkboxes** under a `## Verification Checklist` H2 — `- [ ]` (pending), `- [x]` (pass), `- [fail]`, `- [skip]`, `- [defer]`. The body is the source of truth; no new state-storage frontmatter field.
2. **Trigger: `issue_type: manual_verification`** added to `aitasks/metadata/task_types.txt`.
3. **Meta-dogfood: in-scope** as the final aggregate sibling via `verifies: [t583_1..t583_8]`.
4. **Parser: Python, not bash** (user-requested in review). Robust markdown parsing in bash with `sed`/`grep` is error-prone across macOS/Linux. Python follows the existing `.aitask-scripts/aitask_*.py` pattern (`aitask_codemap.py`, `aitask_stats.py`, etc.). A thin bash wrapper (`aitask_verification_parse.sh`) can exist for uniformity with other helpers, but the logic lives in Python.

Two frontmatter touch-points:
- `issue_type` list → one-line additions to `aitasks/metadata/task_types.txt` and `seed/aitasks/metadata/task_types.txt`.
- New list field `verifies:` → full 3-layer propagation (`aitask_create.sh`, `aitask_update.sh`, `aitask_fold_mark.sh`, `board/aitask_board.py` `TaskDetailScreen`), following the `depends:` precedent.

## Integration Story — where the module plugs into the current workflow

The user's review question — *"how can we best integrate this in the current task workflow?"* — the answer in one picture:

```
                            ┌─────────────────────────────────────────────┐
                            │            GENERATION (plan-time)           │
                            │                                             │
planning.md §6.1 child-task │  After ≥2 children drafted:                 │
creation  ──────────────────┤  scan them → offer aggregate sibling with   │
                            │  verifies:[children] + checklist skeleton   │
                            │                                             │
planning.md §6.1 single     │  After single-task ExitPlanMode:            │
task   ─────────────────────┤  if signal detected → offer follow-up task  │
                            │  with verifies:[this_task]                  │
                            │                                             │
aitask-explore SKILL.md ────┤  Post-draft: same check before finalizing   │
                            └─────────────────────────────────────────────┘
                                                 │
                                                 ▼
                                  task created with issue_type:
                                  manual_verification, verifies: [...],
                                  ## Verification Checklist in body
                                                 │
                                                 ▼
                            ┌─────────────────────────────────────────────┐
                            │             RUNNING (pick-time)             │
                            │                                             │
SKILL.md Step 3 check 3  ──►│  issue_type == manual_verification?         │
                            │  → branch into manual-verification.md       │
                            │                                             │
manual-verification.md    ──┤  iterate checklist items:                   │
                            │   • Pass/Fail/Skip/Defer per item           │
                            │   • Fail → create follow-up bug + annotate  │
                            │   • persist state via parser                │
                            │                                             │
SKILL.md Step 9 archival ──►│  gate: refuse archive unless all items      │
                            │  terminal; carry-over task for defers       │
                            └─────────────────────────────────────────────┘
```

The generation flow is one `AskUserQuestion` added at two specific spots in `planning.md` (child-task creation + single-task post-plan) plus one thin helper that seeds the task body with a checklist. It does **not** attempt auto-detection of "does this need manual verification?" by keyword scanning — that heuristic is unreliable. Instead, the question is always asked (with a quick "No" option) at the moments when user attention is already on the plan — so the cost of one extra prompt is small, and the benefit is that the verification work becomes visible and pickable.

## Out of Scope

- Automated Pilot/TUI test orchestration — that's `/aitask-qa`'s domain.
- Mirror ports of the new skill files into `.gemini/`, `.agents/`, `.opencode/` — per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS", source of truth is Claude Code; separate follow-up tasks will mirror after the design settles.
- Auto-detecting manual-verification need by keyword scanning. The planning-flow integration asks the user; it does not guess.

## Cross-Cutting: Whitelisting new helper scripts (recurring-issue guardrail)

Every new script under `.aitask-scripts/` that is invoked by a skill must be whitelisted in **five** places — **runtime configs (for this project)** AND **seed configs (for new projects bootstrapped via `ait setup`)**. Missing any one of these causes users of the corresponding agent to be prompted on every single invocation, which is a recurring friction source.

| Touchpoint | Entry shape |
|-----------|------------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_<name>.sh:*)"` in `permissions.allow` array |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rules]]` block with `commandPrefix = "./.aitask-scripts/aitask_<name>.sh"` |
| `seed/claude_settings.local.json` | mirror of `.claude/settings.local.json` entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of runtime gemini policy entry |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_<name>.sh *": "allow"` entry |

**Codex exception:** `.codex/config.toml` and `seed/codex_config.seed.toml` use a `prompt`/`forbidden`-only permission model per the codex config's own comment — there is no `allow` decision. Codex does NOT need a whitelist entry; it prompts by default and that is the expected behavior for now.

**Each child that introduces a new helper script is responsible for its own whitelisting** (the helper and its whitelist land in the same commit). Helpers added in this parent:

| Helper | Introduced in | Must be whitelisted |
|--------|--------------|----------------------|
| `aitask_verification_parse.sh` (wraps Python) | t583_1 | yes |
| `aitask_verification_followup.sh` | t583_3 | yes |
| `aitask_create_manual_verification.sh` | t583_7 | yes |

The Python helper `aitask_verification_parse.py` is invoked via its bash wrapper, so only the `.sh` name needs to appear in whitelists.

**Documentation of this convention** (CLAUDE.md update) is folded into t583_8 so future contributors enumerate these touchpoints at plan time.

## Decomposition — 9 Child Tasks

Because this is a high-effort multi-layer change (parser + workflow procedure + helpers + frontmatter propagation + planning-flow integration + tests + docs + dogfood), break into children. Dependency order:

| Child | Name | Depends on | Rationale |
|-------|------|-----------|-----------|
| t583_1 | `verification_parser_python_helper` | — | Foundational state primitive (Python) |
| t583_2 | `verifies_frontmatter_field_three_layer` | — | Independent; enables aggregate tasks |
| t583_3 | `verification_followup_helper_script` | t583_1 | Fail → bug task creator |
| t583_4 | `manual_verification_workflow_procedure` | t583_1, t583_3 | Procedure file + SKILL.md Step 3 branch |
| t583_5 | `archival_gate_and_carryover` | t583_1 | Pre-archive gate + deferred carry-over |
| t583_6 | `issue_type_manual_verification_and_unit_tests` | t583_1, t583_2, t583_3 | Register new type + tests for helpers |
| t583_7 | `plan_time_generation_integration` | t583_2, t583_6 | planning.md + aitask-explore edits + seeder helper |
| t583_8 | `documentation_website_and_skill` | t583_1..7 | Website page + aitask-pick skill docs + CLAUDE.md pointer |
| t583_9 | `meta_dogfood_aggregate_verification` | t583_1..8 | Aggregate with `verifies:` list; exercises every branch |

Sequential pick order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9.

## Child-by-Child Scope

### t583_1 — Parser (Python helper)

**Primary file:** `.aitask-scripts/aitask_verification_parse.py`

**Why Python (not bash):** robust markdown parsing across macOS/Linux — no BSD vs GNU `sed`/`grep` portability concerns; easier unit testing via pytest or the existing bash `assert_eq` pattern; the Python file can expose a `main()` callable by a thin bash wrapper for consistency with other helpers if desired.

**Subcommands:**
- `parse <task_file>` — one line per item on stdout: `ITEM:<index>:<state>:<line_number>:<text>`. `<state>` ∈ `pending|pass|fail|skip|defer`.
- `set <task_file> <index> <state> [--note <text>]` — mutate body in-place: flip the checkbox, append ` — <STATE> YYYY-MM-DD HH:MM [<note>]`; refresh `updated_at` frontmatter.
- `summary <task_file>` — counts: `TOTAL:N PENDING:A PASS:B FAIL:C SKIP:D DEFER:E`.
- `terminal_only <task_file>` — exit 0 if every item is terminal (pass/fail/skip). Exit 2 with `PENDING:<count>` or `DEFERRED:<count>` otherwise. This is the archival-gate primitive.
- `seed <task_file> --items <file>` — populate a fresh `## Verification Checklist` H2 in a task body from a newline-separated items file (used by the seeder in t583_7).

**Parser rules:**
- First H2 whose title matches (case-insensitive) `^verification( checklist)?$` or `^checklist$`.
- Within that section, scan until the next H2 or EOF; each line matching `^[ \t]*- \[([ x]|fail|skip|defer)\]` is an item.
- Suffix parsing: everything after a literal ` — ` on the same line is the state annotation.

**Bash wrapper (required, not optional):** `.aitask-scripts/aitask_verification_parse.sh` — one-liner dispatcher `exec python3 "$SCRIPT_DIR/aitask_verification_parse.py" "$@"`. Call sites use the `.sh` name so (a) future re-implementations can swap the backend, and (b) whitelists only need a single `.sh` entry per helper.

**Whitelist updates for this helper (see Cross-Cutting section above):**
- `.claude/settings.local.json` → add `"Bash(./.aitask-scripts/aitask_verification_parse.sh:*)"`
- `.gemini/policies/aitasks-whitelist.toml` → add `[[rules]]` block with `commandPrefix = "./.aitask-scripts/aitask_verification_parse.sh"`
- `seed/claude_settings.local.json` → mirror the Claude entry
- `seed/geminicli_policies/aitasks-whitelist.toml` → mirror the gemini entry
- `seed/opencode_config.seed.json` → `"./.aitask-scripts/aitask_verification_parse.sh *": "allow"`
- Codex: skip (prompt-only model)

### t583_2 — `verifies:` frontmatter field (3-layer propagation)

Follow the `depends:` precedent:

1. **`.aitask-scripts/aitask_create.sh`** — add `--verifies t1,t2,t3` batch flag + interactive prompt (shown only when `issue_type: manual_verification`); emit `verifies: [...]` via `format_yaml_list()`. Touch points mirror `depends:` at ~line 390, ~470, ~1398.
2. **`.aitask-scripts/aitask_update.sh`** — add `--add-verifies`, `--remove-verifies`, `--set-verifies` flags; parse via `parse_yaml_list()` + `normalize_task_ids()`; pass through to `write_task_file()`. Mirror `depends` at ~335-338, ~442.
3. **`.aitask-scripts/aitask_fold_mark.sh`** — union folded tasks' `verifies:` into the primary at fold time, alongside the existing `folded_tasks` handling.
4. **`.aitask-scripts/board/aitask_board.py`** — add `VerifiesField` widget class to `TaskDetailScreen.compose()` mirroring `DependsField` (~1986-1992); shells out to `aitask_update.sh --batch <id> --set-verifies …`.

### t583_3 — Follow-up helper (`aitask_verification_followup.sh`)

**Usage:**
```
aitask_verification_followup.sh --from <task_id> --item <index> [--origin <feature_task_id>]
```

**Behavior:**
- Load task file via `resolve_task_id_to_file()`; extract failing item via `aitask_verification_parse.sh parse`.
- If task has `verifies: [a, b, c]` and `--origin` omitted, use `AskUserQuestion` to ask which sibling the failure belongs to (options = the `verifies` list). Otherwise default `--origin` to `--from`.
- Resolve commits for `--origin` by invoking the existing `detect_commits()` function in `aitask_issue_update.sh` (~line 246) — expose it via `source` or re-run the underlying `git log --oneline --grep` incantation; pick whichever keeps `aitask_issue_update.sh` stable.
- Extract touched files: `git show --name-only --format= <hash>` per commit.
- Compose a child-task description (commits, files, verbatim failing item text, `related: [<origin>]` frontmatter).
- Shell out to `aitask_create.sh --batch --issue-type bug --priority medium --effort medium --labels verification,bug --related <origin> --desc-file <tmp> --commit`.
- Output: `FOLLOWUP_CREATED:<task_id>:<path>`.
- Append `— FAILED <timestamp> (follow-up: t<new_id>)` to the failed item via `aitask_verification_parse.sh set ... --note "follow-up t<new_id>"`.
- If origin has an archived plan, append a back-reference under its `Final Implementation Notes`; otherwise skip silently.

**Whitelist updates for this helper:**
- `.claude/settings.local.json` → add `"Bash(./.aitask-scripts/aitask_verification_followup.sh:*)"`
- `.gemini/policies/aitasks-whitelist.toml` → add `[[rules]]` block
- `seed/claude_settings.local.json` → mirror Claude entry
- `seed/geminicli_policies/aitasks-whitelist.toml` → mirror gemini entry
- `seed/opencode_config.seed.json` → `"./.aitask-scripts/aitask_verification_followup.sh *": "allow"`
- Codex: skip

### t583_4 — Manual-verification workflow procedure

**New file:** `.claude/skills/task-workflow/manual-verification.md` — interactive loop:
1. `aitask_verification_parse.sh summary` → if `TOTAL:0`, warn and offer to seed from the plan's `## Verification` section (or bail).
2. For each `pending` or `defer` item in order, render the text and prompt via `AskUserQuestion`: `Pass` / `Fail` / `Skip (with reason)` / `Defer`.
3. Persist state via `aitask_verification_parse.sh set` after each answer.
4. `Fail` → `aitask_verification_followup.sh --from <task_id> --item <index>`; continue after FOLLOWUP_CREATED.
5. `Skip` → prompt for reason; stored as annotation.
6. After the loop, commit via `./ait git commit -m "ait: Record verification state for t<task_id>"`.
7. Hand off to Step 9 archival (which gates on `terminal_only`; see t583_5).

**`SKILL.md` Step 3 branch** — add after the existing Done / orphaned checks:
```
Check 3 — Manual-verification task:
- If frontmatter issue_type == manual_verification:
  - Execute the Manual Verification Procedure (see manual-verification.md)
  - Skip Steps 6-8 entirely; proceed to Step 9 archival
```
Steps 4-5 (ownership lock + optional worktree) still run — verification is work that should be owned and locked.

### t583_5 — Archival gate + carry-over

**`.aitask-scripts/aitask_archive.sh`:**
- After `parse_args` in `main()` (~line 532), before dispatching:
  - If task's `issue_type == manual_verification`, run `aitask_verification_parse.sh terminal_only <task_file>`.
  - Exit 2 with `VERIFICATION_PENDING:<count>` if any items are still `pending`.
  - If only `defer` items remain non-terminal, exit 2 with `VERIFICATION_DEFERRED:<count>` unless `--with-deferred-carryover` is set.
- New flag `--with-deferred-carryover`: before archiving, create a new manual-verification task via `aitask_create.sh --batch --issue-type manual_verification --name "<orig>_deferred_carryover" --verifies <orig verifies> --desc-file <tmp>`. Description = filtered checklist with only the `defer` items. Output `CARRYOVER_CREATED:<new_id>:<path>`.

**`manual-verification.md`** gets a post-loop prompt offering "Archive with deferred items" only when all non-`defer` items are terminal.

### t583_6 — `issue_type` registration + unit tests

**Registration:**
- Add `manual_verification` to `aitasks/metadata/task_types.txt` and `seed/aitasks/metadata/task_types.txt`.
- Commit subjects for manual-verification tasks use the literal prefix `manual_verification: <desc> (tNN)` per existing convention.

**Unit tests** (in `tests/`):
- `test_verification_parse.sh` — fixtures: no section, empty section, all states, mixed, malformed checkboxes, H2 case-insensitivity, suffix round-trip. Invokes the Python helper via the bash wrapper.
- `test_verification_followup.sh` — stub `detect_commits`; assert follow-up description contains commit hashes, files, failing-item text; assert `--origin` prompt triggered when `verifies:` has >1 entries.
- `test_verifies_field.sh` — create-update-fold round-trip (create with `--verifies 10,11`, update add/remove, fold two tasks → confirm union).

### t583_7 — Plan-time generation integration

**What this child adds (the "integration" the user asked about):**

1. **New seeder helper** `.aitask-scripts/aitask_create_manual_verification.sh`:
   - Wraps `aitask_create.sh --batch --issue-type manual_verification`.
   - Takes `--verifies <ids>`, `--parent <id>` (for aggregate-sibling mode) or `--related <id>` (for follow-up mode), `--items <file>` (checklist seed), `--name <name>`.
   - Writes the task file, runs `aitask_verification_parse.sh seed` on the new file to inject the `## Verification Checklist` H2.
   - Commits with `ait: Create manual-verification task tN`.

2. **`.claude/skills/task-workflow/planning.md` edits:**

   - **§6.1 "Complexity Assessment" — child-task branch.** After the child-task-creation loop finishes and before the "Child task checkpoint" (~line 170), insert:

     ```
     ### Manual Verification Sibling (post-child-creation)

     After creating the child tasks, use `AskUserQuestion`:
     - Question: "Do any of these children produce behavior that needs manual
       (in-person, at-the-keyboard) verification — TUI flows, live agent launches,
       on-disk artifact inspection? If yes, an aggregate manual-verification
       sibling will be created with `verifies: [t<parent>_1, ..., t<parent>_N]`
       and a `## Verification Checklist` skeleton."
     - Header: "Manual verify"
     - Options:
       - "No, not needed"
       - "Yes, add aggregate sibling (Recommended for TUI/UX work)"
       - "Yes, but let me choose which children it verifies"

     On a Yes, if the user chose "let me choose", ask a multiSelect with one
     option per child. Then run:
     ./.aitask-scripts/aitask_create_manual_verification.sh \
         --parent <parent_num> \
         --name manual_verification_<parent_slug> \
         --verifies <selected_child_ids_csv> \
         --items <tmp_checklist>

     The <tmp_checklist> is generated from the selected children's plan files:
     one bullet per "Verification" section entry if present, else a single stub
     item "TODO: define verification for t<child_id>" that the user fills in
     while running the module.
     ```

   - **§6.1 "Planning" — single-task branch.** After `ExitPlanMode` for a non-parent plan (i.e., when the "create child tasks" path was *not* taken), insert:

     ```
     ### Manual Verification Follow-up (post-ExitPlanMode, single-task path)

     If this plan's implementation could introduce behavior that only a human can
     validate (TUI, UI, live-agent invocation, on-disk artifact checks), use
     `AskUserQuestion`:
     - Question: "Does this task need a manual verification follow-up?
       On Yes, a standalone manual-verification task will be created with
       `verifies: [t<this_task>]`. It is picked after this task is archived."
     - Header: "Manual verify"
     - Options:
       - "No"
       - "Yes, create follow-up task"

     On Yes, run:
     ./.aitask-scripts/aitask_create_manual_verification.sh \
         --related <this_task_id> \
         --name manual_verification_<this_task_slug>_followup \
         --verifies <this_task_id> \
         --items <tmp_checklist>

     The <tmp_checklist> is derived from this plan's Verification section.
     ```

3. **`.claude/skills/aitask-explore/SKILL.md` edit** — in the final "Create task" phase of explore, after the task draft is complete but before the batch-create step, reuse the same question (single-task follow-up variant). Explore-created tasks typically haven't had a plan written yet, so the checklist seed is a single stub item.

**Whitelist updates for the new seeder helper:**
- `.claude/settings.local.json` → add `"Bash(./.aitask-scripts/aitask_create_manual_verification.sh:*)"`
- `.gemini/policies/aitasks-whitelist.toml` → add `[[rules]]` block
- `seed/claude_settings.local.json` → mirror Claude entry
- `seed/geminicli_policies/aitasks-whitelist.toml` → mirror gemini entry
- `seed/opencode_config.seed.json` → `"./.aitask-scripts/aitask_create_manual_verification.sh *": "allow"`
- Codex: skip

**Why this placement is right (addressing the user's integration question):**
- Planning time is when the author knows best what needs verifying. Asking then (vs. at pick-time or archival-time) is cheapest.
- Two insertion points cover both shapes: aggregate sibling for parents with children, follow-up task for single-task plans.
- `aitask-explore` integration covers the "task was born without a full plan" case.
- No auto-detection by keyword scanning — the question is always asked but is one-click "No" if unneeded.
- All three call sites funnel through `aitask_create_manual_verification.sh`, so the seed behavior (description template, checklist items, `verifies:` wiring) stays consistent.

### t583_8 — Documentation

**Website:** `website/content/docs/workflows/manual-verification.md` — concepts, checklist format, generation flow (both aggregate and follow-up), running flow (Pass/Fail/Skip/Defer), fail→follow-up behavior, `verifies:` field semantics, defer/carry-over.

**Skill / guidance touch-ups:**
- `.claude/skills/aitask-pick/SKILL.md` — short "Manual-Verification Branch" note in Notes section referencing `task-workflow/manual-verification.md`.
- `.claude/skills/aitask-explore/SKILL.md` — cross-reference to the new integration step.
- `CLAUDE.md` — two subsection edits:
  1. **Manual verification** — short subsection under Project-Specific Notes with pointer to the website page.
  2. **Whitelisting new helper scripts** — new subsection under "Shell Conventions" (or a new top-level "Adding a New Helper Script" block parallel to "Adding a New Frontmatter Field"). Content enumerates the 5 touchpoints from the Cross-Cutting section of this plan so future contributors catch it at plan time. Codex exception noted.

Per `feedback_doc_forward_only.md`: describe only the final state; no "previously…" framing.

### t583_9 — Meta-dogfood aggregate task

- New child at `aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md`.
- `issue_type: manual_verification`, `verifies: [t583_1, t583_2, t583_3, t583_4, t583_5, t583_6, t583_7, t583_8]`.
- `## Verification Checklist` with one item per major behavior:
  - Parser round-trip on a synthetic task file (all 5 states).
  - `verifies:` frontmatter shows in `ait board` TaskDetailScreen; survives a fold.
  - Pick a manual-verification task; Pass/Fail/Skip/Defer each work; state persists across re-launches.
  - Fail branch creates a follow-up bug with correct commits + files; failed item gets `— FAILED … follow-up tN` annotation.
  - Archival gate blocks archive when items are pending.
  - Carry-over path creates a new manual-verification task with only deferred items.
  - Generation flow: parent-task planning offers aggregate sibling; single-task planning offers follow-up; `aitask-explore` offers follow-up.
  - Docs page renders on local Hugo build; CLAUDE.md pointer is wired.

Completing t583_9 validates the module end-to-end before the parent is marked Done.

## Reused Infrastructure

| Reuse | From | Purpose |
|-------|------|---------|
| `resolve_task_id_to_file()` | `.aitask-scripts/lib/task_utils.sh` | Map task IDs to paths |
| `format_yaml_list()` / `parse_yaml_list()` | `lib/task_utils.sh` | `verifies:` round-tripping |
| `normalize_task_ids()` | `lib/task_utils.sh` | Clean up user-supplied IDs |
| `detect_commits(task_id)` | `aitask_issue_update.sh` ~line 246 | Follow-up commit resolution |
| `aitask_create.sh --batch` | existing | Task creation (all generation paths go through it) |
| `./ait git` wrappers | existing | Task/plan-branch-aware git ops |
| `AskUserQuestion` / plan-mode tooling | Claude Code | Interactive prompts |
| `aitask_codemap.py` / `aitask_stats.py` pattern | existing | Python helper convention for t583_1 |

## Cross-Cutting Notes

- **Commit format:** per-child `issue_type` (e.g., `feature`, `refactor`) — never `manual_verification` (that's for task issue_type, not commit subject). Example: `feature: Add verification parser (t583_1)`.
- **Lock / status:** manual-verification tasks go through Step 4 (ownership lock) and Step 5 (optional worktree). They skip Steps 6-8 and enter the interactive loop.
- **Child plans:** one plan file per child in `aiplans/p583/p583_<N>_*.md`, written during the child-task-creation phase of this parent.
- **Mirror ports:** after the Claude Code implementation settles, spawn follow-up tasks (NOT children of t583) to mirror `.claude/skills/task-workflow/manual-verification.md` into `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/` per CLAUDE.md's source-of-truth rule.

## Verification (of this parent task's planning output)

- Child task files exist in `aitasks/t583/` with correct `depends:` wiring per the table above.
- Child plan files exist in `aiplans/p583/` for all 9 children with required metadata headers.
- Parent task status reverts to `Ready` after children are created; parent lock released.
- Only the picked child holds a lock at a time.
- Each child plan that introduces a new helper script includes an explicit "Whitelist updates" section listing all 5 touchpoints (codex skipped).
- The CLAUDE.md update in t583_8 documents the whitelisting convention project-wide — this is the authoritative home for the convention (not per-user auto-memory).

## Step 9 (Post-Implementation) — Reminder

Refer to `.claude/skills/task-workflow/SKILL.md` Step 9 for merge, build-verification, archival, and push sequence. Profile `fast` has `create_worktree: false`, so branch/worktree cleanup is a no-op; archival commits land directly on `main`.
