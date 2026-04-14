---
Task: t547_2_profile_verification_keys.md
Parent Task: aitasks/t547_plan_verify_on_off_in_task_workflow.md
Sibling Tasks: aitasks/t547/t547_3_workflow_verify_integration.md
Archived Sibling Plans: aiplans/archived/p547/p547_1_plan_verified_helper.md
Base branch: main
plan_verified: []
---

# t547_2: Profile verification keys

## Context

Parent task t547 extends execution profiles with plan verification tracking. This child adds two new profile keys and documents them in the canonical schema. Pure config + documentation — no code changes. Both keys apply uniformly to parent and child tasks (no `_child` variants, per user decision).

The existing external plan at `aiplans/p547/p547_2_profile_verification_keys.md` was read and verified against the current codebase. All file paths, assumptions, and surrounding context still match — the plan is sound and can be executed as-written.

### Verified current state

- `.claude/skills/task-workflow/profiles.md` — schema table at lines 21–37. `plan_preference` at line 29, `plan_preference_child` at line 30, `post_plan_action` at line 31. Insertion point: after line 30.
- `aitasks/metadata/profiles/fast.yaml` — contains `plan_preference: use_current` and `plan_preference_child: verify` as consecutive lines (positions 6–7). Insertion point: immediately after `plan_preference_child`.
- `aitasks/metadata/profiles/default.yaml` and `remote.yaml` — must remain unchanged.
- `.aitask-scripts/aitask_scan_profiles.sh` — only reads `name` and `description`, so unknown keys are harmlessly ignored (no parser change needed).
- Child 1 (t547_1) is archived; its helper `aitask_plan_verified.sh` uses these exact key names as arguments to `decide`. Child 3 will consume this profile config.

## Files to modify

| File | Change |
|---|---|
| `.claude/skills/task-workflow/profiles.md` | Add 2 rows to schema table + descriptive paragraph |
| `aitasks/metadata/profiles/fast.yaml` | Add 2 keys explicitly set to default values |

## Implementation

### Step 1 — `profiles.md` schema table

Insert two rows after the `plan_preference_child` row (after line 30):

```
| `plan_verification_required` | int | no | Positive integer; default `1` | Step 6.0 |
| `plan_verification_stale_after_hours` | int | no | Positive integer; default `24` | Step 6.0 |
```

### Step 2 — `profiles.md` descriptive paragraph

After the schema table (after line 38, the "Only `name` and `description` are required..." line), add a paragraph explaining the new keys. Plan-related keys are described inline in the table, but these two warrant prose because they interact with plan file metadata. The paragraph:

> **Plan verification tracking (`plan_verification_required`, `plan_verification_stale_after_hours`):** When `plan_preference` (or `plan_preference_child`) is `"verify"`, the workflow consults the plan file's `plan_verified` metadata list to decide whether a fresh verification is actually needed. `plan_verification_required` is the number of fresh (non-stale) entries required to skip re-verification — default `1` means a single prior verification is sufficient. `plan_verification_stale_after_hours` is how old (in hours) an entry may be before it no longer counts as fresh — default `24`. Both keys apply uniformly to parent and child tasks — there are no `_child` variants. The actual decision (skip / verify / ask) is computed by `./.aitask-scripts/aitask_plan_verified.sh decide`, which returns a structured report the workflow parses directly.

### Step 3 — `fast.yaml`

Insert two new lines immediately after `plan_preference_child: verify` (line 7):

```yaml
plan_verification_required: 1
plan_verification_stale_after_hours: 24
```

Values match the defaults but are explicit so readers of `fast.yaml` see the intent without cross-referencing `profiles.md`.

### Step 4 — No changes to `default.yaml` / `remote.yaml`

Both files must be byte-identical to pre-task state. Verify with `git diff HEAD`.

### Step 5 — Create follow-up task for settings TUI support

The `ait settings` TUI (`.aitask-scripts/settings/settings_app.py`) has no `int` field type — it currently supports only `bool`, `enum`, and `string`. Adding the new keys there is a separate, non-trivial change (new widget rendering + validation), so it is deferred to a follow-up task created at the end of this implementation.

Investigation findings (already gathered):
- **File**: `.aitask-scripts/settings/settings_app.py` (3092 lines, Textual framework)
- **Three registries to update** (in `_populate_profiles_tab()` neighborhood):
  - `PROFILE_SCHEMA` (~line 94) — currently `(type, options)` tuples with `type ∈ {"bool","enum","string"}`. Needs a new `"int"` type (or `("int", {"min":1,"default":N})`).
  - `PROFILE_FIELD_INFO` (~line 160) — help text (short/long).
  - `PROFILE_FIELD_GROUPS` (~line 309) — visual grouping. Put both new keys near existing `plan_preference_child` (Planning group).
- **Widget rendering branch** (~lines 2738–2763) — currently branches on `bool`/`enum`/`string`. Needs a new `int` branch that renders an `Input` widget with numeric validation and supports the `_UNSET` sentinel so users can clear back to the default.
- **No adapter-specific updates needed** — `settings_app.py` is shared across Claude Code / Codex / Gemini / OpenCode. The TUI is launched via the `ait settings` shell command, not through any skill.

Create the follow-up task at the end of Step 9 (just before archive) using the **Batch Task Creation Procedure**:

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name "settings_tui_int_field_support_and_plan_verification_keys" \
  --priority medium --effort medium \
  --issue-type feature \
  --labels settings_tui,task_workflow \
  --depends 547_2 \
  --description-file <desc_tmpfile>
```

The description file should include:
- Context: why the keys exist (pointer to t547 parent plan) and why they need TUI support.
- Files to modify: `.aitask-scripts/settings/settings_app.py` only.
- Implementation plan: add `int` type to the widget branch at ~2738–2763 (use `Input` widget + numeric validator + `_UNSET` clear-to-default), then register both keys in `PROFILE_SCHEMA`, `PROFILE_FIELD_INFO`, and `PROFILE_FIELD_GROUPS` (Planning group).
- Verification: run `ait settings`, open Profiles tab, edit `fast`, confirm both int fields render, accept integer input, reject non-numeric, and clear to default.
- Note: parallel-safe with t547_3 (workflow integration) — they touch different files.

## Verification

1. `./.aitask-scripts/aitask_scan_profiles.sh` — must list 3 profiles (default, fast, remote) with no INVALID entries
2. `grep -n 'plan_verification_required\|plan_verification_stale_after_hours' .claude/skills/task-workflow/profiles.md` — confirm both keys present
3. `cat aitasks/metadata/profiles/fast.yaml` — visually verify the 2 new keys
4. `git diff HEAD -- aitasks/metadata/profiles/default.yaml aitasks/metadata/profiles/remote.yaml` — expect no output
5. Follow-up task file exists at `aitasks/t<N>_settings_tui_int_field_support_and_plan_verification_keys.md` (whatever ID `aitask_create.sh` assigns)
6. No shellcheck (no bash changes)

After verification, proceed to **Step 8** (User Review) and then **Step 9** (Post-Implementation) per the task-workflow skill — commit code files with `feature: ... (t547_2)`, commit the plan with `ait: Update plan for t547_2`, archive via `./.aitask-scripts/aitask_archive.sh 547_2`, then push.

## Final Implementation Notes

- **Actual work done:**
  - Added two rows (`plan_verification_required`, `plan_verification_stale_after_hours`) to the Profile Schema Reference table in `.claude/skills/task-workflow/profiles.md`, positioned immediately after the `plan_preference_child` row so readers encounter them in the planning-related block.
  - Added a descriptive blockquote paragraph right after the "Only `name` and `description`..." sentence, explaining how the two keys interact with `plan_preference`/`plan_preference_child` and referencing `aitask_plan_verified.sh decide` as the computation source.
  - Added the two keys to `aitasks/metadata/profiles/fast.yaml` immediately after `plan_preference_child: verify` with explicit default values (`1` and `24`).
  - Left `aitasks/metadata/profiles/default.yaml` and `aitasks/metadata/profiles/remote.yaml` untouched (verified via `./ait git diff HEAD`).
  - Ran `./.aitask-scripts/aitask_scan_profiles.sh` after the edits — all 3 profiles still parse cleanly with no INVALID entries, confirming that the scanner ignores unknown keys (it only reads `name` and `description`).

- **Deviations from plan:**
  - None. The verify pass in Step 6 confirmed the plan matched the current codebase; implementation followed the plan step-for-step.
  - Note: `.claude/skills/task-workflow/profiles.md` is the source of truth per CLAUDE.md. Corresponding updates to `.gemini/skills/`, `.agents/skills/`, and `.opencode/skills/` adapters were not made here and should be handled as separate follow-up aitasks if those trees are kept in sync — this is the standard convention in this repo.

- **Issues encountered:** None.

- **Key decisions:**
  - Placed the new rows in the schema table (compact inline form) AND added a separate descriptive paragraph, because the keys' semantics depend on plan file metadata (`plan_verified`) that the table rows alone cannot fully explain. The paragraph references the concrete helper script (`aitask_plan_verified.sh decide`) so Child 3's integration is easy to audit against the docs.
  - Set the values in `fast.yaml` explicitly to their defaults (`1` and `24`) rather than omitting them. This surfaces the intent to anyone reading `fast.yaml` without forcing them to cross-reference `profiles.md` for defaults, at the minor cost of two extra lines.
  - Deferred settings TUI integration to a follow-up task (see Notes below). The TUI schema currently supports only `bool`/`enum`/`string` — adding a new `int` widget type with validation is a separate, non-trivial change that should not block Child 3.

- **Notes for sibling tasks:**
  - **Canonical key names are locked in:** `plan_verification_required` and `plan_verification_stale_after_hours`. Child 3 (`t547_3_workflow_verify_integration`) must use these exact strings when reading the profile for the verify decision.
  - **Defaults are documented in two places:** `profiles.md` (canonical) and `fast.yaml` (explicit). If Child 3's profile loader does not see either key, it should fall back to `1` and `24` respectively. Child 1's `aitask_plan_verified.sh decide` subcommand requires both values as explicit arguments — it does not assume defaults — so Child 3 must pass them.
  - **No `_child` variants:** both keys apply uniformly to parent and child tasks. If that proves too coarse in practice, Child 3 can still special-case based on `is_child` in the workflow markdown without touching these canonical keys.
  - **Scanner compatibility confirmed:** `aitask_scan_profiles.sh` parses only `name`/`description`, so adding new profile keys is a zero-risk operation. Child 3 can add new keys freely without touching the scanner.
  - **Settings TUI lag:** a follow-up task was created to add `int`-type widget support to `.aitask-scripts/settings/settings_app.py` and register both keys there. This is parallel-safe with Child 3 (different files).
