---
title: "Retroactive Change Tracking"
linkTitle: "Retroactive Tracking"
weight: 15
description: "Wrap ad-hoc changes into the aitasks framework after the fact"
depth: [intermediate]
---

When you have changed code without a task, [`/aitask-wrap`]({{< relref "/docs/skills/aitask-wrap" >}}) turns the uncommitted changes into a task, a plan and a commit, then archives them. The change ends up as traceable as planned work: it appears in changelogs and in the task archive like any other task.

## Wrap your changes

1. Run `/aitask-wrap` from the project root. It lists the uncommitted changes (staged, unstaged and untracked files) with the number of files, insertions and deletions. If there are none, it stops.
2. Choose the files. **All changes** includes everything; **Let me select** lets you pick files, so unrelated work in progress stays out of the wrap.
3. Review the analysis. The skill reads the diff and proposes a task name, issue type, priority, effort and labels, a task summary, a plan summary and the commit message. Choose **Adjust task name or metadata** or **Adjust descriptions** to change any of them, then **Looks good**.
4. Confirm. The skill shows what it will create and asks once more: **Yes, proceed**, **Go back** to the analysis, or **Abort** to stop with nothing changed.
5. The skill runs the rest without further questions. It creates the task file and a plan file recording what changed and the probable intent, commits the selected files with a message of the form `<type>: <description> (t<N>)` (for example `bug: Fix session expiry check (t42)`), archives the task and plan, and pushes.

## When you need it

- A quick fix made while working on something else, such as a one-line change to `src/auth/session.py`: choose **Let me select** and pick only the fix, so your other edits stay uncommitted.
- A debugging session that ended in a fix, such as a change to `src/auth/session.py` plus a regression test in `tests/test_session.py`: choose **All changes**, so the task and its plan record the fix and the test together.
- A dependency or config change, such as a version bump in `package.json` and its lock file: check that the plan summary names the old and new versions and any config key you renamed, and add them with **Adjust descriptions** if not, so the task records why the version moved.
- A pair-programming or live-coding session across several files: if the session produced unrelated changes, select the files of the main change first, then run `/aitask-wrap` again for the rest. On a larger diff, check the suggested task name and labels before confirming.

## Wrap vs. Create: When to Use Which

| | `/aitask-wrap` | `/aitask-create` |
|---|---|---|
| **Starting point** | Uncommitted code changes | An idea or requirement |
| **Direction** | Code → task documentation | Task definition → code |
| **When** | After the work is done | Before the work begins |
| **Output** | Task + plan + commit + archive (all at once) | Task file (implementation follows later) |
| **Best for** | Ad-hoc fixes, maintenance, exploratory work | Planned features, known bugs, deliberate work |

If you are not sure yet what needs doing, start with [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) and create the task from there.

## Tips

- Wrap one concern at a time. Each wrap creates one task, so wrap unrelated changes, such as a bug fix and a config tweak, separately to keep the history clean.
- Wrap soon after making the changes, while you still remember why you made them, and before uncommitted fixes pile up.
- The type, metadata and descriptions are inferred from the diff, so read them before confirming.
- The archived plan records which files changed and why. Read it when you review the change or come back to it later; [`/aitask-changelog`]({{< relref "/docs/skills/aitask-changelog" >}}) also reads it when it drafts a release entry.
- A session can start with `/aitask-pick` for planned work and end with `/aitask-wrap` for a fix found along the way.

---

**Next:** [Task Decomposition]({{< relref "/docs/workflows/task-decomposition" >}}): breaking complex tasks into manageable child subtasks.
