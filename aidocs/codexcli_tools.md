# Codex CLI Tooling Reference (Current Session)

- Generated at: 2026-02-20T12:52:10+02:00
- Project root: `/home/ddt/Work/aitasks`
- Codex CLI version: `codex-cli 0.104.0`

## Tool Namespace: `web`

### `web.run`
Single internet/data-access tool that supports multiple operation types in one call.

Arguments:
- `open` (array): Open a page by `ref_id` or URL, optional `lineno`.
- `click` (array): Click a link on an opened page using `ref_id` + numeric `id`.
- `find` (array): Find `pattern` text in an opened page (`ref_id`).
- `screenshot` (array): Capture PDF page image by `ref_id` + `pageno`.
- `image_query` (array): Image search entries with `q`, optional `recency`, optional `domains`.
- `sports` (array): Sports schedules/standings with:
  - `tool` (`"sports"`), `fn` (`"schedule"|"standings"`), `league`
  - optional `team`, `opponent`, `date_from`, `date_to`, `num_games`, `locale`
- `finance` (array): Market quotes with `ticker`, `type` (`equity|fund|crypto|index`), optional `market`.
- `weather` (array): Forecast lookups with `location`, optional `start`, optional `duration`.
- `time` (array): Time lookup by `utc_offset`.
- `search_query` (array): Web search entries with `q`, optional `recency`, optional `domains`.
- `response_length` (`short|medium|long`): Controls tool response verbosity.

## Tool Namespace: `functions`

### `functions.exec_command`
Run a shell command in a PTY/non-PTY execution context.

Arguments:
- `cmd` (string, required): Shell command.
- `justification` (string, optional): Approval request text when escalation is required.
- `login` (boolean, optional): Use login/interactive shell semantics.
- `max_output_tokens` (number, optional): Output token cap.
- `prefix_rule` (string[], optional): Suggested reusable approval prefix.
- `sandbox_permissions` (string, optional): Sandbox mode override.
- `shell` (string, optional): Shell binary.
- `tty` (boolean, optional): Allocate TTY.
- `workdir` (string, optional): Working directory.
- `yield_time_ms` (number, optional): Wait time before returning output.

### `functions.write_stdin`
Send input to an existing running exec session and poll output.

Arguments:
- `session_id` (number, required): Target session.
- `chars` (string, optional): Data to write to stdin.
- `max_output_tokens` (number, optional): Output token cap.
- `yield_time_ms` (number, optional): Wait time before returning output.

### `functions.update_plan`
Update the internal task plan/status list.

Arguments:
- `explanation` (string, optional): Brief plan-update rationale.
- `plan` (array, required): Steps, each with:
  - `step` (string)
  - `status` (`pending|in_progress|completed`)

### `functions.request_user_input`
Ask 1-3 short multiple-choice questions and wait for user response (Plan mode only).

Arguments:
- `questions` (array, required): Question objects containing:
  - `header` (string, <=12 chars)
  - `id` (string, snake_case)
  - `question` (string)
  - `options` (array, 2-3): each with `label` + `description`

### `functions.view_image`
View a local image from filesystem by absolute/local path.

Arguments:
- `path` (string, required): Image path.

### `functions.apply_patch`
Apply file edits via unified patch grammar.

Input format:
- FREEFORM patch text (not JSON), using:
  - `*** Begin Patch`
  - one or more file hunks (`*** Add File`, `*** Update File`, `*** Delete File`)
  - `*** End Patch`

## Tool Namespace: `multi_tool_use`

### `multi_tool_use.parallel`
Run multiple `functions.*` tool calls concurrently when tasks are parallelizable.

Arguments:
- `tool_uses` (array, required): Each item has:
  - `recipient_name` (string): Must be `functions.<tool_name>`
  - `parameters` (object): Arguments for that tool
