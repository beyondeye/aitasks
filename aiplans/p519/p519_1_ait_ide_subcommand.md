---
Task: t519_1_ait_ide_subcommand.md
Parent Task: aitasks/t519_rewrite_of_website_for_tmux_integration.md
Sibling Tasks: aitasks/t519/t519_2_*.md, aitasks/t519/t519_3_*.md, aitasks/t519/t519_4_*.md, aitasks/t519/t519_5_*.md, aitasks/t519/t519_6_*.md
Archived Sibling Plans: (none yet — this is the first child)
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan — t519_1: New `ait ide` subcommand

## Goal

Create a new `ait ide` subcommand that bundles tmux session startup/attachment + `ait monitor` launch into a single command, eliminating the ugly 4-step manual startup (terminal → cd → tmux → ait monitor) and sidestepping the `SessionRenameDialog` fallback in `monitor_app.py`.

## Critical-path note

This is the blocker for t519_2 (terminal-setup rewrite) and t519_3 (getting-started update). Both of those docs refer to `ait ide` by name, so this child must land first.

## Step-by-step implementation

### Step 1 — Verify exact `project_config.yaml` structure for `tmux.default_session`

```bash
cat aitasks/metadata/project_config.yaml
```

Confirm the structure is:
```yaml
tmux:
  default_session: aitasks
  ...
```

If the format differs (e.g., flat keys), adjust the parser in Step 3 accordingly.

### Step 2 — Check whether a bash helper already exists for reading `tmux.default_session`

```bash
grep -rn "default_session" .aitask-scripts/lib/ .aitask-scripts/*.sh 2>/dev/null | head -30
```

If a shared parser function exists, use it. If not, write a small inline parser in Step 3.

### Step 3 — Create `.aitask-scripts/aitask_ide.sh`

Template (adapt to exact conventions found in Step 2):

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

SESSION_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --session)
      SESSION_OVERRIDE="${2:-}"
      [[ -z "$SESSION_OVERRIDE" ]] && die "--session requires a name"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ait ide [--session NAME]

Starts (or attaches to) the configured tmux session and launches ait monitor.

Options:
  --session NAME   Use NAME instead of the configured default_session.
  -h, --help       Show this help.
EOF
      exit 0
      ;;
    *)
      die "Unknown option: $1 (try --help)"
      ;;
  esac
done

resolve_session() {
  if [[ -n "$SESSION_OVERRIDE" ]]; then
    echo "$SESSION_OVERRIDE"
    return
  fi
  local cfg="aitasks/metadata/project_config.yaml"
  if [[ -f "$cfg" ]]; then
    # Minimal YAML parser for tmux.default_session — adjust based on actual format
    local name
    name=$(awk '
      /^tmux:/ { intmux=1; next }
      intmux && /^  default_session:/ {
        sub(/^  default_session:[ \t]*/, "")
        gsub(/"/, "")
        gsub(/'"'"'/, "")
        print
        exit
      }
      /^[^ ]/ && !/^tmux:/ { intmux=0 }
    ' "$cfg")
    if [[ -n "$name" ]]; then
      echo "$name"
      return
    fi
  fi
  echo "aitasks"
}

SESSION=$(resolve_session)

command -v tmux >/dev/null || die "tmux is not installed. Install it first, then re-run 'ait ide'."

if [[ -n "${TMUX:-}" ]]; then
  current_session=$(tmux display-message -p '#S')
  if [[ "$current_session" != "$SESSION" ]]; then
    warn "Already inside tmux session '$current_session', but configured session is '$SESSION'."
    warn "Refusing to nest tmux. Either detach (Ctrl-b d) and re-run 'ait ide', or"
    warn "pass '--session $current_session' to use the current session."
    exit 1
  fi
  if tmux list-windows -F '#{window_name}' | grep -qx 'monitor'; then
    exec tmux select-window -t "$SESSION:monitor"
  else
    exec tmux new-window -n monitor 'ait monitor'
  fi
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  if ! tmux list-windows -t "$SESSION" -F '#{window_name}' | grep -qx 'monitor'; then
    tmux new-window -t "$SESSION:" -n monitor 'ait monitor'
  fi
  exec tmux attach -t "$SESSION" \; select-window -t "$SESSION:monitor"
fi

exec tmux new-session -s "$SESSION" -n monitor 'ait monitor'
```

Make it executable: `chmod +x .aitask-scripts/aitask_ide.sh`.

### Step 4 — Wire into the `ait` dispatcher

1. Open `ait` (repo root).
2. Find the case statement that dispatches subcommands. Look at how `board` and `monitor` are dispatched.
3. Add a branch:
   ```bash
   ide)
     exec ".aitask-scripts/aitask_ide.sh" "$@"
     ;;
   ```
4. Find `show_usage()` (around lines 22–28). Add a line for `ide` in the appropriate section:
   ```
   ide        Start (or attach to) the tmux session and launch monitor
   ```
5. If there's a skip-update-check allowlist around line 150, add `ide` to it so `ait ide` starts fast.

### Step 5 — Commands reference doc (optional, small)

Check whether a commands reference page exists:

```bash
ls website/content/docs/commands/ 2>/dev/null
```

If `commands/_index.md` or similar exists and lists commands, add a short entry for `ait ide`. If no such page exists, skip this step — t519_2 will cover the user-visible docs of the command in `terminal-setup.md`.

### Step 6 — Verification

1. `shellcheck .aitask-scripts/aitask_ide.sh` — no warnings.
2. `./ait ide --help` — prints usage.
3. `./ait` (no args) — `ide` appears in help text.
4. From a plain shell (outside tmux):
   ```bash
   ./ait ide
   ```
   Expect: new tmux session created with name `aitasks` (or whatever `project_config.yaml` says), window `monitor` running `ait monitor`, attached.
5. Detach (`Ctrl-b d`), run `tmux ls` — verify session named `aitasks` exists with a `monitor` window.
6. Re-run `./ait ide` — should attach to existing session and select the `monitor` window, no duplicate monitor window.
7. From inside tmux with matching session name:
   - Create a test: `tmux new-session -s aitasks` (or detach and re-attach).
   - Run `./ait ide` from inside — a new `monitor` window is created (or focused), no nesting.
8. From inside tmux with a DIFFERENT session name:
   - `tmux new-session -s other`
   - Run `./ait ide` from inside — prints warning, exits 1, does not nest.
9. `./ait ide --session custom_name` — uses `custom_name` instead of the default.

### Step 7 — Final plan notes

Add a Final Implementation Notes section at the end of this plan before archival:
- What was actually implemented (the script logic may evolve from the template during implementation).
- Any deviations from the template (e.g., if an existing bash helper was used for YAML parsing).
- Any issues with the dispatcher integration.
- Shared code created (e.g., if a new helper was added to `lib/`).
- Notes useful for t519_2/t519_3 (e.g., finalized command name / flags that docs should reference).

## Files to create

- `.aitask-scripts/aitask_ide.sh` (new, executable)

## Files to modify

- `ait` (dispatcher)
- `website/content/docs/commands/_index.md` (optional — only if an analogous commands reference exists)

## Out of scope (do NOT do in this child)

- Any rewrite of `terminal-setup.md` (that's t519_2).
- Any updates to `getting-started.md` or a new `workflows/tmux-ide.md` page (that's t519_3).
- Documentation of `ait monitor` itself (that's t519_4).
- `--force-nest` flag (deferred to a future task if anyone actually needs it).
