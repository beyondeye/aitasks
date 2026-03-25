---
title: "Code Browser"
linkTitle: "Code Browser"
weight: 20
description: "TUI code viewer with syntax highlighting, task annotations, and explain integration"
---

The `ait codebrowser` command launches an interactive terminal-based code browser for exploring project files with task-aware annotations. Built with [Textual](https://textual.textualize.io/), it provides syntax-highlighted file viewing, a git-aware file tree, and an annotation gutter that maps lines of code to the aitasks that introduced them — powered by the [explain data pipeline]({{< relref "/docs/skills/aitask-explain" >}}).

{{< static-img src="imgs/aitasks_codebrowser.svg" alt="Code browser showing file tree and syntax-highlighted code viewer" caption="The ait codebrowser with file tree (left) and syntax-highlighted code viewer (right)" >}}

## Tutorial

### Launching the Code Browser

```bash
ait codebrowser
```

The browser detects the git project root, builds a file tree from git-tracked files, and cleans up stale explain data on startup.

**Requirements:** Python venv at `~/.aitask/venv/` with packages `textual` and `pyyaml` (installed by [`ait setup`]({{< relref "/docs/commands/setup-install" >}})). Falls back to system `python3` if the venv is not found.

### Understanding the Layout

The code browser has a three-panel layout:

1. **File tree** (left panel) — Shows git-tracked files in a directory tree. Excludes `__pycache__`, `node_modules`, and `.git` directories. The tree width adjusts based on terminal size.

2. **Code viewer** (center panel) — Displays the selected file with syntax highlighting (Monokai theme), line numbers, and an optional annotation gutter. An info bar at the top shows the filename, line count, cursor position, and annotation status.

3. **Detail pane** (right panel, hidden by default) — Shows the task or plan content for the annotation at the current cursor line. Toggle it with **d**.

4. **Footer** — Dynamic keybinding hints showing available actions.

### Browsing Files

Select a file in the tree to open it in the code viewer. Use **Tab** to cycle focus between the file tree, code viewer, and detail pane (if visible).

In the code viewer:
- **Up / Down** arrows move the cursor line by line
- **PageUp / PageDown** moves by a screen height
- **g** opens a go-to-line dialog — type a line number and press Enter
- Click anywhere in the code to position the cursor

### Understanding Annotations

{{< static-img src="imgs/aitasks_codebrowser_w_annotations.svg" alt="Code browser with annotation gutter showing color-coded task IDs" caption="The annotation gutter shows color-coded task IDs for each code section" >}}

When you open a file, the codebrowser automatically generates or loads cached [explain data]({{< relref "/docs/skills/aitask-explain" >}}) for the file's directory. This data maps line ranges to the aitasks that introduced or last modified them.

- The **annotation gutter** appears as a column in the code viewer, showing task IDs (e.g., `t130`, `t145`) color-coded for visual distinction
- The **info bar** shows the annotation timestamp, or "(generating...)" while data is being prepared
- Press **t** to toggle the annotation gutter on or off
- Press **r** to force-refresh annotations (regenerates explain data from git history)

Each unique task ID gets a color from a fixed palette (cyan, green, yellow, magenta, blue, red, bright cyan, bright green), cycling if there are more than 8 unique tasks.

### Using the Detail Pane

{{< static-img src="imgs/aitasks_codebrowser_w_annotaitions_w_details.svg" alt="Code browser with detail pane showing task content" caption="Full layout with the detail pane showing plan content for the annotated task at cursor" >}}

The detail pane provides context about the task annotating the current cursor line:

- Press **d** to toggle the detail pane. Press **D** to expand it to half the screen width.
- As you move the cursor, the pane updates to show the **plan content** (preferred) or **task description** for the task ID on the current line.
- When a selection spans lines annotated by multiple tasks, the pane shows a summary list of all task IDs in the selection.

### Viewing Completed Task History

{{< static-img src="imgs/codebrowser_task_history.svg" alt="History screen showing completed tasks list and task detail pane" caption="The completed tasks history screen with task list (left) and task details (right)" >}}

Press **h** to open the completed tasks history screen. This view lets you browse all archived tasks directly within the codebrowser, ordered by commit history (most recent first).

The history screen has a two-pane layout:

1. **Task list** (left pane) — Shows completed tasks in reverse-chronological order, grouped into chunks. A **Recently Opened** section at the top provides quick access to tasks you've viewed before (persistent across sessions). Scroll down and use "Load more" to fetch older tasks progressively.

2. **Task details** (right pane) — Displays full metadata for the selected task: issue type, priority, effort, labels, completion date, commit links, affected files, and issue/PR links. For child tasks, sibling tasks and child task lists are also shown.

Key capabilities:

- **Task/plan toggle:** Press **v** to switch between viewing the task description and its implementation plan
- **Commit links:** Focus a commit and press **Enter** to open it in your browser (requires a recognized git remote)
- **File navigation:** Focus an affected file and press **Enter** to return to the codebrowser with that file opened
- **Sibling browsing:** For child tasks, press **s** (or **Enter** on the sibling count field) to open a sibling picker modal
- **Label filtering:** Press **l** to filter the task list by labels
- **Pane navigation:** Use **Left** / **Right** arrows to move focus between panes, or **Tab** to cycle. The left arrow cycles between the task list and recently opened list
- **State preservation:** When you return to the codebrowser and press **h** again, the history screen restores your previous position — selected task, scroll position, loaded chunks, plan/task toggle, and label filter

Press **h** or **Escape** to return to the code browser.

### Launching an Explain Session

Press **e** to launch the configured code agent with the [`/aitask-explain`]({{< relref "/docs/skills/aitask-explain" >}}) skill targeting the current file. The code browser uses the [code agent wrapper]({{< relref "/docs/commands/codeagent" >}}) to resolve which agent and model to use for the `explain` operation. If you have a line selection active, the explain session focuses on that specific line range.

Before launching, the code browser performs a pre-flight check to verify the resolved agent binary is available in PATH. If the binary is not found, a notification appears instead of a failed launch.

A terminal emulator is opened automatically. If none is found, the codebrowser suspends and runs the agent in the current terminal.

This is useful when you want a deeper, conversational explanation of a code section — the codebrowser provides the visual overview, and `/aitask-explain` provides the detailed narrative.

---

**See also:**
- [`/aitask-explain`]({{< relref "/docs/skills/aitask-explain" >}}) — The skill that generates annotation data and provides conversational code explanations
- [Understanding Code with Explain]({{< relref "/docs/workflows/explain" >}}) — Workflow guide covering use cases and the cognitive debt framing
- [`ait explain-runs` and `ait explain-cleanup`]({{< relref "/docs/commands/explain" >}}) — Commands for managing explain run data
- [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) — Configures which agent and model the code browser uses for explain sessions

---

**Next:** [Workflow Guides]({{< relref "/docs/workflows" >}})
