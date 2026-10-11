#!/usr/bin/env bash
# agent_string.sh - Single source of truth for agent-string parsing and
# model/binary/flag resolution. Sourceable from any aitask script that
# needs to translate "<agent>/<model>" into the per-CLI invocation triple
# (binary, model_flag, cli_id).
#
# Provides:
#   SUPPORTED_AGENTS           (array of canonical agent names)
#   CODEX_TUI_OVERRIDES        (array of `-c` pairs every Codex launch carries)
#   DEFAULT_AGENT_STRING       (claudecode/opus5_5 at time of writing)
#   METADATA_DIR               (defaults to ${TASK_DIR:-aitasks}/metadata)
#   PARSED_AGENT / PARSED_MODEL (set by parse_agent_string)
#   parse_agent_string <s>     (sets PARSED_AGENT, PARSED_MODEL; dies on bad input)
#   get_cli_binary <agent>     (e.g. claudecode -> claude)
#   get_model_flag <agent>     (e.g. claudecode -> --model)
#   get_cli_model_id <agent> <model>  (reads models_<agent>.json via jq)
#   require_jq                 (dies if jq is missing)

[[ -n "${_AIT_AGENT_STRING_LOADED:-}" ]] && return 0
_AIT_AGENT_STRING_LOADED=1

# shellcheck source=terminal_compat.sh
source "$(dirname "${BASH_SOURCE[0]}")/terminal_compat.sh"

# --- Constants (caller may pre-set any of these to override) ---

DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus5_5}"
METADATA_DIR="${METADATA_DIR:-${TASK_DIR:-aitasks}/metadata}"
SUPPORTED_AGENTS=(claudecode codex opencode)

# Codex TUI overrides carried by EVERY framework Codex launch: both argv
# builders (aitask_codeagent.sh, every `invoke` operation and the
# `--resume-session` restore arm; aitask_skillrun.sh) expand this one array, so
# no launcher repeats a setting. A `-c` override outranks every config file, so
# these hold whatever the user or project config says.
#
#  * tui.whimsy=false + tui.effects.starfield=false (t1797, narrowed by
#    t1944). Codex animates a Braille "starfield" (U+2800-U+28FF) around and
#    inside the idle composer for Astra-family models; the glyphs are visible
#    characters that survive strip_ansi, so the monitor idle timer and the
#    review-loop shadow readiness never settle on an idle Codex pane. These two
#    keys switch off ONLY the starfield. `tui.effects.starfield` is the 0.160
#    key; `tui.whimsy` is the 0.154 key and a 0.160 alias of it (both measured
#    to stop the starfield on 0.160.1 via `-c`). 0.154.0 silently ignores
#    `tui.effects.*` (measured: the starfield kept drawing), so `whimsy` is what
#    covers older builds and `effects.starfield` survives the alias's removal.
#  * tui.animations=true (t1944). `animations` is the MASTER switch over every
#    TUI effect, not a narrower starfield switch: with it off, codex-cli 0.160
#    schedules no frame for the `Working (Ns • esc to interrupt)` row, so the
#    elapsed counter repaints only when something unrelated redraws (measured:
#    a 19.9 s capture gap mid-turn) and a working pane reads as IDLE. On, the
#    counter ticks every second. The explicit `true` outranks the
#    `[tui] animations = false` that t1797 seeded into projects. An OS
#    reduced-motion preference still suppresses it (Codex's system_motion).
#  * tui.alternate_screen=never (t1900, t1902). codex-cli 0.160.0 runs its TUI
#    on the alternate screen by default, where tmux keeps no scrollback, so pane
#    captures, shadow review and copy mode saw only the visible rows. `never`
#    restores inline mode (measured on 0.160.0: alternate_on 1->0 and
#    history_size grows; the value vocabulary is auto|always|never, and a bad
#    value is a hard error). The `-c` form rather than 0.160's `--no-alt-screen`
#    flag, because an unknown flag is a hard clap error on older builds, while
#    0.153.4 / 0.156.1 were measured to launch normally with this override.
#    `codex resume` carries it too, so a restored pane stays inline.
#
# Nothing enforces that this is defined: under `set -u` an undeclared array
# still expands to nothing. The launcher tests (test_codeagent.sh 11e/11f,
# test_codeagent_resume_session.sh, test_skillrun_codex.sh) pin the argv.
# shellcheck disable=SC2034  # Read by callers after sourcing this lib.
CODEX_TUI_OVERRIDES=(-c tui.animations=true -c tui.whimsy=false -c tui.effects.starfield=false -c tui.alternate_screen=never)

# --- Parsed agent string (set by parse_agent_string; read by callers in
# aitask_codeagent.sh and aitask_skillrun.sh after sourcing) ---

# shellcheck disable=SC2034
PARSED_AGENT=""
# shellcheck disable=SC2034
PARSED_MODEL=""

# --- Utility functions ---

require_jq() {
    if ! command -v jq &>/dev/null; then
        die "jq is required. Install via your package manager."
    fi
}

# Validate and parse an agent string like "claudecode/opus4_6"
# Sets PARSED_AGENT and PARSED_MODEL
parse_agent_string() {
    local agent_string="$1"
    if [[ ! "$agent_string" =~ ^([a-z]+)/([a-z0-9_]+)$ ]]; then
        die "Invalid agent string format: '$agent_string'. Expected: <agent>/<model> (e.g., claudecode/opus4_6)"
    fi
    # shellcheck disable=SC2034  # Read by callers after sourcing this lib.
    PARSED_AGENT="${BASH_REMATCH[1]}"
    # shellcheck disable=SC2034  # Read by callers after sourcing this lib.
    PARSED_MODEL="${BASH_REMATCH[2]}"

    # Validate agent is supported
    local valid=false
    for a in "${SUPPORTED_AGENTS[@]}"; do
        [[ "$a" == "$PARSED_AGENT" ]] && valid=true
    done
    if ! $valid; then
        die "Unknown agent: '$PARSED_AGENT'. Supported: ${SUPPORTED_AGENTS[*]}"
    fi
}

# Map agent name to CLI binary name
get_cli_binary() {
    local agent="$1"
    case "$agent" in
        claudecode) echo "claude" ;;
        codex)    echo "codex" ;;
        opencode) echo "opencode" ;;
        *) die "Unknown agent: '$agent'" ;;
    esac
}

# Map agent name to the CLI flag used for model selection
get_model_flag() {
    local agent="$1"
    case "$agent" in
        claudecode) echo "--model" ;;
        codex)    echo "-m" ;;
        opencode) echo "--model" ;;
        *) die "Unknown agent: '$agent'" ;;
    esac
}

# Look up the CLI model ID from the model config JSON
# Usage: get_cli_model_id <agent> <model_name>
get_cli_model_id() {
    local agent="$1"
    local model_name="$2"
    local models_file="$METADATA_DIR/models_${agent}.json"

    if [[ ! -f "$models_file" ]]; then
        die "Model config not found: $models_file"
    fi

    local cli_id
    cli_id=$(jq -r --arg name "$model_name" \
        '.models[] | select(.name == $name) | .cli_id' "$models_file")

    if [[ -z "$cli_id" || "$cli_id" == "null" ]]; then
        die "Unknown model '$model_name' for agent '$agent'. Run 'ait codeagent list-models $agent' to see available models."
    fi

    # Check model status (defaults to "active" for files without status field)
    local model_status
    model_status=$(jq -r --arg name "$model_name" \
        '.models[] | select(.name == $name) | .status // "active"' "$models_file")

    if [[ "$model_status" == "unavailable" ]]; then
        die "Model '$model_name' is unavailable (not currently marked as available by connected providers). Run 'ait opencode-models' to refresh."
    fi

    echo "$cli_id"
}
