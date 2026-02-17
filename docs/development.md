# Development

## Table of Contents

- [Architecture](#architecture)
- [Directory Layout](#directory-layout)
- [Library Scripts](#library-scripts)
  - [lib/task_utils.sh](#libtask_utilssh)
  - [lib/terminal_compat.sh](#libterminal_compatsh)
- [Atomic Task ID Counter](#atomic-task-id-counter)
- [Atomic Task Locking](#atomic-task-locking)
- [Modifying Scripts](#modifying-scripts)
- [Testing Changes](#testing-changes)
- [Release Process](#release-process)
- [Keeping Documentation in Sync](#keeping-documentation-in-sync)

---

## Architecture

The framework follows a dispatcher pattern. The `ait` script in the project root routes subcommands to individual scripts:

```
ait <subcommand> [args]  →  aiscripts/aitask_<subcommand>.sh [args]
```

## Directory Layout

| Directory | Purpose |
|-----------|---------|
| `aiscripts/` | All framework scripts (`aitask_*.sh`) |
| `aiscripts/lib/` | Shared library scripts sourced by main scripts |
| `.claude/skills/aitask-*` | Claude Code skill definitions (SKILL.md files) |
| `aitasks/` | Active task files (`t<N>_name.md`) and child task directories (`t<N>/`) |
| `aitasks/new/` | Draft task files (gitignored, local-only) |
| `aiplans/` | Active plan files (`p<N>_name.md`) and child plan directories (`p<N>/`) |
| `aitasks/archived/` | Completed task files and child directories |
| `aiplans/archived/` | Completed plan files and child directories |
| `aitasks/metadata/` | Configuration: `labels.txt`, `task_types.txt`, `emails.txt`, `profiles/` |
| `docs/` | Project documentation (commands, skills, workflows, etc.) |

---

## Library Scripts

Shared utilities in `aiscripts/lib/` are sourced by main scripts. Both libraries use a double-source guard (`[[ -n "${_VAR_LOADED:-}" ]] && return 0`) to prevent duplicate loading.

### lib/task_utils.sh

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

### lib/terminal_compat.sh

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

---

## Atomic Task ID Counter

The internal script `aiscripts/aitask_claim_id.sh` manages a shared atomic counter for task IDs. It is not exposed via the `ait` dispatcher — it is called internally by `aitask_create.sh` during finalization and by `aitask_setup.sh` during initialization.

- A separate git branch `aitask-ids` holds a single file `next_id.txt` as the shared counter
- Atomicity is achieved via git plumbing commands (`hash-object`, `mktree`, `commit-tree`) and push rejection on non-fast-forward updates (compare-and-swap semantics)
- On push conflict (another PC claimed simultaneously), retries with random backoff up to 5 attempts
- Initialized via `ait setup` with a buffer of 10 above the highest existing task ID
- Child tasks do not use the atomic counter — they use local file scan instead, which is safe because the parent's unique ID acts as a namespace and only one PC works on a task at a time

---

## Atomic Task Locking

The internal script `aiscripts/aitask_lock.sh` prevents race conditions when two PCs try to pick the same task simultaneously. It is not exposed via the `ait` dispatcher — it is called internally by the `aitask-pick` skill workflow.

- A separate git orphan branch `aitask-locks` holds per-task lock files (`t<id>_lock.yaml` in YAML format with task ID, email, timestamp, and hostname)
- Atomicity uses the same compare-and-swap approach as the ID counter: git plumbing commands + push rejection on non-fast-forward, with random backoff up to 5 retries
- A task is locked when picked (during status change to "Implementing") and unlocked when archived or aborted
- Locks are idempotent: the same email can refresh its own lock, and unlocking a non-existent lock succeeds silently
- Available commands: `--init`, `--lock <task_id> --email <email>`, `--unlock <task_id>`, `--check <task_id>`, `--list`, `--cleanup`
- The `--cleanup` command removes stale locks for tasks that have already been archived
- Initialized via `ait setup` alongside the atomic ID counter

---

## Modifying Scripts

All framework scripts live in `aiscripts/`. The `ait` dispatcher forwards subcommands to the corresponding `aitask_*.sh` script. Claude Code skills are defined in `.claude/skills/`.

---

## Testing Changes

Run individual commands to verify:

```bash
./ait --version          # Check dispatcher works
./ait ls -v 5            # List tasks
./ait setup              # Re-run dependency setup
bash -n aiscripts/*.sh   # Syntax-check all scripts
```

---

## Release Process

1. Run `/aitask-changelog` in Claude Code to generate the changelog entry for the new version
2. Run `./create_new_release.sh` which bumps the `VERSION` file, creates a git tag, and pushes to trigger the GitHub Actions release workflow
3. Run `/aitask-zipold` to archive old completed task and plan files, keeping the repository clean

---

## Keeping Documentation in Sync

Project documentation lives in the `docs/` directory with the main `README.md` serving as a landing page with links to each section. When adding new features:

1. **New CLI commands** — Add to `docs/commands.md` and update the command summary table
2. **New Claude Code skills** — Add to `docs/skills.md` and update the skill overview table
3. **New workflows** — Add to `docs/workflows.md`
4. **Architectural changes** — Update `docs/development.md`

The `README.md` links to each docs file with a brief summary. If you add a new docs file, add a corresponding link in the Documentation section of README.md.
