# Gemini CLI Tools Documentation

**Date:** Thursday, March 5, 2026  
**Gemini CLI Version:** 0.32.1

This document provides a comprehensive list of tools available to the Gemini CLI agent in this session, including their functionality and arguments.

---

## File System Tools

### `list_directory`
Lists the names of files and subdirectories directly within a specified directory path.
- **Arguments:**
  - `dir_path` (string, required): The path to the directory to list.
  - `file_filtering_options` (object, optional): Whether to respect ignore patterns from `.gitignore` or `.geminiignore`.
  - `ignore` (array of strings, optional): List of glob patterns to ignore.

### `read_file`
Reads and returns the content of a specified file. Handles text, images (PNG, JPG, GIF, WEBP, SVG, BMP), audio (MP3, WAV, AIFF, AAC, OGG, FLAC), and PDF files.
- **Arguments:**
  - `file_path` (string, required): The path to the file to read.
  - `start_line` (number, optional): The 1-based line number to start reading from.
  - `end_line` (number, optional): The 1-based line number to end reading at (inclusive).

### `write_file`
Writes the complete content to a file, automatically creating missing parent directories. Overwrites existing files.
- **Arguments:**
  - `file_path` (string, required): Path to the file.
  - `content` (string, required): The complete content to write.

### `replace`
Replaces text within a file. By default, replaces exactly ONE occurrence unless `allow_multiple` is set.
- **Arguments:**
  - `file_path` (string, required): The path to the file to modify.
  - `instruction` (string, required): A clear, semantic instruction for the code change.
  - `old_string` (string, required): The exact literal text to replace.
  - `new_string` (string, required): The exact literal text to replace `old_string` with.
  - `allow_multiple` (boolean, optional): If true, replaces all occurrences of `old_string`.

### `glob`
Efficiently finds files matching specific glob patterns (e.g., `src/**/*.ts`).
- **Arguments:**
  - `pattern` (string, required): The glob pattern to match against.
  - `dir_path` (string, optional): The absolute path to the directory to search within.
  - `case_sensitive` (boolean, optional): Whether the search should be case-sensitive.
  - `respect_gemini_ignore` (boolean, optional): Whether to respect `.geminiignore` patterns.
  - `respect_git_ignore` (boolean, optional): Whether to respect `.gitignore` patterns.

### `grep_search`
Searches for a regular expression pattern within file contents. Powered by ripgrep.
- **Arguments:**
  - `pattern` (string, required): The pattern to search for (Rust-flavored regex).
  - `dir_path` (string, optional): Directory or file to search. Defaults to current directory.
  - `include_pattern` (string, optional): Glob pattern to filter files (e.g., `*.ts`).
  - `exclude_pattern` (string, optional): Regex pattern to exclude from results.
  - `case_sensitive` (boolean, optional): Defaults to false.
  - `fixed_strings` (boolean, optional): Treats pattern as a literal string.
  - `before` / `after` / `context` (number, optional): Lines of context to show.
  - `max_matches_per_file` (number, optional): Limit matches per file.
  - `total_max_matches` (number, optional): Limit total matches (defaults to 100).
  - `names_only` (boolean, optional): Return only file paths.
  - `no_ignore` (boolean, optional): Search ignored files.

---

## System and Shell Tools

### `run_shell_command`
Executes a given shell command as `bash -c <command>`.
- **Arguments:**
  - `command` (string, required): Exact bash command to execute.
  - `description` (string, required): Brief description of the command's purpose.
  - `dir_path` (string, optional): The path of the directory to run the command in.
  - `is_background` (boolean, optional): Run the command in the background.

---

## Agent Coordination and Memory

### `codebase_investigator`
Specialized sub-agent for codebase analysis, architectural mapping, and understanding system-wide dependencies.
- **Arguments:**
  - `objective` (string, required): Detailed description of the goal.

### `cli_help`
Specialized sub-agent for answering questions about Gemini CLI features, documentation, and configuration.
- **Arguments:**
  - `question` (string, required): The specific question about Gemini CLI.

### `generalist`
A general-purpose AI agent with access to all tools, ideal for batch tasks or high-volume output processing.
- **Arguments:**
  - `request` (string, required): The task or question for the generalist agent.

### `activate_skill`
Activates a specialized agent skill by name to provide expert guidance and resources.
- **Arguments:**
  - `name` (enum, required): The name of the skill (e.g., `skill-creator`, `aitask-review`).

### `save_memory`
Persists global preferences or facts across ALL future sessions in a global memory file.
- **Arguments:**
  - `fact` (string, required): A concise, global fact or preference.

---

## External Information Gathering

### `google_web_search`
Performs a grounded Google Search to find information across the internet.
- **Arguments:**
  - `query` (string, required): The search query.

### `web_fetch`
Analyzes and extracts information from up to 20 URLs.
- **Arguments:**
  - `prompt` (string, required): The URL(s) and specific analysis instructions.

---

## Available Skills
The following skills can be activated via `activate_skill`:
- `skill-creator`
- `aitask-wrap`
- `aitask-web-merge`
- `aitask-stats`
- `aitask-reviewguide-merge`
- `aitask-reviewguide-import`
- `aitask-reviewguide-classify`
- `aitask-review`
- `aitask-refresh-code-models`
- `aitask-pr-import`
- `aitask-pickweb`
- `aitask-pickrem`
- `aitask-pick`
- `aitask-fold`
- `aitask-explore`
- `aitask-explain`
- `aitask-create`
- `aitask-changelog`
