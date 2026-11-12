---
title: "Creating Tasks from Code"
linkTitle: "Creating Tasks from Code"
weight: 65
description: "Select lines in the code browser and create a task that points at them, optionally folding pending tasks about the same file into it."
depth: [intermediate]
---

When you spot a TODO, a design problem or a bug while reading a file, you can create a task that points at those lines without leaving the code browser. The task records them in its [`file_references`]({{< relref "/docs/development/task-format" >}}#frontmatter-fields) field, so the agent that implements it starts with that context, and the board can take you back to the code later.

## Create a task from the code browser

1. Run `ait codebrowser` and open the file.
2. Select the lines with **Shift+Up** / **Shift+Down** or by dragging with the mouse. Without a selection of at least two lines, the task references the whole file.
3. Press **n**. A dialog opens with a create command that already carries the reference, such as `--file-ref lib/auth.py:42-68`.
4. Optionally edit the command. Adding `--auto-merge` folds pending tasks that already reference the same file into the new one without asking (see step 6).
5. Choose **Run in terminal** on the **Direct** tab, or **Run in tmux** on the **Tmux** tab.
6. Walk through the usual create flow, which starts by listing the reference it was given, and finalize the task. If pending tasks (status `Ready` or `Editing`) already reference the same file, you are asked whether to fold them into the new task. Answer No to keep them separate; they are then listed as a warning.

The committed task carries `file_references: [lib/auth.py:42-68]`. Because it has a file reference, it also records the commit it was created at as its `premise_baseline`, so the [premise staleness check]({{< relref "/docs/workflows/premise-staleness" >}}) can tell you, when the task is picked, whether those files changed in the meantime.

The [codebrowser reference]({{< relref "/docs/tuis/codebrowser/reference" >}}#creating-a-task-from-the-viewer) lists which reference each selection produces, and [`ait create`]({{< relref "/docs/commands/task-management" >}}#folding-tasks-that-reference-the-same-files) describes which tasks are folded and what folding does to them.

## Open a task's code from the board

1. In `ait board`, press **Enter** on a task card to open Task Detail.
2. Move to the **File Refs** row with **Up** / **Down** or **Tab**, and press **Enter**. If the task has several references, pick one from the list.

The codebrowser in your project's tmux session shows the file at the referenced lines. This needs the project's tmux session to be running, though the board itself can run outside tmux; the [board reference]({{< relref "/docs/tuis/board/reference" >}}#opening-file-references) has the details.

## Do it from the command line

`ait create` and `ait update` take references as flags:

```bash
# Create a task from a line range and fold pending tasks that reference the same file
ait create --batch --commit \
    --name "rework_token_validation" --priority medium --effort medium \
    --type refactor --labels "auth,tech-debt" \
    --file-ref "lib/auth.py:42-68" \
    --auto-merge \
    --desc "Rework the token validation path"

# Several references, one of them with two ranges on the same file
ait create --batch --commit \
    --name "login_cleanup" \
    --file-ref "lib/login.py:10-20^89-100" \
    --file-ref "lib/auth.py:42-68" \
    --desc "Unify login edge cases"

# Add a reference to task 42 and remove an old one
ait update --batch 42 \
    --file-ref "lib/auth.py:100-150" \
    --remove-file-ref "lib/auth.py:42-68"
```

`--file-ref` is repeatable on both commands, and `--remove-file-ref` removes the entry that matches it exactly. Without `--auto-merge`, a batch create folds nothing: it lists the overlapping pending tasks as a warning.

To see which pending tasks already reference a file before you create one, run the `aitask_find_by_file.sh` script with the file's path; [Finding tasks by file reference]({{< relref "/docs/development/task-format" >}}#finding-tasks-by-file-reference) describes how to call it and what it prints.

## See also

- [Task Format]({{< relref "/docs/development/task-format" >}}#frontmatter-fields): the `file_references` syntax and the rest of the frontmatter schema
- [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}): the **n** key in context; the overview's [Creating Tasks from Code]({{< relref "/docs/tuis/codebrowser#creating-tasks-from-code" >}}) section walks through it
- [Board How-To]({{< relref "/docs/tuis/board/how-to#how-to-navigate-task-relationships" >}}): the File Refs row among the other relationship fields
- [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}): the skill that drives the interactive create flow
- [Follow-Up Tasks]({{< relref "/docs/workflows/follow-up-tasks" >}}): capturing tasks during implementation
