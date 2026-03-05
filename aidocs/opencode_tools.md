# OpenCode Tools Documentation

**Generated:** Thu Mar 05 2026  
**OpenCode Version:** 1.2.17  
**Working Directory:** /home/ddt/Work/aitasks

---

## Table of Contents

- [ask](#ask) - Ask the user a question and wait for their response
- [bash](#bash) - Execute bash commands in a persistent shell
- [read](#read) - Read a file or directory from the local filesystem
- [glob](#glob) - Find files matching a glob pattern
- [grep](#grep) - Search file contents using regular expressions
- [edit](#edit) - Replace text in a file
- [write](#write) - Write content to a file
- [webfetch](#webfetch) - Fetch content from a URL
- [websearch](#websearch) - Search the web using Exa AI
- [codesearch](#codesearch) - Search programming context using Exa Code API
- [todowrite](#todowrite) - Create and manage a structured todo list
- [task](#task) - Launch a specialized subagent for complex tasks
- [skill](#skill) - Load a specialized skill for domain-specific tasks

---

## ask

**Description:** Ask the user a question and wait for their response.

**Use Cases:**
- Gather user preferences or requirements
- Clarify ambiguous instructions
- Get decisions on implementation choices
- Offer choices to the user about direction

**Arguments:**
- `question` (string, required): The question to ask the user
- `follow_up` (array): Follow-up questions with structured options
  - Each item contains:
    - `question` (string): Complete question text
    - `options` (array): Available choices with `label` and `description`
    - `header` (string): Short label (max 30 chars)
    - `multiple` (boolean): Allow selecting multiple choices

**Example:**
```json
{
  "question": "What color do you want?",
  "follow_up": [{
    "question": "Choose a color",
    "header": "Color selection",
    "multiple": false,
    "options": [
      {"label": "Red", "description": "Primary color red"},
      {"label": "Blue", "description": "Primary color blue"}
    ]
  }]
}
```

---

## bash

**Description:** Execute a bash command in a persistent shell session.

**Features:**
- Proper handling and security measures
- Timeout support (default 120000ms)
- Output truncation for large results
- Working directory control

**Arguments:**
- `command` (string, required): The command to execute
- `description` (string): Clear description of what the command does (5-10 words)
- `timeout` (number): Optional timeout in milliseconds (max 600000)
- `workdir` (string): Working directory to run the command in

**Important Notes:**
- Use `workdir` parameter instead of `cd` commands
- Quote paths with spaces using double quotes
- Avoid destructive/irreversible commands

**Example:**
```json
{
  "command": "git status",
  "description": "Shows working tree status"
}
```

---

## read

**Description:** Read a file or directory from the local filesystem.

**Features:**
- Returns up to 2000 lines by default
- Line-numbered output (1-indexed)
- Offset parameter for reading sections
- Image and PDF support

**Arguments:**
- `file_path` (string, required): Absolute path to file or directory
- `offset` (number): Line number to start from (1-indexed)
- `limit` (number): Maximum lines to read (default 2000)

**Output Format:**
- Files: Line numbers as prefixes (e.g., `1: content`)
- Directories: Entries with trailing `/` for subdirectories

**Example:**
```json
{
  "file_path": "/home/ddt/Work/aitasks/README.md",
  "offset": 1,
  "limit": 100
}
```

---

## glob

**Description:** Find files matching a glob pattern.

**Features:**
- Works with any codebase size
- Supports patterns like `**/*.js`, `src/**/*.ts`
- Returns sorted results by modification time

**Arguments:**
- `pattern` (string, required): Glob pattern to match
- `path` (string): Directory to search in (defaults to current working directory)

**Example:**
```json
{
  "pattern": "**/*.py",
  "path": "/home/ddt/Work/aitasks"
}
```

---

## grep

**Description:** Search file contents using regular expressions.

**Features:**
- Full regex syntax support
- File filtering by pattern
- Returns file paths and line numbers

**Arguments:**
- `pattern` (string, required): Regex pattern to search for
- `include` (string): File pattern to filter (e.g., "*.js", "*.{ts,tsx}")
- `path` (string): Directory to search in (defaults to current working directory)

**Example:**
```json
{
  "pattern": "function.*Error",
  "include": "*.js",
  "path": "/home/ddt/Work/aitasks/src"
}
```

---

## edit

**Description:** Perform exact string replacements in files.

**Features:**
- Exact match replacement
- Replace all occurrences option
- Requires prior file read

**Arguments:**
- `file_path` (string, required): Absolute path to the file
- `old_string` (string, required): Text to replace
- `new_string` (string, required): Replacement text
- `replace_all` (boolean): Replace all occurrences (default false)

**Example:**
```json
{
  "file_path": "/home/ddt/Work/aitasks/config.json",
  "old_string": "version: 1.0",
  "new_string": "version: 2.0"
}
```

---

## write

**Description:** Write content to a file.

**Features:**
- Overwrites existing files
- Requires prior file read for existing files
- Absolute paths only

**Arguments:**
- `file_path` (string, required): Absolute path to the file
- `content` (string, required): Content to write

**Example:**
```json
{
  "file_path": "/home/ddt/Work/aitasks/newfile.txt",
  "content": "Hello, World!"
}
```

---

## webfetch

**Description:** Fetch content from a specified URL.

**Features:**
- HTTP to HTTPS automatic upgrade
- Multiple format options (markdown, text, html)
- Timeout support

**Arguments:**
- `url` (string, required): Fully-formed valid URL
- `format` (string): Output format - "markdown" (default), "text", or "html"
- `timeout` (number): Optional timeout in seconds (max 120)

**Example:**
```json
{
  "url": "https://example.com/docs",
  "format": "markdown",
  "timeout": 30
}
```

---

## websearch

**Description:** Search the web using Exa AI.

**Features:**
- Real-time web searches
- Live crawling modes
- Configurable result counts

**Arguments:**
- `query` (string, required): Search query
- `numResults` (number): Number of results (default 8)
- `type` (string): Search type - "auto" (default), "fast", or "deep"
- `livecrawl` (string): Crawling mode - "fallback" (default) or "preferred"
- `contextMaxCharacters` (number): Maximum characters for context (default 10000)

**Example:**
```json
{
  "query": "AI news 2026",
  "type": "deep",
  "numResults": 10
}
```

---

## codesearch

**Description:** Search and get relevant context for programming tasks using Exa Code API.

**Features:**
- High quality, fresh context for libraries and APIs
- Comprehensive code examples and documentation
- Optimized for programming patterns

**Arguments:**
- `query` (string, required): Search query (e.g., "React useState hook examples")
- `tokensNum` (number, required): Number of tokens (1000-50000, default 5000)

**Example:**
```json
{
  "query": "Python pandas dataframe filtering",
  "tokensNum": 3000
}
```

---

## todowrite

**Description:** Create and manage a structured todo list for tracking progress.

**Features:**
- Task states: pending, in_progress, completed, cancelled
- Priority levels: high, medium, low
- Progress tracking for complex tasks

**Arguments:**
- `todos` (array, required): Array of todo items
  - Each item contains:
    - `content` (string, required): Task description
    - `status` (string, required): Current status
    - `priority` (string, required): Priority level

**Example:**
```json
{
  "todos": [
    {
      "content": "Implement user authentication",
      "status": "in_progress",
      "priority": "high"
    },
    {
      "content": "Add unit tests",
      "status": "pending",
      "priority": "medium"
    }
  ]
}
```

---

## task

**Description:** Launch a specialized subagent for complex, multi-step tasks.

**Features:**
- General-purpose and explore agent types
- Autonomous task execution
- Reusable task sessions

**Arguments:**
- `prompt` (string, required): Detailed task description
- `description` (string, required): Short task description (3-5 words)
- `subagent_type` (string, required): Agent type - "general" or "explore"
- `task_id` (string): Resume previous task session
- `command` (string): The command that triggered this task

**Example:**
```json
{
  "description": "Review codebase structure",
  "prompt": "Explore this codebase and identify all API endpoints",
  "subagent_type": "explore"
}
```

---

## skill

**Description:** Load a specialized skill for domain-specific instructions and workflows.

**Features:**
- Domain-specific instructions
- Access to bundled resources
- Workflow guidance

**Arguments:**
- `name` (string, required): Skill name from available skills

**Example:**
```json
{
  "name": "aitask-pick"
}
```

---

## Notes

- All paths must be absolute, not relative
- Tools execute sequentially unless explicitly called in parallel
- Most tools require prior file read for editing existing files
- Timeout defaults vary by tool type
- Error handling is built into all tools
