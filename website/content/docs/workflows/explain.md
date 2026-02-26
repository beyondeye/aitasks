---
title: "Understanding Code with Explain"
linkTitle: "Explain"
weight: 85
description: "Use code evolution history to rebuild understanding of why code exists"
---

When AI agents accelerate development, teams can ship features faster than they can understand them. Code that works perfectly may still be opaque — nobody knows why it exists, which task motivated it, or how its design evolved. This gap between code velocity and code comprehension is what Margaret Storey calls [cognitive debt](https://margaretstorey.com/blog/2026/02/09/cognitive-debt/): "the debt compounded from going fast lives in the brains of the developers." The [`/aitask-explain`](../../skills/aitask-explain/) skill addresses this by tracing code back through the aitask and aiplan records that document every change's purpose.

**The key insight: technical debt lives in the code; cognitive debt lives in developers' understanding. The aitasks framework addresses both because it stores structured records that capture the "why" behind every change.**

## Cognitive Debt vs Technical Debt

**Technical debt** is about problems in the code itself: missing error handling, duplicated logic, unoptimized patterns, security gaps. It accumulates when teams take shortcuts in implementation. The tool for this is [`/aitask-review`](../../skills/aitask-review/), which systematically reviews code against quality standards and creates tasks from findings.

**Cognitive debt** is about problems in developer understanding: nobody knows why a module was structured this way, which edge case prompted a specific guard clause, or how the architecture evolved from its original design. It accumulates when teams — or AI agents — ship changes faster than they build comprehension. The tool for this is [`/aitask-explain`](../../skills/aitask-explain/), which traces code history through structured task and plan records.

The aitasks framework is well-positioned to address cognitive debt because every change made through [`/aitask-pick`](../../skills/aitask-pick/) creates a task file (with description and metadata) and a plan file (with implementation notes, design decisions, and post-implementation feedback). These records persist in the git history even after archival, and `/aitask-explain` harvests them to reconstruct the narrative of why code exists.

## When to Use Explain

- **Understanding AI-generated code** — When an AI agent implemented a feature over several tasks and you need to understand why specific patterns were chosen. The code evolution mode traces each section back to the task that introduced it and the plan notes that document the reasoning
- **Onboarding to unfamiliar modules** — When joining a project or returning to code you haven't touched in months. Instead of reading just the current state, see how the module evolved, which tasks shaped it, and what design decisions were made along the way
- **Debugging with historical context** — When a bug may be related to a recent change, use code evolution to see which tasks introduced specific code sections. The line-range-to-commit-to-task mapping lets you pinpoint exactly when and why a piece of code was added
- **Code review preparation** — Before reviewing a pull request or module, run explain to get comprehensive background. Understanding the history helps distinguish intentional design from accidental complexity
- **Knowledge transfer** — When a team member who implemented a feature is unavailable, the explain skill makes the implicit evolution context explicit and shareable. The structured task/plan records serve as institutional memory

## Walkthrough: Understanding a Refactored Module

You need to understand `aiscripts/lib/task_utils.sh`, a core library that has been modified by many tasks. You don't know the history of the file or why certain patterns exist.

**1. Launch the skill**

```
/aitask-explain
```

Select "Enter paths directly" and provide `aiscripts/lib/task_utils.sh`.

> **Tip:** You can also choose "Search for files" to find files by keyword, name, or functionality — useful when you don't know the exact path. See [File Selection](../../skills/aitask-explain/#file-selection) for details.

**2. Select analysis modes**

Choose all three modes: Functionality, Usage examples, and Code evolution. This gives a comprehensive understanding in one pass.

**3. Reference data generation**

The skill runs `aitask_explain_extract_raw_data.sh`, which gathers the commit history (up to 50 commits), runs `git blame` to map every line to its originating commit, and copies the associated task and plan files into an isolated run directory. The Python processor then builds `reference.yaml`, which maps line ranges to commits to task IDs.

**4. Review the explanation**

Claude presents the analysis across all three modes. The functionality section describes the file's purpose, key functions, and data flow. The usage examples section shows where `task_utils.sh` is sourced and which scripts call its functions. The code evolution section provides a newest-first narrative — for example, it might show that lines 45-67 (the `resolve_task_file` function) were last modified in task t130 ("Support child task hierarchy") and that the plan notes for t130 explain why a recursive lookup was added.

**5. Drill into a specific section**

Select "Ask about specific code section" and ask about `resolve_plan_file`. The skill uses the `line_ranges` data from `reference.yaml` to identify which commits and tasks are relevant to that function, reads the corresponding task and plan files, and provides a targeted explanation combining code analysis with historical context.

**6. Keep the data for later**

When done, select "No, keep" at the cleanup prompt. The analysis data is preserved and can be reused next time you run `/aitask-explain` by selecting "Use existing analysis."

## How It Works

The explain skill builds a structured reference that connects lines of code to the tasks that created them:

```
Target files
    |
    v
aitask_explain_extract_raw_data.sh
    |-- git log --follow (commit timeline per file)
    |-- git blame --porcelain (line-to-commit mapping)
    |-- resolve task/plan files (copy associated aitask/aiplan files)
    |
    v
aitask_explain_process_raw_data.py
    |-- Aggregates blame lines into contiguous line ranges
    |-- Maps ranges to commits and task IDs
    |
    v
reference.yaml (line_ranges -> commits -> tasks)
    |
    v
Claude reads reference.yaml + task/plan files -> structured explanation
```

The `reference.yaml` file is the key artifact. It contains per-file data: a commit timeline (newest first) and a list of line ranges, each annotated with which commits and task IDs contributed to those lines. This enables the skill to answer questions like "which task added lines 50-80?" by looking up the line range in the reference data.

Run directories use the naming convention `<dir_key>__<timestamp>` (e.g., `aiscripts__lib__20260226_155403`), where `dir_key` identifies the source directory. When new analysis data is generated, stale runs for the same source directory are automatically cleaned up — only the newest run is kept. This also happens at codebrowser TUI startup.

## Tips

- **Start with code evolution** — If you only pick one mode, start with code evolution. It provides the most unique value compared to what you could learn by just reading the file. Functionality and usage can often be inferred from the code itself; the "why" behind changes cannot
- **Reuse runs across sessions** — Keep the analysis data when prompted. Subsequent sessions can reuse the cached reference data, avoiding the cost of re-running git analysis. Refresh only when the file has changed significantly
- **Combine with review** — Use `/aitask-explain` to understand why code exists, then use [`/aitask-review`](../../skills/aitask-review/) to evaluate whether it should change. Understanding context first makes review findings more actionable
- **Explain directories for module-level understanding** — Pass a directory path to explain all files in a module at once. The shared commit and task context across files often reveals architectural decisions that are invisible when looking at individual files
- **Manage disk usage** — Stale runs are cleaned up automatically when new data is generated, but you can also run `./aiscripts/aitask_explain_runs.sh --cleanup-stale` to manually remove older runs for the same source directory. Use `./aiscripts/aitask_explain_runs.sh --list` to see all current runs, or the interactive mode to selectively delete individual runs
