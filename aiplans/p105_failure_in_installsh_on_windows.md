---
Task: t105_failure_in_installsh_on_windows.md
---

## Context

When running `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash` on Windows (WSL), the installation fails silently at the "Install these Claude Code permissions? [Y/n]" prompt. This happens because `install.sh` calls `ait setup` at line 376, but `aitask_setup.sh` uses `read -r` without TTY checks. When piped via curl, stdin is the pipe (not the terminal), `read` gets EOF, and `set -euo pipefail` causes silent exit.

The README (line 87) already documents `ait setup` as a separate post-install step.

## Plan

### 1. Remove the `ait setup` call from `install.sh`

- Remove lines 373-376 (`info "Running ait setup..."` / `(cd "$INSTALL_DIR" && ./ait setup)`)
- Add a reminder message in the success output: "Next step: run 'ait setup' to install dependencies..."
- Reorder Quick start to list `ait setup` first

### 2. Add TTY checks to `aitask_setup.sh` interactive prompts

Defensive improvement — wrap 3 prompt blocks with `[[ -t 0 ]]` checks:
- ~Line 248: "Initialize a git repository here? [Y/n]"
- ~Line 270: "Commit these files? [Y/n]"
- ~Line 394: "Install these Claude Code permissions? [Y/n]"

Auto-accept default (Y) when non-interactive with info message.

## Verification

- [x] `bash -n install.sh` — syntax OK
- [x] `bash -n aiscripts/aitask_setup.sh` — syntax OK

## Final Implementation Notes
- **Actual work done:** Removed `ait setup` call from `install.sh` and added TTY checks to all 3 interactive prompts in `aitask_setup.sh`, matching the pattern already used in `install.sh`.
- **Deviations from plan:** None — implemented as planned.
- **Issues encountered:** None.
- **Key decisions:** Used `[[ -t 0 ]]` pattern (consistent with `install.sh` lines 103, 308) rather than `/dev/tty` redirection. Auto-accepts default (Y) with info message when non-interactive.
