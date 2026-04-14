---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [task_workflow, aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-14 16:11
updated_at: 2026-04-14 17:07
completed_at: 2026-04-14 17:07
---

## Context

Parent task t547 extends execution profiles with plan verification tracking. This child adds two new profile keys and documents them in the canonical schema. No code changes — pure config + documentation.

Both keys apply uniformly to parent and child tasks (no `_child` variants, per user decision).

## Key Files to Modify

- `.claude/skills/task-workflow/profiles.md` — add 2 new keys to the schema table
- `aitasks/metadata/profiles/fast.yaml` — set the new keys explicitly (matches defaults, but explicit for clarity)

## Reference Files for Patterns

- `.claude/skills/task-workflow/profiles.md` — the schema table near the top is the canonical profile key reference. Note existing keys like `plan_preference`, `plan_preference_child`, `post_plan_action` for naming conventions and column formatting.
- `aitasks/metadata/profiles/fast.yaml` — current schema. The new keys are added at the end of the plan-related section.
- `aitasks/metadata/profiles/default.yaml` — minimal profile to verify it remains unchanged
- `aitasks/metadata/profiles/remote.yaml` — must remain unchanged (uses `use_current`, not `verify`)
- `.aitask-scripts/aitask_scan_profiles.sh` — profile parser that only reads `name` and `description`, so new keys don't require parser changes. Must still parse cleanly.

## Implementation Plan

### Step 1: Add keys to `profiles.md` schema table

Locate the profile key table in `.claude/skills/task-workflow/profiles.md`. Add two new rows:

| Key | Type | Required | Values | Step |
|-----|------|----------|--------|------|
| `plan_verification_required` | int | no | Positive integer; default `1` | Step 6.0 |
| `plan_verification_stale_after_hours` | int | no | Positive integer; default `24` | Step 6.0 |

Add a short description paragraph below the table explaining:

- `plan_verification_required`: Number of fresh (non-stale) `plan_verified` entries that must exist in a plan file for the verify path to SKIP re-verification. Only consulted when `plan_preference` (or `plan_preference_child`) is `"verify"`.
- `plan_verification_stale_after_hours`: Age (in hours) after which a `plan_verified` entry is considered stale and no longer counts toward the required fresh count.

Mention that both keys apply uniformly — no `_child` variants.

### Step 2: Update `fast.yaml`

Add the two new keys to `aitasks/metadata/profiles/fast.yaml`, near the existing plan-related settings:

```yaml
plan_preference: use_current
plan_preference_child: verify
plan_verification_required: 1
plan_verification_stale_after_hours: 24
```

These match the defaults but are explicit for clarity.

### Step 3: Verify other profiles unchanged

- `aitasks/metadata/profiles/default.yaml` — no changes
- `aitasks/metadata/profiles/remote.yaml` — no changes

### Step 4: Sanity check scanner

Run `./.aitask-scripts/aitask_scan_profiles.sh`. Output must still list all 3 profiles with correct names/descriptions — unknown keys should be harmlessly ignored.

## Verification Steps

1. Run: `./.aitask-scripts/aitask_scan_profiles.sh` — expect 3 PROFILE lines (default, fast, remote), no INVALID lines
2. Visually verify `profiles.md` renders cleanly (table aligns)
3. Run: `cat aitasks/metadata/profiles/fast.yaml | head -20` — visually verify the new keys are present
4. Run: `diff <(git show HEAD~1:aitasks/metadata/profiles/default.yaml) aitasks/metadata/profiles/default.yaml` — expect no output (unchanged)
5. Run: `diff <(git show HEAD~1:aitasks/metadata/profiles/remote.yaml) aitasks/metadata/profiles/remote.yaml` — expect no output (unchanged)

## Notes for sibling tasks

Child 3 (workflow integration) reads these profile keys with the standard profile-loading pattern. The canonical key names are `plan_verification_required` and `plan_verification_stale_after_hours` — Child 3 must use these exact names.

Parallel-safe with Child 1 (`--no-sibling-dep`): this child only touches config/docs; Child 1 only touches the helper script. No ordering dependency.
