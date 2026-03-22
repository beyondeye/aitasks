---
Task: t426_6_documentation_updates.md
Parent Task: aitasks/t426_default_execution_profiles.md
Sibling Tasks: aitasks/t426/t426_1_*.md, aitasks/t426/t426_2_*.md, aitasks/t426/t426_3_*.md, aitasks/t426/t426_4_*.md, aitasks/t426/t426_5_*.md
Archived Sibling Plans: aiplans/archived/p426/p426_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t426_6 — Documentation Updates

## Context

All implementation is done (t426_1 through t426_5). This task updates documentation to reflect the new `default_profiles` config, `--profile` argument, and the updated profile selection behavior.

## Steps

### 1. Update `profiles.md` — Profile Schema Reference

**File:** `.claude/skills/task-workflow/profiles.md`

Add two new sections:

**A. "Default Profile Configuration" section** (after the existing schema documentation):

```markdown
## Default Profile Configuration

Set a default execution profile per skill in `project_config.yaml` (team-wide) or `userconfig.yaml` (personal override):

\```yaml
# project_config.yaml (shared with team)
default_profiles:
  pick: fast
  review: default

# userconfig.yaml (personal, gitignored)
default_profiles:
  pick: default   # overrides team's "fast"
\```

Valid skill names: `pick`, `fold`, `review`, `pr-import`, `revert`, `explore`, `pickrem`, `pickweb`.

Values are profile names (without `.yaml` extension) matching the `name` field in profile YAML files.
```

**B. "Profile Override Argument" section:**

```markdown
## Profile Override Argument

All skills that support profiles accept an optional `--profile <name>` argument:

\```
/aitask-pick --profile fast
/aitask-pick 42 --profile fast
/aitask-fold --profile fast 106,108
/aitask-review --profile default
/aitask-pickrem 42 --profile remote
\```

### Resolution Order

1. `--profile <name>` argument (highest priority)
2. `userconfig.yaml` → `default_profiles.<skill>` (personal)
3. `project_config.yaml` → `default_profiles.<skill>` (team)
4. Interactive selection / auto-select (fallback)
```

### 2. Update Website Settings Docs

**File:** `website/content/docs/tuis/settings/reference.md`

Add `default_profiles` to the Project Config section, documenting the key name, type (dict), and purpose.

**File:** `website/content/docs/tuis/settings/how-to.md`

Add a how-to section: "Set default execution profiles" with step-by-step guide using the TUI or direct YAML editing.

### 3. Update Website Execution Profiles Page

**File:** Check if `website/content/docs/skills/aitask-pick/execution-profiles.md` exists. If so, add Default Profiles and Override sections. If the execution profiles documentation lives elsewhere, find and update it.

### 4. Add `--profile` notes to skill Notes sections

For each of the 8 skills, add a brief note in the Notes section at the end of SKILL.md:

```markdown
- **Profile override:** Use `--profile <name>` to override profile selection. Default profiles can be configured in `project_config.yaml` or `userconfig.yaml`. See `profiles.md` for details.
```

### 5. Verify

- Build website: `cd website && hugo build --gc --minify` — verify no broken links
- Read through all updated docs for consistency
- Verify resolution order is documented consistently across all locations

## Files to Modify

- `.claude/skills/task-workflow/profiles.md`
- `website/content/docs/tuis/settings/reference.md`
- `website/content/docs/tuis/settings/how-to.md`
- Website execution profiles page (find exact path)
- 8 skill SKILL.md Notes sections (`.claude/skills/aitask-{pick,fold,review,pr-import,revert,explore,pickrem,pickweb}/SKILL.md`)

## Reference Files

- `.claude/skills/task-workflow/execution-profile-selection.md` — updated procedure (from t426_2)
- `seed/project_config.yaml` — config documentation (from t426_1)

## Final Implementation Notes
- **Actual work done:** Updated 4 documentation files: `profiles.md` (added Default Profile Configuration and Profile Override Argument sections with ToC), `reference.md` (added `default_profiles` to Project Config Keys table), `how-to.md` (added Set Default Execution Profiles section with TUI/YAML/override instructions), `execution-profiles.md` (added default profiles and override sections with resolution order). Skipped Step 4 (skill Notes sections) — all 9 skills already had `--profile` notes from t426_3/t426_4.
- **Deviations from plan:** Added `qa` to valid skill names list in all locations (9 skills total, consistent with t426_1). Added mention of Settings TUI profile picker in profiles.md and execution-profiles.md (reflecting t426_5's per-skill picker UI). Step 4 entirely skipped — verification showed it was already complete.
- **Issues encountered:** None. Website builds cleanly (115 pages, no errors).
- **Key decisions:** Kept resolution order documentation consistent across all 4 files: `--profile` → `userconfig.yaml` → `project_config.yaml` → interactive/auto-select. Included both TUI and YAML approaches in how-to.md for completeness.
- **Notes for sibling tasks:** This was the final child task. All documentation is now in sync with the implementation from t426_1 through t426_5. The `qa` skill is included in all valid skill name lists.
