---
Task: t461_2_crew_setmode_cli.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_1_*.md, aitasks/t461/t461_3_*.md, aitasks/t461/t461_4_*.md, aitasks/t461/t461_5_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_2 — `ait crew setmode` CLI for existing agents

## Goal

Add a small bash script and `ait` subcommand that mutates the
`launch_mode` field on a Waiting agent's status yaml. Used both from the
command line and from the brainstorm status-tab edit flow (t461_4).

## Files

### New

1. `.aitask-scripts/aitask_crew_setmode.sh`

### Modified

2. `ait` — register `setmode)` subcommand under the `crew)` dispatch
   block (around lines 180-209).

## Implementation steps

### 1. Script skeleton

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
. "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/terminal_compat.sh
. "$SCRIPT_DIR/lib/terminal_compat.sh"

usage() {
    cat <<EOF
Usage: ait crew setmode --crew <id> --name <agent> --mode <headless|interactive>

Change the launch_mode of a Waiting agent in a crew. Refuses to mutate
agents in Running/Completed/Error states.
EOF
}

CREW_ID=""
AGENT_NAME=""
MODE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --crew) CREW_ID="$2"; shift 2;;
        --name) AGENT_NAME="$2"; shift 2;;
        --mode) MODE="$2"; shift 2;;
        -h|--help) usage; exit 0;;
        *) die "Unknown argument: $1";;
    esac
done

[[ -n "$CREW_ID" ]] || die "--crew is required"
[[ -n "$AGENT_NAME" ]] || die "--name is required"
[[ "$MODE" =~ ^(headless|interactive)$ ]] || die "--mode must be headless or interactive"
```

### 2. Locate the status file

Use the same resolution as `aitask_crew_addwork.sh` (probably
`.aitask-crews/crew-${CREW_ID}/${AGENT_NAME}_status.yaml`).

```bash
CREW_DIR=".aitask-crews/crew-${CREW_ID}"
STATUS_FILE="${CREW_DIR}/${AGENT_NAME}_status.yaml"
[[ -f "$STATUS_FILE" ]] || die "No status file: $STATUS_FILE"
```

### 3. Status gate

Read `status:` field from the yaml and refuse if not `Waiting`:

```bash
current_status="$(grep -E '^status:' "$STATUS_FILE" | head -1 | awk '{print $2}' | tr -d '"'"'")"
if [[ "$current_status" != "Waiting" ]]; then
    die "Agent '$AGENT_NAME' is in state '$current_status' — launch_mode only applies to pending launches"
fi
```

### 4. Mutate with `update_yaml_field`

```bash
update_yaml_field "$STATUS_FILE" launch_mode "$MODE"
```

(`update_yaml_field` already exists in `lib/task_utils.sh` — read it to
confirm signature and fallback behavior if the key is not yet present.
If the field is missing, it should be appended.)

### 5. Auto-commit via `./ait git`

```bash
if ./ait git status --porcelain -- "$STATUS_FILE" | grep -q .; then
    ./ait git add "$STATUS_FILE"
    ./ait git commit -m "ait: Set launch_mode=$MODE for crew $CREW_ID agent $AGENT_NAME"
fi
```

### 6. Structured success line

```bash
echo "UPDATED:$AGENT_NAME:$MODE"
```

### 7. Wire `ait` dispatcher

In the `crew)` subcommand switch, add next to `addwork)`:

```bash
setmode)
    exec "$SCRIPT_DIR/.aitask-scripts/aitask_crew_setmode.sh" "$@"
    ;;
```

Update inline help strings to list `setmode` with a one-line
description.

## Verification

1. `shellcheck .aitask-scripts/aitask_crew_setmode.sh` passes.
2. Create a test crew with a Waiting agent. Run
   `./ait crew setmode --crew <id> --name <agent> --mode interactive`.
   Confirm:
   - Exit code 0
   - `launch_mode: interactive` appears in the status file
   - A commit "ait: Set launch_mode=interactive ..." was created
   - Stdout contains `UPDATED:<name>:interactive`
3. Run setmode against a Running agent — should fail with clear error.
4. Run setmode with `--mode verbose` — should fail validation.
5. Run setmode for a non-existent crew/agent — should fail with clear
   "No status file" message.
6. `./ait crew --help` lists `setmode`.

## Dependencies

- Depends on the `launch_mode` schema from t461_1. If t461_1 has not
  been merged yet, the script still works because `update_yaml_field`
  appends the key, but the runner will not honor it until t461_1 lands.

## Notes for sibling tasks

- **t461_4** shells out to this script. Keep the `UPDATED:` line stable
  (machine-readable) — t461_4 parses it to confirm success.
