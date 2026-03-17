---
Task: t411_fix_crew_script_permissions_and_help.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Fix crew script permissions and add missing help text

## Context

Two `ait crew` scripts (`init`, `addwork`) are missing executable permissions, causing "Permission denied" errors. Additionally, four thin-wrapper scripts (`runner`, `status`, `report`, `dashboard`) lack `--help` handling, and `ait crew` with no subcommand shows an unhelpful error.

## Changes

### 1. Fix executable permissions

```bash
chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
```

### 2. Add `--help` to thin wrapper scripts

Each of these scripts ends with `exec "$PYTHON" ... "$@"`, so `--help` would technically pass through to Python. But intercepting `--help` in bash is better because:
- It works even when Python/deps are missing
- It documents the bash-level usage (the `ait crew <sub>` interface)

Add a `--help|-h` check before the Python exec in each script, using the usage info from the file header comment:

**`.aitask-scripts/aitask_crew_runner.sh`** — Add before `exec` line:
```bash
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait crew runner --crew <id> [--interval N] [--max-concurrent N] [--once] [--dry-run] [--check] [--force]"
    echo ""
    echo "Start or check the crew runner orchestrator."
    exit 0
fi
```

**`.aitask-scripts/aitask_crew_status.sh`** — Same pattern:
```bash
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait crew status --crew <id> [--agent <name>] <get|set|list|heartbeat> [options]"
    echo ""
    echo "Get or set agent and crew status."
    exit 0
fi
```

**`.aitask-scripts/aitask_crew_report.sh`** — Same pattern:
```bash
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait crew report [--batch] <summary|detail|output|list> [options]"
    echo ""
    echo "Report crew summary, agent details, and outputs."
    exit 0
fi
```

**`.aitask-scripts/aitask_crew_dashboard.sh`** — Same pattern:
```bash
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait crew dashboard [options]"
    echo ""
    echo "TUI dashboard for monitoring and managing crews."
    exit 0
fi
```

### 3. Handle bare `ait crew` (no subcommand)

In `ait` (line 165-177), when `subcmd` is empty, show the available subcommands instead of an error. Change the `*)` case in the crew block to also catch the empty string, and add a dedicated empty-string case:

```bash
"")            echo "Usage: ait crew <subcommand> [options]"; echo ""; echo "Available subcommands:"; echo "  init        Initialize a new agentcrew"; echo "  addwork     Add an agent to an existing crew"; echo "  status      Get/set agent and crew status"; echo "  command     Send commands to agents"; echo "  runner      Start/check the crew runner orchestrator"; echo "  report      Report crew summary, agent details, outputs"; echo "  cleanup     Remove completed crew worktrees and branches"; echo "  dashboard   TUI dashboard for monitoring and managing crews"; echo ""; echo "Run 'ait crew <subcommand> --help' for subcommand-specific help."; exit 0 ;;
```

## Files to modify

1. `.aitask-scripts/aitask_crew_init.sh` — chmod +x only
2. `.aitask-scripts/aitask_crew_addwork.sh` — chmod +x only
3. `.aitask-scripts/aitask_crew_runner.sh` — add --help block
4. `.aitask-scripts/aitask_crew_status.sh` — add --help block
5. `.aitask-scripts/aitask_crew_report.sh` — add --help block
6. `.aitask-scripts/aitask_crew_dashboard.sh` — add --help block
7. `ait` — handle bare `ait crew` with empty subcommand

## Verification

```bash
# Test permissions
ait crew init --help
ait crew addwork --help

# Test new help text
ait crew runner --help
ait crew status --help
ait crew report --help
ait crew dashboard --help

# Test bare ait crew
ait crew
```

## Post-Review Changes

### Change Request 1 (2026-03-17)
- **Requested by user:** Add `--help` suggestion to error messages when required args are missing
- **Changes made:** Added "Run 'ait crew <subcmd> --help' for usage." to all `die` messages for missing required arguments in: `addwork`, `cleanup`, `command` (including sub-commands send, send-all, list, ack)
- **Files affected:** `aitask_crew_addwork.sh`, `aitask_crew_cleanup.sh`, `aitask_crew_command.sh`

## Final Implementation Notes
- **Actual work done:** All three planned changes plus help suggestions in error messages
- **Deviations from plan:** Added help suggestions to error messages (user feedback)
- **Issues encountered:** None
- **Key decisions:** Added `--help|-h` to the crew case block in `ait` alongside empty string, so `ait crew --help` also works

## Step 9: Post-Implementation

Archive task, push changes.
