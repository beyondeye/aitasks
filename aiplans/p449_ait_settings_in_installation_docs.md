---
Task: t449_ait_settings_in_installation_docs.md
Worktree: (none - worked on current branch)
Branch: main
Base branch: main
---

# Plan: Add ait settings reference to getting started docs (t449)

## Context

The `ait settings` TUI is a centralized configuration interface that lets users manage agent defaults, board settings, project config, models, and execution profiles. Its documentation exists at `docs/tuis/settings/` but is not referenced from the getting-started page, making it easy to miss during initial setup. Additionally, the operation descriptions in the settings TUI code don't mention where these defaults are actually used (Board TUI, Code Browser TUI).

## Changes

### 1. Add settings section to Getting Started page

**File:** `website/content/docs/getting-started.md`

Add a new step 2 "Review Settings" between current step 1 (Install) and step 2 (Create). Renumber subsequent steps (3→Create, 4→Board, 5→Pick, 6→Iterate).

New section content:

```markdown
## 2. Review Settings

After setup, review and configure framework settings with the interactive TUI:

` ``bash
ait settings
` ``

The Settings TUI provides centralized management of:

- **Agent Defaults** — Which code agent and model is used when launching tasks from the [Board](tuis/board/) TUI and when running explain from the [Code Browser](tuis/codebrowser/) TUI
- **Board** — Auto-refresh interval and sync behavior
- **Project Config** — Build verification commands, test/lint commands, co-author email domain
- **Models** — Browse available models and their verified performance scores
- **Execution Profiles** — Pre-configured answers to workflow prompts (e.g., skip confirmations, auto-create worktrees)

We recommend reviewing settings early — they affect how the Board and Code Browser TUIs invoke code agents and which models are used. See the [Settings documentation](tuis/settings/) for details.
```

### 2. Update operation descriptions in Settings TUI Python code

**File:** `.aitask-scripts/settings/settings_app.py` (lines 115-119)

Update `OPERATION_DESCRIPTIONS` dict to mention where each default is used:

```python
OPERATION_DESCRIPTIONS: dict[str, str] = {
    "pick": "Model used for picking and implementing tasks (used when launching tasks from the Board TUI)",
    "explain": "Model used for explaining/documenting code (used when running explain from the Code Browser TUI)",
    "batch-review": "Model used for batch code review operations",
    "raw": "Model used for direct/ad-hoc code agent invocations (passthrough mode)",
    ...
}
```

### 3. Update Agent Defaults description in Settings TUI docs

**File:** `website/content/docs/tuis/settings/_index.md` (line 24)

Add context about where these defaults are used:

Change:
```
Shows the default agent/model for each operation (`task-pick`, `explain`, `batch-review`, `raw`). Each entry displays:
```
To:
```
Shows the default agent/model for each operation (`task-pick`, `explain`, `batch-review`, `raw`). These defaults are used when launching tasks from the [Board]({{< relref "/docs/tuis/board" >}}) TUI and running explain from the [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) TUI. Each entry displays:
```

## Files to modify

- `website/content/docs/getting-started.md` — Add new "Review Settings" section, renumber steps
- `.aitask-scripts/settings/settings_app.py` — Update `pick` and `explain` operation descriptions
- `website/content/docs/tuis/settings/_index.md` — Clarify Agent Defaults description with Board/Code Browser context

## Post-Review Changes

### Change Request 1 (2026-03-24)
- **Requested by user:** Settings doc link in getting-started page is broken
- **Changes made:** Fixed relative links — changed `tuis/settings/`, `tuis/board/`, `tuis/codebrowser/` to `../tuis/settings/`, `../tuis/board/`, `../tuis/codebrowser/` (getting-started.md is at docs/ level, needs `../` to reach sibling dirs)
- **Files affected:** `website/content/docs/getting-started.md`

## Final Implementation Notes
- **Actual work done:** Added "Review Settings" section to getting-started.md (new step 2, renumbered subsequent steps), updated OPERATION_DESCRIPTIONS in settings_app.py to mention Board/Code Browser TUI context, updated settings docs _index.md Agent Defaults description
- **Deviations from plan:** No installation page changes (user clarified only getting-started page needed). Initial relative links were wrong (missing `../` prefix) — fixed in post-review.
- **Issues encountered:** Hugo relative links from `docs/getting-started.md` to `docs/tuis/settings/` require `../` prefix since getting-started.md is a page at the docs level, not in a subdirectory
- **Key decisions:** Used `../` relative links consistent with existing link patterns in the file (e.g., line 68's `../tuis/board/`)

## Verification

1. Run `cd website && hugo build --gc --minify` to verify the site builds without errors
2. Check that the relative links resolve correctly
