---
title: "Development Guide"
linkTitle: "Development"
weight: 70
description: "Architecture, internals, and release process"
---

## Architecture

The framework follows a dispatcher pattern. The `ait` script in the project root routes subcommands to individual scripts:

```
ait <subcommand> [args]  →  .aitask-scripts/aitask_<subcommand>.sh [args]
```

## Directory Layout

| Directory | Purpose |
|-----------|---------|
| `.aitask-scripts/` | All framework scripts (`aitask_*.sh`) |
| `.aitask-scripts/lib/` | Shared library scripts sourced by main scripts |
| `.claude/skills/aitask-*` | Primary skill definitions (SKILL.md files) |
| `aitasks/` | Active task files (`t<N>_name.md`) and child task directories (`t<N>/`) |
| `aitasks/new/` | Draft task files (gitignored, local-only) |
| `aiplans/` | Active plan files (`p<N>_name.md`) and child plan directories (`p<N>/`) |
| `aitasks/archived/` | Completed task files and child directories |
| `aitasks/archived/_bN/` | Numbered archive bundles (`old0.tar.gz` through `old9.tar.gz` per directory) |
| `aiplans/archived/` | Completed plan files and child directories |
| `aitasks/metadata/` | Configuration: `labels.txt`, `task_types.txt`, `emails.txt`, `profiles/` |
| `aireviewguides/` | Review guide files, vocabulary metadata, and environment subdirectories |
| `website/content/docs/` | Project documentation (single source of truth) |

---

## Library Scripts

Shared utilities in `.aitask-scripts/lib/` are sourced by main scripts. Both libraries use a double-source guard (`[[ -n "${_VAR_LOADED:-}" ]] && return 0`) to prevent duplicate loading.

### lib/task_utils.sh

Task and plan file resolution utilities. Sources `terminal_compat.sh` automatically.

**Directory variables** (override before sourcing if needed):

- `TASK_DIR` — Active task directory (default: `aitasks`)
- `ARCHIVED_DIR` — Archived task directory (default: `aitasks/archived`)
- `PLAN_DIR` — Active plan directory (default: `aiplans`)
- `ARCHIVED_PLAN_DIR` — Archived plan directory (default: `aiplans/archived`)

**Functions:**

- **`resolve_task_file(task_id)`** — Find a task file by number (e.g., `"53"` or `"53_6"`). Searches active directory first, then archived loose files, then numbered archives (`_bN/oldM.tar.gz`), with legacy `old.tar.gz` fallback. Dies if not found or if multiple matches exist.
- **`resolve_plan_file(task_id)`** — Find the corresponding plan file using `t→p` prefix conversion (e.g., `t53_name.md` → `p53_name.md`). Searches the same three tiers as `resolve_task_file`. Returns empty string if not found.
- **`extract_issue_url(file_path)`** — Parse the `issue:` field from a task file's YAML frontmatter. Returns empty string if not present.
- **`extract_final_implementation_notes(plan_path)`** — Extract the `## Final Implementation Notes` section from a plan file. Stops at the next `##` heading. Trims leading/trailing blank lines.

### lib/archive_utils.sh

Archive path computation and search/extract primitives for the numbered archive scheme.

**Functions:**

- **`archive_bundle(task_id)`** — Compute bundle number (`task_id / 100`)
- **`archive_dir(bundle)`** — Compute directory number (`bundle / 10`)
- **`archive_path_for_id(task_id, archived_dir)`** — Full archive path for a task ID (e.g., task 150 → `archived/_b0/old1.tar.gz`)

### lib/archive_scan.sh

Consolidated archive scanning functions for numbered archives.

**Functions:**

- **`scan_max_task_id(task_dir, archived_dir)`** — Find highest task ID across all locations (active, archived loose, numbered archives, legacy)
- **`search_archived_task(task_num, archived_dir)`** — Search for a task in numbered and legacy archives using O(1) lookup

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

The internal script `.aitask-scripts/aitask_claim_id.sh` manages a shared atomic counter for task IDs. It is not exposed via the `ait` dispatcher — it is called internally by `aitask_create.sh` during finalization and by `aitask_setup.sh` during initialization.

- A separate git branch `aitask-ids` holds a single file `next_id.txt` as the shared counter
- Atomicity is achieved via git plumbing commands (`hash-object`, `mktree`, `commit-tree`) and push rejection on non-fast-forward updates (compare-and-swap semantics)
- On push conflict (another PC claimed simultaneously), retries with random backoff up to 5 attempts
- Initialized via `ait setup` to one above the highest existing task ID (so new projects start at t1)
- Child tasks do not use the atomic counter — they use local file scan instead, which is safe because the parent's unique ID acts as a namespace and only one PC works on a task at a time

---

## Atomic Task Locking

The internal script `.aitask-scripts/aitask_lock.sh` prevents race conditions when two PCs try to pick the same task simultaneously. It is not exposed via the `ait` dispatcher — it is called internally by the `aitask-pick` skill workflow.

- A separate git orphan branch `aitask-locks` holds per-task lock files (`t<id>_lock.yaml` in YAML format with task ID, email, timestamp, and hostname)
- Atomicity uses the same compare-and-swap approach as the ID counter: git plumbing commands + push rejection on non-fast-forward, with random backoff up to 5 retries
- A task is locked when picked (during status change to "Implementing") and unlocked when archived or aborted
- Locks are idempotent: the same email can refresh its own lock, and unlocking a non-existent lock succeeds silently
- Available commands: `--init`, `--lock <task_id> --email <email>`, `--unlock <task_id>`, `--check <task_id>`, `--list`, `--cleanup`
- The `--cleanup` command removes stale locks for tasks that have already been archived. It runs before every task pick, and reports its outcome rather than always exiting 0: exit `11` means the lock branch could not be read, exit `12` means the removal push was rejected on every retry. Both warn on stderr and name what was left uncleaned. The pick itself is never blocked — a failed sweep is forwarded as a warning and the workflow continues
- Initialized via `ait setup` alongside the atomic ID counter

---

## Task Data Branch

When enabled via `ait setup`, task and plan files can live on a separate orphan branch `aitask-data` instead of the main code branch. This separates task management commits from implementation commits, reducing noise in `git log` and avoiding merge conflicts when multiple PCs update tasks independently.

- An orphan git branch `aitask-data` holds all files under `aitasks/` and `aiplans/`
- A permanent git worktree at `.aitask-data/` provides filesystem access to the branch
- Symlinks `aitasks → .aitask-data/aitasks` and `aiplans → .aitask-data/aiplans` keep all existing paths working transparently
- The CLI command `ait git` routes git operations to the correct branch: in branch mode it runs `git -C .aitask-data`, in legacy mode it passes through to plain `git`
- Shell scripts use `task_git()` from `task_utils.sh` internally; the Python TUI board uses its own `_task_git_cmd()` helper — both auto-detect the active mode
- Initialized via `ait setup` alongside the atomic ID counter and task locking

---

## Development Dependencies

### ShellCheck

[ShellCheck](https://www.shellcheck.net/) is required for linting shell scripts during development.

| Platform | Command |
|----------|---------|
| macOS (Homebrew) | `brew install shellcheck` |
| Ubuntu / Debian | `sudo apt install shellcheck` |
| Arch Linux | `sudo pacman -S shellcheck` |

### Hugo (for website development)

The documentation website uses [Hugo](https://gohugo.io/) with the Docsy theme. Hugo **extended edition** is required along with Go, Dart Sass, and Node.js.

| Platform | Command |
|----------|---------|
| macOS (Homebrew) | `brew install hugo go sass/sass/sass node` |
| Ubuntu / Debian | See [detailed instructions](https://github.com/beyondeye/aitasks/blob/main/website/README.md#ubuntu--debian) (Hugo requires manual `.deb` install for extended edition) |
| Arch Linux | `sudo pacman -S hugo go dart-sass nodejs npm` |

After installing, run `cd website && npm install` for Node.js dependencies. See [`website/README.md`](https://github.com/beyondeye/aitasks/blob/main/website/README.md) for full setup, verification, and troubleshooting.

---

## Modifying Scripts

All framework scripts live in `.aitask-scripts/`. The `ait` dispatcher forwards subcommands to the corresponding `aitask_*.sh` script. Primary skill definitions live in `.claude/skills/`, with wrappers for other agents generated from or aligned to those sources.

---

## Testing Changes

Run individual commands to verify:

```bash
./ait --version                    # Check dispatcher works
./ait ls -v 5                      # List tasks
./ait setup                        # Re-run dependency setup
bash -n .aitask-scripts/*.sh             # Syntax-check all scripts
shellcheck .aitask-scripts/aitask_*.sh   # Lint all scripts
```

### Bash tests

Bash tests have no runner — each file under `tests/` is self-contained and prints its own PASS/FAIL summary. Run them one at a time:

```bash
bash tests/test_claim_id.sh
```

A test file whose bodies run inside `( … )` subshells must opt into the
file-backed counters from `tests/lib/asserts.sh`: call `assert_counters_init`
after sourcing the library, and `assert_counters_load` in the footer before the
`[[ "$FAIL" -eq 0 ]]` guard. The shared assertion helpers mutate in-process
`PASS`/`FAIL`/`TOTAL` counters, which do not survive a subshell — without the
opt-in, a file reports zero failures and exits 0 however many assertions failed.

### Python tests

The Python tests do have an aggregate runner:

```bash
bash tests/run_all_python_tests.sh                    # whole suite
bash tests/run_all_python_tests.sh --test-dir <dir>   # a subset
```

It runs on `pytest` when that is importable and falls back to the standard library's `unittest discover` otherwise, so the suite works on a default install.

**Read only the last line for the verdict.** It is written to stderr in the form `PYTHON SUITE: PASSED (runner=pytest, exit=0)` — or `FAILED` — and is derived from the backend's real exit status. A `Results: N passed, 0 failed` line earlier in the output belongs to a single test module, not to the suite. Piping discards the exit status (`… | tail` exits with `tail`'s `0` whatever the suite did), so use `set -o pipefail` or check `${PIPESTATUS[0]}`; the verdict line itself survives `2>&1 | tail` because it goes to stderr.

#### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AIT_TEST_WORKERS` | Auto — 4 or 2 | Worker count for the parallel lane. The default is load-aware: 4 when the machine has at least 4 CPUs and a 1-minute load average at or below half of them, otherwise 2. An explicit value always wins, and the runner prints the count it auto-selected. |
| `AIT_TEST_PARALLEL` | `1` | Set to `0` to run the suite serially. |

**What switches the parallel lane on.** The runner resolves its interpreter to the `ait setup` virtual environment at `~/.aitask/venv/` rather than a bare `python3`. It selects pytest when `pytest` is importable there, and enables the parallel lane (`-n <workers> --dist loadfile`, with a small serial carve-out) whenever `pytest-xdist` is importable too. `ait setup --with-dev` is the supported way to install both into that venv; it also records a marker so later plain `ait setup` runs revalidate and repair the tier. The runner never reads that marker — it simply checks whether `pytest-xdist` can be imported.

**Opting out is two independent actions.** `AIT_TEST_PARALLEL=0` disables the lane while leaving the packages installed; deleting the marker at `~/.aitask/dev_tier` stops `ait setup` reinstalling or repairing the tier while leaving the lane running. Removing the tier entirely means both, plus uninstalling `pytest` and `pytest-xdist` from the venv.

**Narrow a run with `--test-dir`, not a path.** A positional test path is forwarded to every phase, which *widens* the run and disables the parallel lane along with its serial carve-out.

---

## Release Process

1. Run `/aitask-changelog` in your configured code agent session to generate the changelog entry for the new version
2. Run `./create_new_release.sh` which bumps the `VERSION` file, creates a git tag, and pushes to trigger the GitHub Actions release workflow
3. Run `./ait zip-old` to archive old completed task and plan files, keeping the repository clean

---

## Keeping Documentation in Sync

Project documentation lives in `website/content/docs/` — the Hugo/Docsy website is the single source of truth. When adding new features:

1. **New CLI commands** — Add to the appropriate file under `website/content/docs/commands/`
2. **New code agent skills** — Add a new file under `website/content/docs/skills/`
3. **New workflows** — Add to `website/content/docs/workflows.md`
4. **Architectural changes** — Update `website/content/docs/development/_index.md`

The `README.md` links to each docs file with a brief summary. If you add a new docs section, add a corresponding link in the Documentation section of README.md.
