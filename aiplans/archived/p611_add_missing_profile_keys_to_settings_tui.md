---
Task: t611_add_missing_profile_keys_to_settings_tui.md
Base branch: main
plan_verified: []
---

## Context

Several execution-profile keys are actively read by skills and already used in shipped profiles (`fast.yaml`, `remote.yaml`) but are missing from the settings TUI's `PROFILE_SCHEMA`. Users must hand-edit YAML to set them. Goal: make them editable through `ait settings → Profiles`.

Missing keys:
- `manual_verification_followup_mode` — enum (`ask`, `never`). Used in `.claude/skills/task-workflow/manual-verification-followup.md:19`. Already set in `fast.yaml` (ask) and `remote.yaml` (never).
- `post_plan_action_for_child` — enum (same values as `post_plan_action`). Used in `.claude/skills/task-workflow/planning.md:290`. Already set in `fast.yaml` (ask).
- `review_default_modes` — string, comma-separated mode names. Used in `.claude/skills/aitask-review/SKILL.md:113`.
- `review_auto_continue` — bool. Used in `.claude/skills/aitask-review/SKILL.md:237`.
- `qa_tier` — enum (`q`, `s`, `e`). Used in `.claude/skills/aitask-qa/SKILL.md:37-51`.

Also fix an inconsistency: `post_plan_action`'s enum is declared as `["start_implementation"]` but `profiles.md:33` and `fast.yaml` use `"ask"` as well; add `"ask"` so the cycle widget has both named options.

## Scope

All changes live in one file: `/home/ddt/Work/aitasks/.aitask-scripts/settings/settings_app.py`.

The settings TUI already renders any key that appears in **all three** structures (`settings_app.py:2750-2812`, save path at `settings_app.py:2923-2974`). So adding a key in these three places is the complete change — no new widget classes required.

## Implementation

### 1. `PROFILE_SCHEMA` (around line 95–120)

Add five entries and fix `post_plan_action`:

```python
"post_plan_action": ("enum", ["start_implementation", "ask"]),  # was: ["start_implementation"]
...
"post_plan_action_for_child": ("enum", ["start_implementation", "ask"]),
...
"manual_verification_followup_mode": ("enum", ["ask", "never"]),
"review_default_modes": ("string", None),
"review_auto_continue": ("bool", None),
"qa_tier": ("enum", ["q", "s", "e"]),
```

### 2. `PROFILE_FIELD_INFO` (around line 163–320)

Add `(short, detailed)` tuples for the five new keys, modeling tone on existing entries. Drafts:

- `post_plan_action_for_child`:
  - Short: `"Override post_plan_action for child tasks only"`
  - Detailed: `"Same values as post_plan_action (start_implementation, ask), but only applies when the current task is a child. Takes priority over post_plan_action for child tasks. Omit to fall back to post_plan_action."`

- `manual_verification_followup_mode`:
  - Short: `"Post-commit manual-verification follow-up prompt: ask or never"`
  - Detailed: `"Controls task-workflow Step 8c.\n  'ask': prompt after commit to queue a manual-verification follow-up task\n  'never': skip the prompt entirely\n  (unset): same as 'ask'\nUseful to set to 'never' in non-interactive/remote profiles."`

- `review_default_modes`:
  - Short: `"Comma-separated review-guide names to auto-select"`
  - Detailed: `"Used by aitask-review Step 1b. When set, auto-selects these review guides instead of prompting. Values are mode names (the 'name' field from each review guide's frontmatter), comma-separated, e.g., 'code_conventions,security'."`

- `review_auto_continue`:
  - Short: `"Auto-continue to implementation in review mode"`
  - Detailed: `"Used by aitask-review. When true, automatically continues to the implementation phase after review finishes. When false or unset, asks the user. (default: false)"`

- `qa_tier`:
  - Short: `"QA analysis depth: q (quick), s (standard), e (exhaustive)"`
  - Detailed: `"Used by /aitask-qa Step 1c. When set, skips the tier selection prompt.\n  'q': Quick — existing tests + lint only\n  's': Standard — full analysis with test plan\n  'e': Exhaustive — full analysis + edge cases + verification gate\n  (unset): prompts the user"`

(The `post_plan_action` detailed text should also be updated to reflect that `"ask"` is now a selectable enum value alongside `start_implementation`.)

### 3. `PROFILE_FIELD_GROUPS` (around line 323–343)

Rearrange to place the new keys in sensible groups:

```python
PROFILE_FIELD_GROUPS: list[tuple[str, list[str]]] = [
    ("Identity", ["name", "description"]),
    ("Task Selection", ["skip_task_confirmation", "default_email"]),
    ("Branch & Worktree", ["create_worktree", "base_branch"]),
    ("Planning", [
        "plan_preference",
        "plan_preference_child",
        "plan_verification_required",
        "plan_verification_stale_after_hours",
        "post_plan_action",
        "post_plan_action_for_child",
    ]),
    ("Feedback", ["enableFeedbackQuestions"]),
    ("Post-Implementation", ["test_followup_task"]),
    ("Manual Verification", ["manual_verification_followup_mode"]),
    ("QA Analysis", ["qa_mode", "qa_run_tests", "qa_tier"]),
    ("Exploration", ["explore_auto_continue"]),
    ("Review", ["review_default_modes", "review_auto_continue"]),
    ("Lock Management", ["force_unlock_stale"]),
    ("Remote Workflow", [
        "done_task_action", "orphan_parent_action", "complexity_action",
        "review_action", "issue_action", "abort_plan_action", "abort_revert_status",
    ]),
]
```

## Critical files

- `.aitask-scripts/settings/settings_app.py` — all three schema structures live here; renderer at lines 2750-2812; save path at 2923-2974.
- `aitasks/metadata/profiles/fast.yaml`, `remote.yaml` — used to verify round-trip.

## Verification

1. **Syntax:** `python3 -m py_compile .aitask-scripts/settings/settings_app.py`
2. **Static check:** `grep -c 'manual_verification_followup_mode\|post_plan_action_for_child\|review_default_modes\|review_auto_continue\|qa_tier' .aitask-scripts/settings/settings_app.py` — expect ≥15 (each key in 3 places).
3. **Manual TUI check** (user needs to run; this is the real test):
   - `./ait settings` → Profiles tab → pick `fast` → confirm each new key is listed under its group with a CycleField/string/int widget.
   - Confirm existing values from `fast.yaml` render as current: `post_plan_action=ask`, `post_plan_action_for_child=ask`, `manual_verification_followup_mode=ask`, `qa_mode=ask`.
   - Change `manual_verification_followup_mode` from `ask` → `never`, Save, reopen — confirm YAML updated and still renders the new value.
   - Pick `remote` profile → confirm `manual_verification_followup_mode=never` renders correctly (regression check).
4. **Commit:** one commit, `feature: Surface remaining execution-profile keys in settings TUI (t611)`.

## Notes

- No new widget classes are needed — existing `CycleField` (enum/bool) and `ConfigRow` (string/int) handle every added key via the schema.
- The enum `("q", "s", "e")` for `qa_tier` matches the short codes written to the `tier` context variable in `.claude/skills/aitask-qa/SKILL.md:49-51`.
- Adding `"ask"` to `post_plan_action`'s enum doesn't change any behavior — an explicit `"ask"` already works at runtime (fast.yaml already has it); it just lets the cycle widget name it instead of forcing `(unset)`.
- Step 9 of task-workflow will verify build (none configured for this project beyond lint/tests — nothing to run here), then archive.

## Final Implementation Notes

- **Actual work done:**
  - `PROFILE_SCHEMA`: added `post_plan_action_for_child`, `manual_verification_followup_mode`, `review_default_modes`, `review_auto_continue`, `qa_tier`; updated `post_plan_action` enum to include `"ask"`.
  - `PROFILE_FIELD_INFO`: added short/detailed entries for the 5 new keys and extended `post_plan_action`'s detail to mention `"ask"`.
  - `PROFILE_FIELD_GROUPS`: added `post_plan_action_for_child` to Planning; introduced "Manual Verification" and "Review" groups; added `qa_tier` to "QA Analysis".
- **Deviations from plan:**
  - Mid-review the user asked whether `test_followup_task` was still used. Confirmed it was deprecated in favor of `/aitask-qa` (CLAUDE.md and `.claude/skills/aitask-qa/SKILL.md:118`), with no active reader in any skill or script. Scope expanded to also remove it from the settings TUI (all 3 structures) and from the seed profiles (`seed/profiles/fast.yaml`, `seed/profiles/remote.yaml`). As a consequence the original "Post-Implementation" group became empty and was dropped entirely.
- **Issues encountered:** None.
- **Key decisions:**
  - Removed the empty "Post-Implementation" group rather than leaving it as a header with no entries.
  - Did not touch the live profile YAMLs in `aitasks/metadata/profiles/` because they were already clean (no `test_followup_task` present).
  - Left the historical explanatory note in `aitask-qa/SKILL.md:118` ("formerly Step 8b … now deprecated") as-is; it's correct and serves as a breadcrumb.
