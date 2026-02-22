---
title: "/aitask-explain"
linkTitle: "/aitask-explain"
weight: 55
description: "Explain files: functionality, usage examples, and code evolution traced through aitasks"
---

Explain files in the project by providing detailed analysis of their functionality, real usage examples from the codebase, and code evolution history traced through aitask and aiplan records. The unique value of this skill is answering not just "what does this code do" but "why does it exist and how did it get here" — by connecting code sections back to the tasks that motivated each change and the plan notes that document the reasoning.

**Usage:**
```
/aitask-explain                     # Interactive: select files and analysis mode
/aitask-explain path/to/file.sh     # Direct: explain a specific file
/aitask-explain src/lib/            # Direct: explain all git-tracked files in a directory
```

## Workflow Overview

1. **File selection** — Choose files via three methods: reuse data from a previous explain run, search the project using the file-select interface, or enter file/directory paths directly. Directories are automatically expanded to all git-tracked text files within them
2. **Mode selection** — Choose one or more analysis modes (multi-select): Functionality (what the code does), Usage examples (how it is used in the project), Code evolution (how it changed over time, traced through commits and aitasks)
3. **Generate reference data** — Gathers git commit history and blame data for each file, extracts associated task and plan files, and produces a structured `reference.yaml` mapping line ranges to commits to task IDs. Each run creates an isolated directory under `aiexplains/<timestamp>/`
4. **Analysis and explanation** — Functionality covers purpose, key components, data flow, error handling, and design patterns. Usage examples searches the project for real imports, references, and call sites. Code evolution presents a newest-first narrative of how the code evolved, citing specific commits and linking to the tasks and plan notes that motivated each change
5. **Interactive follow-up** — Ask about specific code sections (by line range, function name, or description), switch analysis modes, or analyze different files. Reference data is reused across follow-ups within the same session
6. **Cleanup** — Choose to delete the run directory or keep it for reuse in future sessions

## Key Capabilities

- **Three analysis modes** — Functionality, usage examples, and code evolution can be selected individually or combined. Multi-select lets you get a complete picture in one pass
- **Line-to-task tracing** — The `reference.yaml` maps every line of code to the commit that last touched it, and from there to the aitask that motivated the change. This lets code evolution mode explain not just what changed but why, citing the original task description and plan notes
- **Run reuse** — Generated reference data is stored in `aiexplains/<timestamp>/` and can be reused across sessions. When you return to a file, select "Use existing analysis" to skip regeneration. Data can also be refreshed if the file has changed
- **Directory expansion** — Passing a directory path expands to all git-tracked text files within it, making it easy to explain entire modules at once
- **Interactive drill-down** — After the initial explanation, ask targeted questions about specific code sections. The skill uses the line-range-to-commit mapping from `reference.yaml` to provide historically-grounded answers

## Run Management

Run data is stored under `aiexplains/` with one timestamped directory per run. Each directory contains `files.txt` (analyzed files), `reference.yaml` (structured reference data), and `tasks/` + `plans/` subdirectories with extracted aitask and aiplan files.

```bash
# List all runs
./aiscripts/aitask_explain_runs.sh --list

# Interactive deletion with fzf
./aiscripts/aitask_explain_runs.sh

# Delete a specific run
./aiscripts/aitask_explain_runs.sh --delete aiexplains/20260221_143052

# Delete all runs
./aiscripts/aitask_explain_runs.sh --delete-all
```

For a full workflow guide covering use cases and the cognitive debt framing, see [Understanding Code with Explain](../../workflows/explain/).
