# Gemini CLI Tool Documentation

**Version:** 0.5.0
**Date:** Sunday, February 22, 2026, 02:48 PM IST

This document provides a comprehensive list of all tools available to the Gemini CLI LLM for this session, including their functionality and arguments.

---

## Tool: `list_directory`
Lists the names of files and subdirectories directly within a specified directory path. Can optionally ignore entries matching provided glob patterns.

### Arguments:
- `dir_path` (STRING): The path to the directory to list.
- `file_filtering_options` (OBJECT): Optional: Whether to respect ignore patterns from .gitignore or .geminiignore.
  - `respect_gemini_ignore` (BOOLEAN): Optional: Whether to respect .geminiignore patterns when listing files. Defaults to true.
  - `respect_git_ignore` (BOOLEAN): Optional: Whether to respect .gitignore patterns when listing files. Only available in git repositories. Defaults to true.
- `ignore` (ARRAY of STRING): List of glob patterns to ignore.

---

## Tool: `read_file`
Reads and returns the content of a specified file. If the file is large, the content will be truncated. The tool's response will clearly indicate if truncation has occurred and will provide details on how to read more of the file using the 'offset' and 'limit' parameters. Handles text, images (PNG, JPG, GIF, WEBP, SVG, BMP), audio files (MP3, WAV, AIFF, AAC, OGG, FLAC), and PDF files. For text files, it can read specific line ranges.

### Arguments:
- `file_path` (STRING): The path to the file to read.
- `limit` (NUMBER): Optional: For text files, maximum number of lines to read. Use with 'offset' to paginate through large files. If omitted, reads the entire file (if feasible, up to a default limit).
- `offset` (NUMBER): Optional: For text files, the 0-based line number to start reading from. Requires 'limit' to be set. Use for paginating through large files.

---

## Tool: `grep_search`
Searches for a regular expression pattern within file contents. Max 100 matches.

### Arguments:
- `pattern` (STRING): The pattern to search for. By default, treated as a Rust-flavored regular expression. Use '\b' for precise symbol matching (e.g., '\bMatchMe\b').
- `after` (INTEGER): Show this many lines after each match (equivalent to grep -A). Defaults to 0 if omitted.
- `before` (INTEGER): Show this many lines before each match (equivalent to grep -B). Defaults to 0 if omitted.
- `case_sensitive` (BOOLEAN): If true, search is case-sensitive. Defaults to false (ignore case) if omitted.
- `context` (INTEGER): Show this many lines of context around each match (equivalent to grep -C). Defaults to 0 if omitted.
- `dir_path` (STRING): Directory or file to search. Directories are searched recursively. Relative paths are resolved against current working directory. Defaults to current working directory ('.') if omitted.
- `fixed_strings` (BOOLEAN): If true, treats the `pattern` as a literal string instead of a regular expression. Defaults to false (basic regex) if omitted.
- `include` (STRING): Glob pattern to filter files (e.g., '*.ts', 'src/**'). Recommended for large repositories to reduce noise. Defaults to all files if omitted.
- `no_ignore` (BOOLEAN): If true, searches all files including those usually ignored (like in .gitignore, build/, dist/, etc). Defaults to false if omitted.

---

## Tool: `glob`
Efficiently finds files matching specific glob patterns (e.g., `src/**/*.ts`, `**/*.md`), returning absolute paths sorted by modification time (newest first). Ideal for quickly locating files based on their name or path structure, especially in large codebases.

### Arguments:
- `pattern` (STRING): The glob pattern to match against (e.g., '**/*.py', 'docs/*.md').
- `case_sensitive` (BOOLEAN): Optional: Whether the search should be case-sensitive. Defaults to false.
- `dir_path` (STRING): Optional: The absolute path to the directory to search within. If omitted, searches the root directory.
- `respect_gemini_ignore` (BOOLEAN): Optional: Whether to respect .geminiignore patterns when finding files. Defaults to true.
- `respect_git_ignore` (BOOLEAN): Optional: Whether to respect .gitignore patterns when finding files. Only available in git repositories. Defaults to true.

---

## Tool: `replace`
Replaces text within a file. By default, replaces a single occurrence, but can replace multiple occurrences when `expected_replacements` is specified. This tool requires providing significant context around the change to ensure precise targeting. Always use the read_file tool to examine the file's current content before attempting a text replacement.

### Arguments:
- `file_path` (STRING): The path to the file to modify.
- `instruction` (STRING): A clear, semantic instruction for the code change, acting as a high-quality prompt for an expert LLM assistant. It must be self-contained and explain the goal of the change.
- `old_string` (STRING): The exact literal text to replace, preferably unescaped. For single replacements (default), include at least 3 lines of context BEFORE and AFTER the target text, matching whitespace and indentation precisely.
- `new_string` (STRING): The exact literal text to replace `old_string` with, preferably unescaped. Provide the EXACT text. Ensure the resulting code is correct and idiomatic.
- `expected_replacements` (NUMBER): Number of replacements expected. Defaults to 1 if not specified. Use when you want to replace multiple occurrences. The tool will replace ALL occurrences that match `old_string` exactly. Ensure the number of replacements matches your expectation.

---

## Tool: `write_file`
Writes content to a specified file in the local filesystem.

### Arguments:
- `file_path` (STRING): The path to the file to write to.
- `content` (STRING): The content to write to the file.

---

## Tool: `web_fetch`
Processes content from URL(s), including local and private network addresses (e.g., localhost), embedded in a prompt. Include up to 20 URLs and instructions (e.g., summarize, extract specific data) directly in the 'prompt' parameter.

### Arguments:
- `prompt` (STRING): A comprehensive prompt that includes the URL(s) (up to 20) to fetch and specific instructions on how to process their content (e.g., "Summarize https://example.com/article and extract key points from https://another.com/data").

---

## Tool: `run_shell_command`
This tool executes a given shell command as `bash -c <command>`. To run a command in the background, set the `is_background` parameter to true. Do NOT use `&` to background commands. Command is executed as a subprocess that leads its own process group. Command process group can be terminated as `kill -- -PGID` or signaled as `kill -s SIGNAL -- -PGID`.

### Arguments:
- `command` (STRING): Exact bash command to execute as `bash -c <command>`.
- `description` (STRING): Brief description of the command for the user. Be specific and concise. Ideally a single sentence. Can be up to 3 sentences for clarity. No line breaks.
- `dir_path` (STRING): (OPTIONAL) The path of the directory to run the command in. If not provided, the project root directory is used. Must be a directory within the workspace and must already exist.
- `is_background` (BOOLEAN): Set to true if this command should be run in the background (e.g. for long-running servers or watchers). The command will be started, allowed to run for a brief moment to check for immediate errors, and then moved to the background.

---

## Tool: `save_memory`
Saves concise global user context (preferences, facts) for use across ALL workspaces.
**CRITICAL: GLOBAL CONTEXT ONLY.** NEVER save workspace-specific context, local paths, or commands (e.g. "The entry point is src/index.js", "The test command is npm test"). These are local to the current workspace and must NOT be saved globally. EXCLUSIVELY for context relevant across ALL workspaces.

### Arguments:
- `fact` (STRING): The specific fact or piece of information to remember. Should be a clear, self-contained statement.

---

## Tool: `google_web_search`
Performs a web search using Google Search (via the Gemini API) and returns the results. This tool is useful for finding information on the internet based on a query.

### Arguments:
- `query` (STRING): The search query to find information on the web.

---

## Tool: `enter_plan_mode`
Switch to Plan Mode to safely research, design, and plan complex changes using read-only tools.

### Arguments:
- `reason` (STRING): Short reason explaining why you are entering plan mode.

---

## Tool: `codebase_investigator`
The specialized tool for codebase analysis, architectural mapping, and understanding system-wide dependencies. Invoke this tool for tasks like vague requests, bug root-cause analysis, system refactoring, comprehensive feature implementation or to answer questions about the codebase that require investigation. It returns a structured report with key file paths, symbols, and actionable architectural insights.

### Arguments:
- `objective` (STRING): A comprehensive and detailed description of the user's ultimate goal. You must include original user's objective as well as questions and any extra context and questions you may have.

---

## Tool: `cli_help`
Specialized in answering questions about how users use you, (Gemini CLI): features, documentation, and current runtime configuration.

### Arguments:
- `question` (STRING): The specific question about Gemini CLI.

---

## Tool: `activate_skill`
Activates a specialized agent skill by name. Returns the skill's instructions wrapped in `<activated_skill>` tags. These provide specialized guidance for the current task. Use this when you identify a task that matches a skill's description. ONLY use names exactly as they appear in the `<available_skills>` section.

### Arguments:
- `name` (STRING): The name of the skill to activate (Available: 'skill-creator').
