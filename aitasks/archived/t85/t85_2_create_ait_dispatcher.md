---
priority: high
effort: low
depends: [t85_1]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 12:13
completed_at: 2026-02-11 12:13
---

## Context

This is child task 2 of parent task t85 (Cross-Platform aitask Framework Distribution). The `ait` script is the single entry point for the aitask framework. Instead of users typing `./aitask_create.sh`, they type `ait create`. The dispatcher lives at the project root and forwards subcommands to the appropriate script in `aiscripts/`.

This script will be created in the `beyondeye/aitasks` repo (at `~/Work/aitasks/ait`). After t85_1 has initialized the repo, this task fills in the `ait` file.

## What to Do

### Create the `ait` dispatcher script

**File**: `~/Work/aitasks/ait`

The script must:

1. **Determine its own location** using `BASH_SOURCE[0]` to find the project root
2. **`cd` to its own directory** before dispatching — this is CRITICAL because all aitask bash scripts use `TASK_DIR="aitasks"` as a relative path from the project root. If the user runs `ait` from a subdirectory, the scripts would look for `aitasks/` in the wrong place without this `cd`.
3. **Dispatch subcommands** via a `case` statement using `exec` (replaces the shell process cleanly)
4. **Support `--version`** by reading the `VERSION` file
5. **Support `help`** with a usage message listing all commands

### Subcommand mapping

| Subcommand | Script |
|------------|--------|
| `create` | `aiscripts/aitask_create.sh` |
| `ls` | `aiscripts/aitask_ls.sh` |
| `update` | `aiscripts/aitask_update.sh` |
| `import` | `aiscripts/aitask_import.sh` |
| `board` | `aiscripts/aitask_board.sh` |
| `stats` | `aiscripts/aitask_stats.sh` |
| `clear-old` | `aiscripts/aitask_clear_old.sh` |
| `issue-update` | `aiscripts/aitask_issue_update.sh` |
| `setup` | `aiscripts/aitask_setup.sh` |
| `help` / `--help` / `-h` | Print usage |
| `--version` / `-v` | Print version from VERSION file |
| (no args) | Print usage |
| (unknown) | Print error + usage hint |

### Key design patterns

```bash
#!/usr/bin/env bash
set -euo pipefail

AIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AIT_DIR"  # CRITICAL: ensures TASK_DIR="aitasks" works in all scripts

SCRIPTS_DIR="$AIT_DIR/aiscripts"
```

For dispatching, use `exec` so the subprocess replaces the current shell (clean PID, proper signal forwarding):
```bash
case "${1:-help}" in
    create) shift; exec "$SCRIPTS_DIR/aitask_create.sh" "$@" ;;
    ...
esac
```

For version:
```bash
show_version() {
    local version_file="$AIT_DIR/VERSION"
    if [[ -f "$version_file" ]]; then
        echo "ait version $(cat "$version_file")"
    else
        echo "ait version unknown"
    fi
}
```

### Make executable

```bash
chmod +x ~/Work/aitasks/ait
```

### Commit

```bash
cd ~/Work/aitasks
git add ait
git commit -m "Add ait dispatcher script"
```

## Verification

1. `cd ~/Work/aitasks && ./ait --version` prints `ait version 0.1.0`
2. `./ait help` prints usage with all subcommands listed
3. `./ait unknowncmd` prints an error and suggests `ait help`
4. `./ait` (no args) prints usage
