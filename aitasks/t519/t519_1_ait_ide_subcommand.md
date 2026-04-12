---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [tmux, cli]
created_at: 2026-04-12 15:14
updated_at: 2026-04-12 15:14
---

## Context

Part of t519 (website docs rewrite for tmux integration). The current startup for the aitasks "IDE" is a 4-step manual sequence: open terminal → `cd` to project → `tmux` → `ait monitor`. This is bad UX and has a subtle bug: when tmux is started without an explicit session name, the session name will not match the configured `default_session` in `aitasks/metadata/project_config.yaml`, forcing `ait monitor` to offer a `SessionRenameDialog` fallback (`monitor_app.py` lines 118–165, 402–435).

A new `ait ide` subcommand collapses steps 3–4 into one command and always passes an explicit session name so the rename dialog never fires on the happy path. This is the **critical-path child** for t519: subsequent doc rewrites (t519_2, t519_3) reference `ait ide` by name as the recommended entry point.

## Key Files to Modify

- `.aitask-scripts/aitask_ide.sh` (new) — the implementation script. `#!/usr/bin/env bash` with `set -euo pipefail`, sources `terminal_compat.sh` for `die/warn/info`.
- `ait` (dispatcher, repo root) — add `ide` to the case branch that dispatches subcommands, add to `show_usage()` help text, and to any skip-update-check allowlist if one exists around lines 22–28 and 150.
- `website/content/docs/commands/_index.md` (or whichever file lists commands in the Docsy site; verify during implementation) — add an `ait ide` entry so the commands reference stays consistent. This is a small one-paragraph insertion, NOT a full command reference page.

## Reference Files for Patterns

- `.aitask-scripts/monitor/monitor_app.py` lines 1019–1074 — session-name resolution logic: CLI arg > TMUX env > configured `default_session` > hardcoded `"aitasks"`. `ait ide` should use the same precedence when picking a session name.
- `.aitask-scripts/monitor/monitor_app.py` lines 118–165, 402–435 — the `SessionRenameDialog` code path that `ait ide` sidesteps.
- `.aitask-scripts/lib/agent_launch_utils.py` `load_tmux_defaults()` around line 125+ — how other scripts read `tmux.default_session` from `project_config.yaml`. Use the same helper if it's bash-callable, otherwise parse `project_config.yaml` with a small Python one-liner or `yq`/`awk`.
- Any existing simple wrapper script in `.aitask-scripts/aitask_*.sh` (e.g., `aitask_board.sh`, `aitask_monitor.sh`) as a structural model — shebang, `set -euo pipefail`, sourcing, error helpers.

## Implementation Plan

### Step 1 — Create `.aitask-scripts/aitask_ide.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# Parse --session NAME override
SESSION_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --session)
      SESSION_OVERRIDE="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat <<EOF
Usage: ait ide [--session NAME]

Starts (or attaches to) the configured tmux session and launches ait monitor.

Options:
  --session NAME   Use NAME instead of the configured default_session.
  -h, --help       Show this help.
EOF
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

# Resolve session name
resolve_session() {
  if [[ -n "$SESSION_OVERRIDE" ]]; then
    echo "$SESSION_OVERRIDE"
    return
  fi
  local cfg="aitasks/metadata/project_config.yaml"
  if [[ -f "$cfg" ]]; then
    local name
    name=$(awk '/^tmux:/{intmux=1;next} intmux && /^  default_session:/ {print $2; exit} /^[a-zA-Z]/{intmux=0}' "$cfg" | tr -d '"'"'")
    if [[ -n "$name" ]]; then
      echo "$name"
      return
    fi
  fi
  echo "aitasks"
}

SESSION=$(resolve_session)

# Require tmux
command -v tmux >/dev/null || die "tmux is not installed — install it first (see docs)"

# Inside tmux?
if [[ -n "${TMUX:-}" ]]; then
  current_session=$(tmux display-message -p '#S')
  if [[ "$current_session" != "$SESSION" ]]; then
    warn "Already inside tmux session '$current_session' but configured session is '$SESSION'."
    warn "Refusing to nest. Either detach (Ctrl-b d) and re-run, or pass --session $current_session."
    exit 1
  fi
  # Matching session — ensure a monitor window exists, then select it
  if tmux list-windows -F '#{window_name}' | grep -qx 'monitor'; then
    tmux select-window -t "$SESSION:monitor"
  else
    tmux new-window -n monitor 'ait monitor'
  fi
  exit 0
fi

# Not inside tmux — attach or create
if tmux has-session -t "$SESSION" 2>/dev/null; then
  # Ensure monitor window exists
  if ! tmux list-windows -t "$SESSION" -F '#{window_name}' | grep -qx 'monitor'; then
    tmux new-window -t "$SESSION:" -n monitor 'ait monitor'
  fi
  exec tmux attach -t "$SESSION" \; select-window -t "$SESSION:monitor"
else
  exec tmux new-session -s "$SESSION" -n monitor 'ait monitor'
fi
```

**Notes:**
- The `awk`-based `default_session` parser is a pragmatic workaround. If `project_config.yaml` has more structure, prefer a Python helper or `yq`. Verify the exact format of `aitasks/metadata/project_config.yaml` during implementation.
- Check whether a shared helper for parsing `tmux.default_session` from bash already exists (grep `default_session` in `.aitask-scripts/lib/`). If so, use it instead of duplicating the parser.
- `chmod +x` the script after creating.

### Step 2 — Dispatcher integration

Edit the `ait` script at the repo root:

1. Add `ide` to the `show_usage()` help text (TUI/command section, around lines 22–28).
2. Add a case branch dispatching `ide)` to `exec ".aitask-scripts/aitask_ide.sh" "$@"`.
3. If `ait` has a skip-update-check allowlist (check around line 150), add `ide` to it since `ait ide` is a fast-start command.

Use `./.aitask-scripts/aitask_ide.sh` exec, following the exact pattern of an existing simple subcommand like `ait board` or `ait monitor`.

### Step 3 — Commands reference doc update

Grep the website content for existing ait-command documentation:
```bash
grep -rl "ait board\|ait monitor" website/content/docs/commands/ website/content/docs/installation/ 2>/dev/null
```

Add a short entry for `ait ide` in the most natural location (likely `website/content/docs/commands/_index.md` if it exists, otherwise defer to t519_2 which rewrites `installation/terminal-setup.md`). Keep it minimal — a one-paragraph description and a reference to the terminal-setup page for the full workflow.

**If no `commands/` docs exist at all:** skip this step and let t519_2 cover the user-visible documentation of the command.

## Verification

- `./ait ide --help` prints usage.
- From a plain shell (no `$TMUX`): `./ait ide` creates a tmux session with the configured name and opens `ait monitor`. Detach (Ctrl-b d) and verify `tmux ls` shows the session with the configured name.
- Re-run `./ait ide` while detached: it attaches to the existing session and focuses the monitor window instead of creating a duplicate monitor.
- From inside a tmux session named `aitasks` (matching): `./ait ide` creates a new `monitor` window in the current session.
- From inside a tmux session with a DIFFERENT name: `./ait ide` prints a warning and exits 1 without nesting.
- `./ait ide --session alt_name` uses `alt_name` instead of the configured default.
- `shellcheck .aitask-scripts/aitask_ide.sh` passes clean.
- `./ait` (no args) shows `ide` in the help output.

## Step 9 — Post-Implementation

Part of t519 — follow the shared task-workflow post-implementation flow. The follow-up screenshot task (including `aitasks_ait_ide_startup.svg`) is created at the parent's archival time, not here.
