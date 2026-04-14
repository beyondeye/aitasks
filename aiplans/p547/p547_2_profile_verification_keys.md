---
Task: t547_2_profile_verification_keys.md
Parent Task: aitasks/t547_plan_verify_on_off_in_task_workflow.md
Sibling Tasks: aitasks/t547/t547_*_*.md
Archived Sibling Plans: aiplans/archived/p547/p547_*_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified: []
---

# Context

This child extends the canonical execution profile schema with two new keys that drive the verify-decision logic introduced by parent task t547. Pure config + documentation — no code changes.

Parallel-safe with Child 1 (`--no-sibling-dep` on creation). Child 3 depends on this and on Child 1.

Both keys apply uniformly to parent and child tasks — no `_child` variants, per user decision.

# Files to modify

| File | Change |
|---|---|
| `.claude/skills/task-workflow/profiles.md` | Add 2 rows to the schema table + descriptive paragraph |
| `aitasks/metadata/profiles/fast.yaml` | Add the 2 keys set to default values (explicit for clarity) |

**NOT modified:**
- `aitasks/metadata/profiles/default.yaml` (remains minimal)
- `aitasks/metadata/profiles/remote.yaml` (uses `use_current`, not affected)
- `.aitask-scripts/aitask_scan_profiles.sh` (only reads `name`/`description`, new keys ignored)

# Detailed changes

## `profiles.md` schema table

Add the following rows in the appropriate position in the schema table (near the existing `plan_preference` / `plan_preference_child` rows):

| Key | Type | Required | Values | Step |
|-----|------|----------|--------|------|
| `plan_verification_required` | int | no | Positive integer; default `1` | Step 6.0 |
| `plan_verification_stale_after_hours` | int | no | Positive integer; default `24` | Step 6.0 |

## `profiles.md` descriptive paragraph

Add this paragraph after the schema table, in the section describing plan-related keys:

> **Plan verification tracking (`plan_verification_required`, `plan_verification_stale_after_hours`):** When `plan_preference` (or `plan_preference_child`) is `"verify"`, the workflow consults the plan file's `plan_verified` metadata list to decide whether a fresh verification is actually needed. `plan_verification_required` is the number of fresh (non-stale) entries required to skip re-verification — default `1` means a single prior verification is sufficient. `plan_verification_stale_after_hours` is how old (in hours) an entry may be before it no longer counts as fresh — default `24`. Both keys apply uniformly to parent and child tasks — there are no `_child` variants. The actual decision (skip / verify / ask) is computed by `./.aitask-scripts/aitask_plan_verified.sh decide`, which returns a structured report the workflow parses directly.

## `fast.yaml` update

Current `fast.yaml` (from Step 0 of this pick) has:

```yaml
plan_preference: use_current
plan_preference_child: verify
```

Add the two new keys right after these, maintaining alphabetical/grouped ordering:

```yaml
plan_preference: use_current
plan_preference_child: verify
plan_verification_required: 1
plan_verification_stale_after_hours: 24
```

These values match the defaults, but are set explicitly so readers of `fast.yaml` see the intent without cross-referencing `profiles.md`.

## No changes to `default.yaml` / `remote.yaml`

Verify they are byte-identical to pre-task state:

```bash
git diff HEAD -- aitasks/metadata/profiles/default.yaml aitasks/metadata/profiles/remote.yaml
```

Expected: no output.

# Verification

1. `./.aitask-scripts/aitask_scan_profiles.sh` — must list 3 profiles (default, fast, remote) with no INVALID entries
2. `grep -n 'plan_verification_required\|plan_verification_stale_after_hours' .claude/skills/task-workflow/profiles.md` — confirm both keys documented
3. `cat aitasks/metadata/profiles/fast.yaml` — visually verify the 2 new keys present with correct values
4. `git diff HEAD -- aitasks/metadata/profiles/default.yaml aitasks/metadata/profiles/remote.yaml` — no output
5. `shellcheck` not applicable (no bash changes)

# Notes for sibling tasks

Child 3 reads these profile keys via the standard profile-loading pattern. The canonical key names are `plan_verification_required` and `plan_verification_stale_after_hours` — Child 3 must use these exact names.

Defaults (`1` and `24`) live in the helper script (Child 1) AND in the `profiles.md` documentation. When Child 3 reads the profile, if the key is absent it should fall back to the defaults documented here. Child 1's `decide` subcommand requires the values as explicit arguments — it does not assume defaults, so Child 3 must pass them.
