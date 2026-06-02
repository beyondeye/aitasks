# Codex CLI Tools Reference

- Generated at: **2026-03-05 12:31:28 IST +0200**
- Codex CLI version: **codex-cli 0.110.0**
- Project root: **`/home/ddt/Work/aitasks`**

## Available Tools in This Session

## `web.run`
General internet/data access tool. Accepts a single object with one or more operation fields.

### `search_query`
Functionality: Web search for text queries.

Arguments (per query object):
- `q` (string): Search query text.
- `recency` (integer, optional): Restrict to recent days.
- `domains` (string[], optional): Domain allowlist.

### `image_query`
Functionality: Image search.

Arguments (per query object):
- `q` (string): Image query.
- `recency` (integer, optional): Restrict to recent days.
- `domains` (string[], optional): Domain allowlist.

### `open`
Functionality: Open a result/reference URL and optionally jump to line number.

Arguments (per open object):
- `ref_id` (string): Search ref (e.g., `turn0search0`) or full URL.
- `lineno` (integer, optional): Target line.

### `click`
Functionality: Follow a numbered link from an opened page.

Arguments (per click object):
- `ref_id` (string): Opened page reference.
- `id` (integer): Link id.

### `find`
Functionality: Find text pattern in an opened page.

Arguments (per find object):
- `ref_id` (string): Opened page reference.
- `pattern` (string): Search pattern.

### `screenshot`
Functionality: Capture PDF page screenshot.

Arguments (per screenshot object):
- `ref_id` (string): PDF reference.
- `pageno` (integer): 0-based page index.

### `sports`
Functionality: Sports standings/schedules.

Arguments (per sports object):
- `tool` (`"sports"`)
- `fn` (`"schedule" | "standings"`)
- `league` (`"nba" | "wnba" | "nfl" | "nhl" | "mlb" | "epl" | "ncaamb" | "ncaawb" | "ipl"`)
- `team` (string, optional)
- `opponent` (string, optional)
- `date_from` (YYYY-MM-DD, optional)
- `date_to` (YYYY-MM-DD, optional)
- `num_games` (integer, optional)
- `locale` (string, optional)

### `finance`
Functionality: Market quotes.

Arguments (per finance object):
- `ticker` (string)
- `type` (`"equity" | "fund" | "crypto" | "index"`)
- `market` (string, optional)

### `weather`
Functionality: Weather forecast lookup.

Arguments (per weather object):
- `location` (string)
- `start` (YYYY-MM-DD, optional)
- `duration` (integer days, optional)

### `time`
Functionality: Local time by UTC offset.

Arguments (per time object):
- `utc_offset` (string, format like `+03:00`)

### Shared/Top-level `web.run` fields
- `response_length` (`"short" | "medium" | "long"`, optional)

---

## `functions.exec_command`
Functionality: Run a shell command (optionally PTY) and return output or interactive session id.

Arguments:
- `cmd` (string): Shell command to execute.
- `justification` (string, optional): Approval prompt text (when escalation is required).
- `login` (boolean, optional): Run login/interactive shell semantics.
- `max_output_tokens` (integer, optional): Output cap.
- `prefix_rule` (string[], optional): Suggested reusable approval command prefix.
- `sandbox_permissions` (string, optional): Sandbox mode override request.
- `shell` (string, optional): Shell binary.
- `tty` (boolean, optional): Allocate TTY.
- `workdir` (string, optional): Working directory.
- `yield_time_ms` (integer, optional): Wait time before returning output.

## `functions.write_stdin`
Functionality: Send input to an existing exec session and fetch recent output.

Arguments:
- `session_id` (integer): Existing session id.
- `chars` (string, optional): Bytes to write.
- `max_output_tokens` (integer, optional): Output cap.
- `yield_time_ms` (integer, optional): Wait time before returning output.

## `functions.update_plan`
Functionality: Update task plan and statuses.

Arguments:
- `explanation` (string, optional): Plan-level note.
- `plan` (array): Step objects:
  - `step` (string): Step text.
  - `status` (`"pending" | "in_progress" | "completed"`)

## `functions.request_user_input`
Functionality: Ask 1-3 short multiple-choice questions and wait for user reply (Plan mode only).

Arguments:
- `questions` (array, 1-3 items):
  - `header` (string, <=12 chars)
  - `id` (string, snake_case)
  - `question` (string)
  - `options` (array, 2-3 items):
    - `label` (string)
    - `description` (string)

## `functions.view_image`
Functionality: View a local image file by absolute/accessible path.

Arguments:
- `path` (string): Local filesystem path.

## `functions.apply_patch`
Functionality: Apply structured patch edits to files.

Arguments:
- FREEFORM patch text in required grammar:
  - Must start with `*** Begin Patch`
  - One or more hunks:
    - `*** Add File: <filename>` with `+` lines
    - `*** Delete File: <filename>`
    - `*** Update File: <filename>` with diff-style context and `+/-/ ` lines
    - Optional `*** Move to: <filename>`
  - Must end with `*** End Patch`

## `multi_tool_use.parallel`
Functionality: Execute multiple developer tools in parallel when safe.

Arguments:
- `tool_uses` (array): Each entry includes:
  - `recipient_name` (string): Tool name in format `<tool_name>.<function_name>`
  - `parameters` (object): Arguments for that specific tool call

Notes:
- Only developer-defined tools are allowed in this wrapper.
- Parallel calls should be independent and safe to run concurrently.
