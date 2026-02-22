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

## How It Compares

| Scenario | Recommended skill |
|----------|-------------------|
| Changes already made, need to document them | [`/aitask-wrap`](../../skills/aitask-wrap/) |
| Know what to build, defining the task first | [`/aitask-create`](../../skills/aitask-create/) |
| Not sure what needs doing, want to explore first | [`/aitask-explore`](../../skills/aitask-explore/) |

## Tips

- **Wrap early** — The sooner you wrap after making changes, the fresher the context. Don't let uncommitted fixes pile up
- **Select files carefully** — If you have changes from multiple concerns, wrap them separately. Each invocation creates one task, so separating concerns keeps the history clean
- **Review the auto-analysis** — Claude's suggested intent and metadata are inferences from the diff. They're usually accurate but always worth a quick check before confirming
