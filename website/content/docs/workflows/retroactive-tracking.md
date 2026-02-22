---
title: "Retroactive Change Tracking"
linkTitle: "Retroactive Tracking"
weight: 15
description: "Wrap ad-hoc changes into the aitasks framework after the fact"
---

Not every change starts with a task. Quick fixes get applied directly, debugging sessions turn into real improvements, config changes happen on the fly, and pair programming sessions accumulate changes without formal tracking. The [`/aitask-wrap`](../../skills/aitask-wrap/) skill retroactively integrates these changes into the aitasks framework so nothing falls through the cracks.

**The philosophy: never lose traceability, even for unplanned work.**

## When You Need This

- **Quick fixes applied directly** — You spotted a bug during code review and fixed it in 30 seconds. It's uncommitted, untracked, and will be lost in the noise if not documented
- **Debugging that became an improvement** — You started investigating an issue, found the root cause, and fixed it — but never created a task because you weren't sure it would lead anywhere
- **Config or dependency changes** — Updated a package version, tweaked a build setting, or adjusted environment config outside the normal task flow
- **Pair programming or live-coding** — Changes accumulated during a collaborative session without task tracking

## Walkthrough: Wrapping a Quick Fix

You fixed a shell quoting bug in `aitask_ls.sh` while working on something else. The fix is uncommitted and you want to document it properly.

**1. Launch the skill**

```
/aitask-wrap
```

Claude detects the uncommitted changes and shows a summary (files changed, insertions, deletions).

**2. Select files**

You're asked whether to include all changes or select specific files. Since you also have unrelated work-in-progress files, select "Let me select" and pick only the `aitask_ls.sh` change.

**3. Review the analysis**

Claude reads the diff and presents its analysis:
- **Task name:** `fix_ls_quoting_bug`
- **Issue type:** `bug`
- **Summary:** Fixed unquoted variable expansion in `aitask_ls.sh` that caused incorrect output when task names contained spaces

You confirm the analysis looks correct.

**4. Execute**

After final confirmation, everything runs automatically: task file is created, plan file documents the changes, code is committed with proper format (`bug: Fix ls quoting bug (t42)`), and both are archived and pushed.

The change now has the same traceability as any planned task — it appears in changelogs, can be linked to issues, and is searchable in the archive.

## Walkthrough: Debugging That Became a Fix

You were investigating intermittent test failures in the CI pipeline. After tracing the issue, you found and fixed a race condition in `aitask_lock.sh` — and added a regression test. But you never created a task because the investigation started as a "let me just check something" moment.

Now you have two changed files: the lock script fix and a new test file.

**1. Launch and select files**

```
/aitask-wrap
```

Claude detects changes to `aiscripts/lib/aitask_lock.sh` and a new `tests/test_lock_race.sh`. Since both files are part of the same fix, select "Include all changes."

**2. Review the analysis**

Claude reads the diff — a guard clause added to prevent concurrent lock acquisition, plus a test that simulates parallel lock attempts. The analysis:
- **Task name:** `fix_lock_race_condition`
- **Issue type:** `bug`
- **Priority:** `high` (inferred from the fix touching a shared utility)
- **Summary:** Fixed race condition in lock acquisition where two processes could obtain the same lock simultaneously. Added regression test.

The analysis captures both the fix and the test. You confirm.

**3. Execute**

Commit message: `bug: Fix lock race condition (t43)`. Task and plan archived. The investigation that "wasn't supposed to be a task" now has a full paper trail — the plan file documents what the race condition was, how it was fixed, and that a test covers it.

## Walkthrough: Config and Dependency Changes

You updated Hugo from 0.155 to 0.158, bumped the Docsy theme module, and adjusted a deprecated config key in `hugo.toml`. Three files changed, all related to the same maintenance activity.

**1. Launch the skill**

```
/aitask-wrap
```

Claude detects changes in `website/go.mod`, `website/go.sum`, and `website/hugo.toml`.

**2. Review the analysis**

Claude recognizes the pattern — version bumps in dependency files and a config adjustment:
- **Task name:** `update_hugo_and_docsy`
- **Issue type:** `chore`
- **Priority:** `low`
- **Effort:** `low`
- **Summary:** Updated Hugo to 0.158 and Docsy module to latest. Replaced deprecated `googleAnalytics` config key with the `services.googleAnalytics` section.

All three files are clearly part of the same concern, so the grouping is correct.

**3. Execute**

Commit message: `chore: Update Hugo and Docsy (t44)`. The dependency update is now documented with the exact versions changed and the config migration noted in the plan file — useful context if something breaks after the upgrade.

**Key point:** Config and dependency changes lose context fast. A week later, you won't remember why you bumped a version or what config key you migrated. Wrapping captures that context while it's fresh.

## Walkthrough: Pair Programming Session

After a two-hour pairing session, you have changes across six files — a new board column filter feature spanning the Python TUI, shell scripts, and board config. The changes work but were never tracked.

**1. Launch and assess scope**

```
/aitask-wrap
```

Claude shows 6 modified files with 120 insertions and 15 deletions. Before including everything, consider: are all changes part of the same logical feature? In this case, yes — the column filter touches the board UI, the config schema, and the CLI integration.

If the session had produced unrelated changes (say, a typo fix in a README alongside the feature), you'd want to wrap them separately — select files for the feature first, wrap that, then wrap the typo fix in a second invocation.

**2. Review the analysis**

With a larger diff, Claude's analysis is more detailed:
- **Task name:** `add_board_column_filter`
- **Issue type:** `feature`
- **Priority:** `medium`
- **Effort:** `medium`
- **Labels:** `[ui, board]`
- **Summary:** Added column-based filtering to the board TUI, allowing users to show/hide columns. Includes config persistence in `board_config.json` and CLI flag `--columns`.

Review the suggested metadata carefully. For a multi-file feature, Claude's inferences are usually good but the task name or labels might need adjustment. You can select "Adjust metadata" to refine before proceeding.

**3. Execute**

Commit message: `feature: Add board column filter (t45)`. Six files committed as a single logical change. The archived plan file documents the full scope — which files were changed, what the feature does, and how the pieces connect. Anyone reviewing the git history later can trace the commit back to a complete task record.

## Wrap vs. Create: When to Use Which

The core distinction: **wrap documents work already done; create plans work before it starts.**

| | `/aitask-wrap` | `/aitask-create` |
|---|---|---|
| **Starting point** | Uncommitted code changes | An idea or requirement |
| **Direction** | Code → task documentation | Task definition → code |
| **When** | After the work is done | Before the work begins |
| **Output** | Task + plan + commit + archive (all at once) | Task file (implementation follows later) |
| **Best for** | Ad-hoc fixes, maintenance, exploratory work | Planned features, known bugs, deliberate work |

**Decision guide:**
- Code changes already exist in your working tree → **wrap**
- You know what to build but haven't started → **create**
- You're not sure what needs doing → [**explore**](../../skills/aitask-explore/) first, then create

Both workflows produce the same artifacts (task file, plan file, properly formatted commits, archived records). The difference is timing — wrap creates documentation after the fact, while create establishes it upfront.

## Tips

- **Wrap early** — The sooner you wrap after making changes, the fresher the context. Don't let uncommitted fixes pile up
- **One concern per wrap** — Each invocation creates one task. If you have changes spanning unrelated concerns (a bug fix and a config tweak), wrap them separately to keep the history clean
- **Review the auto-analysis** — Claude's suggested intent and metadata are inferences from the diff. They're usually accurate but always worth a quick check before confirming
- **Check the archived plan** — After wrapping, the plan file is archived alongside the task. It contains a detailed record of what changed and why — useful for changelogs, code reviews, or when you need to understand a past change
- **Mix workflows freely** — Wrap and create are complementary. A typical session might start with `/aitask-pick` for planned work, then end with `/aitask-wrap` to capture a quick fix discovered along the way
