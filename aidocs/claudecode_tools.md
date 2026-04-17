# Claude Code Tools Reference

**Generated:** 2026-03-05 13:02:58 IST
**Claude Code Version:** 2.1.69
**Model:** Claude Opus 4.7 (`claude-opus-4-7`)

---

## Table of Contents

1. [Read](#read)
2. [Write](#write)
3. [Edit](#edit)
4. [Bash](#bash)
5. [Grep](#grep)
6. [Glob](#glob)
7. [Agent](#agent)
8. [AskUserQuestion](#askuserquestion)
9. [TodoWrite](#todowrite)
10. [WebFetch](#webfetch)
11. [WebSearch](#websearch)
12. [Skill](#skill)
13. [LSP](#lsp)
14. [NotebookEdit](#notebookedit)
15. [EnterPlanMode](#enterplanmode)
16. [ExitPlanMode](#exitplanmode)
17. [EnterWorktree](#enterworktree)
18. [TaskOutput](#taskoutput)
19. [TaskStop](#taskstop)
20. [ToolSearch](#toolsearch)

---

## Read

Reads a file from the local filesystem. Supports text files, images (PNG, JPG, etc.), PDFs, and Jupyter notebooks (.ipynb). Returns content with line numbers (cat -n format). Lines longer than 2000 characters are truncated. Can only read files, not directories.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `file_path` | string | Yes | The absolute path to the file to read |
| `offset` | number | No | The line number to start reading from. Only provide if the file is too large to read at once |
| `limit` | number | No | The number of lines to read. Only provide if the file is too large to read at once |
| `pages` | string | No | Page range for PDF files (e.g., "1-5", "3", "10-20"). Only applicable to PDF files. Maximum 20 pages per request |

---

## Write

Writes a file to the local filesystem. Overwrites the existing file if one exists at the provided path. For existing files, the Read tool must be used first. Prefer Edit for modifying existing files (sends only the diff).

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `file_path` | string | Yes | The absolute path to the file to write (must be absolute, not relative) |
| `content` | string | Yes | The content to write to the file |

---

## Edit

Performs exact string replacements in files. The `old_string` must be unique in the file unless `replace_all` is used. The Read tool must be used at least once before editing. Preserves exact indentation.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `file_path` | string | Yes | The absolute path to the file to modify |
| `old_string` | string | Yes | The text to replace |
| `new_string` | string | Yes | The text to replace it with (must be different from old_string) |
| `replace_all` | boolean | No | Replace all occurrences of old_string (default false) |

---

## Bash

Executes a given bash command and returns its output. The working directory persists between commands, but shell state does not. The shell environment is initialized from the user's profile. Prefer dedicated tools (Read, Edit, Write, Grep, Glob) over shell equivalents.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `command` | string | Yes | The command to execute |
| `description` | string | No | Clear, concise description of what this command does in active voice |
| `timeout` | number | No | Optional timeout in milliseconds (max 600000). Default 120000 (2 minutes) |
| `run_in_background` | boolean | No | Set to true to run this command in the background. Use TaskOutput to read the output later |
| `dangerouslyDisableSandbox` | boolean | No | Set to true to override sandbox mode and run commands without sandboxing |

---

## Grep

A powerful search tool built on ripgrep. Supports full regex syntax, file filtering with glob or type parameters, and multiple output modes. Use instead of running `grep` or `rg` via Bash.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `pattern` | string | Yes | The regular expression pattern to search for in file contents |
| `path` | string | No | File or directory to search in. Defaults to current working directory |
| `glob` | string | No | Glob pattern to filter files (e.g. "*.js", "*.{ts,tsx}") |
| `type` | string | No | File type to search (e.g., "js", "py", "rust", "go") |
| `output_mode` | string | No | "content" (matching lines), "files_with_matches" (file paths, default), or "count" (match counts) |
| `-i` | boolean | No | Case insensitive search |
| `-n` | boolean | No | Show line numbers in output (default true). Requires output_mode: "content" |
| `-A` | number | No | Number of lines to show after each match. Requires output_mode: "content" |
| `-B` | number | No | Number of lines to show before each match. Requires output_mode: "content" |
| `-C` | number | No | Alias for context |
| `context` | number | No | Number of lines to show before and after each match. Requires output_mode: "content" |
| `multiline` | boolean | No | Enable multiline mode where `.` matches newlines and patterns can span lines. Default false |
| `head_limit` | number | No | Limit output to first N lines/entries. Defaults to 0 (unlimited) |
| `offset` | number | No | Skip first N lines/entries before applying head_limit. Defaults to 0 |

---

## Glob

Fast file pattern matching tool that works with any codebase size. Supports glob patterns like `**/*.js` or `src/**/*.ts`. Returns matching file paths sorted by modification time. Use instead of `find` or `ls` via Bash.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `pattern` | string | Yes | The glob pattern to match files against |
| `path` | string | No | The directory to search in. Defaults to current working directory |

---

## Agent

Launches a new agent (subprocess) to handle complex, multi-step tasks autonomously. Each agent type has specific capabilities. Supports foreground and background execution, and worktree isolation.

**Available agent types:**

- **general-purpose**: General-purpose agent for researching complex questions, searching for code, and executing multi-step tasks. Has access to all tools.
- **statusline-setup**: Configures the user's Claude Code status line setting. Has access to Read and Edit.
- **Explore**: Fast agent specialized for exploring codebases — finding files, searching code, answering questions about the codebase. Has access to all tools except Agent, ExitPlanMode, Edit, Write, NotebookEdit.
- **Plan**: Software architect agent for designing implementation plans. Has access to all tools except Agent, ExitPlanMode, Edit, Write, NotebookEdit.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `description` | string | Yes | A short (3-5 word) description of the task |
| `prompt` | string | Yes | The task for the agent to perform |
| `subagent_type` | string | Yes | The type of specialized agent to use (general-purpose, statusline-setup, Explore, Plan) |
| `run_in_background` | boolean | No | Set to true to run this agent in the background |
| `isolation` | string | No | Set to "worktree" to run the agent in a temporary git worktree |
| `resume` | string | No | Optional agent ID to resume from a previous invocation |

---

## AskUserQuestion

Asks the user questions during execution to gather preferences, clarify ambiguous instructions, get implementation decisions, or offer choices. Supports single and multi-select options with 2-4 choices per question (plus automatic "Other" option). Supports 1-4 questions per invocation.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `questions` | array | Yes | Questions to ask the user (1-4 questions). Each question has: `question` (string), `header` (string, max 12 chars), `options` (array of 2-4 objects with `label`, `description`, optional `preview`), `multiSelect` (boolean) |
| `answers` | object | No | User answers collected by the permission component |
| `annotations` | object | No | Optional per-question annotations from the user |
| `metadata` | object | No | Optional metadata for tracking and analytics purposes |

---

## TodoWrite

Creates and manages a structured task list for the current coding session. Helps track progress, organize complex tasks, and demonstrate thoroughness. Use for tasks with 3+ steps, multiple operations, or when the user provides multiple tasks.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `todos` | array | Yes | The updated todo list. Each item has: `content` (string, imperative form), `status` ("pending", "in_progress", or "completed"), `activeForm` (string, present continuous form) |

---

## WebFetch

Fetches content from a specified URL, converts HTML to markdown, and processes it with a prompt using a small, fast model. Includes a self-cleaning 15-minute cache. Will fail for authenticated or private URLs — use specialized tools for those.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `url` | string (URI) | Yes | The URL to fetch content from |
| `prompt` | string | Yes | The prompt to run on the fetched content |

---

## WebSearch

Searches the web and returns results to inform responses. Provides up-to-date information beyond Claude's knowledge cutoff. Returns search result blocks with links as markdown hyperlinks. Supports domain filtering.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | string | Yes | The search query to use (min 2 chars) |
| `allowed_domains` | array of strings | No | Only include search results from these domains |
| `blocked_domains` | array of strings | No | Never include search results from these domains |

---

## Skill

Executes a skill (slash command) within the main conversation. Skills provide specialized capabilities and domain knowledge. Available skills are listed in system-reminder messages.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `skill` | string | Yes | The skill name. E.g., "commit", "review-pr", or "pdf". Can use fully qualified names like "ms-office-suite:pdf" |
| `args` | string | No | Optional arguments for the skill |

---

## LSP

Interacts with Language Server Protocol (LSP) servers for code intelligence features. LSP servers must be configured for the file type.

**Supported operations:** `goToDefinition`, `findReferences`, `hover`, `documentSymbol`, `workspaceSymbol`, `goToImplementation`, `prepareCallHierarchy`, `incomingCalls`, `outgoingCalls`

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `operation` | string | Yes | The LSP operation to perform (one of the supported operations listed above) |
| `filePath` | string | Yes | The absolute or relative path to the file |
| `line` | integer | Yes | The line number (1-based) |
| `character` | integer | Yes | The character offset (1-based) |

---

## NotebookEdit

Replaces, inserts, or deletes cells in a Jupyter notebook (.ipynb file). Cell numbering is 0-indexed.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `notebook_path` | string | Yes | The absolute path to the Jupyter notebook file to edit |
| `new_source` | string | Yes | The new source for the cell |
| `cell_id` | string | No | The ID of the cell to edit. For insert mode, new cell is inserted after this cell |
| `cell_type` | string | No | The type of the cell: "code" or "markdown". Required for insert mode |
| `edit_mode` | string | No | The type of edit: "replace" (default), "insert", or "delete" |

---

## EnterPlanMode

Transitions into plan mode for designing implementation approaches before writing code. Use proactively for non-trivial implementation tasks: new features, multiple valid approaches, code modifications, architectural decisions, multi-file changes, unclear requirements, or when user preferences matter. In plan mode, you explore the codebase, design an approach, and present it for user approval.

**Arguments:** None (empty object)

---

## ExitPlanMode

Signals that the plan is complete and ready for user approval. Use only when planning implementation steps for a task that requires writing code. The user will see the plan file contents for review.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `allowedPrompts` | array | No | Prompt-based permissions needed to implement the plan. Each item has `tool` ("Bash") and `prompt` (semantic description of the action) |

---

## EnterWorktree

Creates an isolated git worktree and switches the current session into it. Use ONLY when the user explicitly asks to work in a worktree. Creates worktrees inside `.claude/worktrees/` with a new branch based on HEAD.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | No | Optional name for the worktree. A random name is generated if not provided |

---

## TaskOutput

Retrieves output from a running or completed task (background shell, agent, or remote session). Supports blocking and non-blocking modes.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `task_id` | string | Yes | The task ID to get output from |
| `block` | boolean | Yes | Whether to wait for completion (default true) |
| `timeout` | number | Yes | Max wait time in ms (default 30000, max 600000) |

---

## TaskStop

Stops a running background task by its ID.

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `task_id` | string | No | The ID of the background task to stop |
| `shell_id` | string | No | Deprecated: use task_id instead |

---

## ToolSearch

Searches for or selects deferred tools to make them available for use. Deferred tools must be loaded via this tool before they can be called. Supports keyword search and direct selection modes.

**Query modes:**

- **Keyword search**: Use keywords to discover tools (e.g., "slack message", "notebook jupyter"). Returns up to 5 matching tools ranked by relevance.
- **Direct selection**: Use `select:<tool_name>` for exact tool selection (e.g., "select:Read,Edit,Grep"). Multiple tools can be comma-separated.
- **Required keyword**: Prefix with `+` to require a match (e.g., "+linear create issue").

**Arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | string | Yes | Query to find deferred tools. Use "select:<tool_name>" for direct selection, or keywords to search |
| `max_results` | number | No | Maximum number of results to return (default 5) |
