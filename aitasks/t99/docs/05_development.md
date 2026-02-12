<!-- SECTION: Development — Architecture and Library Scripts -->
<!-- PLACEMENT: before "### Modifying scripts" in Development section -->

### Architecture

The framework follows a dispatcher pattern. The `ait` script in the project root routes subcommands to individual scripts:

```
ait <subcommand> [args]  →  aiscripts/aitask_<subcommand>.sh [args]
```

**Directory layout:**

| Directory | Purpose |
|-----------|---------|
| `aiscripts/` | All framework scripts (`aitask_*.sh`) |
| `aiscripts/lib/` | Shared library scripts sourced by main scripts |
| `.claude/skills/aitask-*` | Claude Code skill definitions (SKILL.md files) |
| `aitasks/` | Active task files (`t<N>_name.md`) and child task directories (`t<N>/`) |
| `aiplans/` | Active plan files (`p<N>_name.md`) and child plan directories (`p<N>/`) |
| `aitasks/archived/` | Completed task files and child directories |
| `aiplans/archived/` | Completed plan files and child directories |
| `aitasks/metadata/` | Configuration: `labels.txt`, `task_types.txt`, `emails.txt`, `profiles/` |

### Library Scripts

Shared utilities in `aiscripts/lib/` are sourced by main scripts. Both libraries use a double-source guard (`[[ -n "${_VAR_LOADED:-}" ]] && return 0`) to prevent duplicate loading.

#### lib/task_utils.sh

Task and plan file resolution utilities. Sources `terminal_compat.sh` automatically.

**Directory variables** (override before sourcing if needed):

- `TASK_DIR` — Active task directory (default: `aitasks`)
- `ARCHIVED_DIR` — Archived task directory (default: `aitasks/archived`)
- `PLAN_DIR` — Active plan directory (default: `aiplans`)
- `ARCHIVED_PLAN_DIR` — Archived plan directory (default: `aiplans/archived`)

**Functions:**

- **`resolve_task_file(task_id)`** — Find a task file by number (e.g., `"53"` or `"53_6"`). Searches active directory first, then archived. Dies if not found or if multiple matches exist.
- **`resolve_plan_file(task_id)`** — Find the corresponding plan file using `t→p` prefix conversion (e.g., `t53_name.md` → `p53_name.md`). Returns empty string if not found.
- **`extract_issue_url(file_path)`** — Parse the `issue:` field from a task file's YAML frontmatter. Returns empty string if not present.
- **`extract_final_implementation_notes(plan_path)`** — Extract the `## Final Implementation Notes` section from a plan file. Stops at the next `##` heading. Trims leading/trailing blank lines.

#### lib/terminal_compat.sh

Terminal capability detection and colored output helpers.

**Color variables:** `RED`, `GREEN`, `YELLOW`, `BLUE`, `NC` (no color) — standard ANSI escape codes.

**Logging functions:**

- **`die(message)`** — Print red error message to stderr and exit 1
- **`info(message)`** — Print blue informational message
- **`success(message)`** — Print green success message
- **`warn(message)`** — Print yellow warning to stderr

**Detection functions:**

- **`ait_check_terminal_capable()`** — Returns 0 if the terminal supports modern features (TUI, true color). Checks `COLORTERM`, `WT_SESSION`, `TERM_PROGRAM`, `TERM`, and tmux/screen presence. Caches result in `AIT_TERMINAL_CAPABLE`.
- **`ait_is_wsl()`** — Returns 0 if running under Windows Subsystem for Linux (checks `/proc/version` for "microsoft").
- **`ait_warn_if_incapable_terminal()`** — Prints suggestions for upgrading to a modern terminal if capability check fails. Provides WSL-specific guidance when applicable. Suppressed by `AIT_SKIP_TERMINAL_CHECK=1`.
