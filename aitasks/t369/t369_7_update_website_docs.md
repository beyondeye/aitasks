---
priority: low
effort: low
depends: [t369_6]
issue_type: documentation
status: Ready
labels: [aitask_explain, documentation]
created_at: 2026-03-11 18:34
updated_at: 2026-03-11 18:34
---

Document gather_explain_context profile field and historical context feature in the website. Update settings/reference.md profile schema table, aitask-pick skill page, and settings overview if needed.

## Context

The website documentation needs to reflect the new `gather_explain_context` profile field and the historical context gathering feature. The website is built with Hugo/Docsy and lives in the `website/` directory. The two key pages to update are the settings reference (which has the profile schema table) and the aitask-pick skill page (which describes the pick workflow steps).

## Key Files to Modify

- **`website/content/docs/tuis/settings/reference.md`** -- Add `gather_explain_context` to the Profile Schema table in the Planning section (around line 95-99).
- **`website/content/docs/skills/aitask-pick/_index.md`** -- Add mention of historical context gathering in the step-by-step workflow description and the Key Capabilities section.

## Reference Files for Patterns

- **`website/content/docs/tuis/settings/reference.md`** -- The existing profile schema tables. Follow the same `| Key | Type | Options | Description |` format used in the Planning section. Currently has `plan_preference`, `plan_preference_child`, `post_plan_action`.
- **`website/content/docs/skills/aitask-pick/_index.md`** -- The existing step-by-step list (numbered 1-10). The historical context feature is part of step 7 (Planning). Also look at the Key Capabilities section for the bullet format.

## Implementation Plan

### Step 1: Update `website/content/docs/tuis/settings/reference.md`

In the Planning section of the Profile Schema (around line 95-99), add a new row to the table:

```markdown
| `gather_explain_context` | int or enum | `ask`, `0`, `1`, `2`, `3`, `5` | Number of historical plans to extract during planning. `ask` = prompt user, `0` = disabled, `N` = max plans |
```

Insert it after the `post_plan_action` row.

### Step 2: Update `website/content/docs/skills/aitask-pick/_index.md`

**In the Step-by-Step section**, update step 7 (Planning) to mention historical context:

Current text (line ~29):
```
7. **Planning** -- Enters the agent planning flow to explore the codebase and create an implementation plan. ...
```

Add mention of historical context gathering:
```
7. **Planning** -- Enters the agent planning flow to explore the codebase and create an implementation plan. Optionally gathers historical architectural context from aitask-explain data showing why existing code was designed the way it is. If a plan already exists, offers three options: ...
```

**In the Key Capabilities section**, add a new bullet:

```markdown
- **Historical context** -- During planning, optionally extracts historical plan content from the aitask-explain data to show WHY existing code was designed a certain way. Controlled by the `gather_explain_context` profile key (0 = disabled, N = max plans, ask = prompt). Plans are selected by code contribution (git blame line count) and deduplicated across files
```

### Step 3: Check if `website/content/docs/tuis/settings/_index.md` needs updating

Read this file to see if it lists specific profile fields. If it does, add `gather_explain_context`. If it only provides a general overview, no changes needed.

### Step 4: Check if execution profiles page needs updating

Check if `website/content/docs/skills/aitask-pick/execution-profiles/` has its own profile schema listing. If so, update it too.

## Verification Steps

1. **Build test**: Run `cd website && hugo build --gc --minify` and verify no build errors.
2. **Visual check**: Run `cd website && ./serve.sh` and visit the settings reference page -- verify the new row appears correctly in the Planning table.
3. **Verify aitask-pick page**: Navigate to the aitask-pick skill page and verify the historical context mentions are well-integrated.
4. **Link check**: Ensure any new internal links resolve correctly.
