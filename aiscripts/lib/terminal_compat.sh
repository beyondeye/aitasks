#!/usr/bin/env bash
# terminal_compat.sh - Terminal capability detection and shared helpers
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TERMINAL_COMPAT_LOADED:-}" ]] && return 0
_AIT_TERMINAL_COMPAT_LOADED=1

# --- Color definitions ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Common logging helpers ---
die()     { echo -e "${RED}Error: $1${NC}" >&2; exit 1; }
info()    { echo -e "${BLUE}$1${NC}"; }
success() { echo -e "${GREEN}$1${NC}"; }
warn()    { echo -e "${YELLOW}Warning: $1${NC}" >&2; }

# --- Terminal capability check ---
# Returns 0 if running in a capable modern terminal, 1 otherwise.
# Caches result in AIT_TERMINAL_CAPABLE (1=capable, 0=not).
ait_check_terminal_capable() {
    # Use cached result if available
    if [[ -n "${AIT_TERMINAL_CAPABLE:-}" ]]; then
        [[ "$AIT_TERMINAL_CAPABLE" == "1" ]] && return 0 || return 1
    fi

    AIT_TERMINAL_CAPABLE=0

    # Check 1: COLORTERM (most universal modern-terminal indicator)
    if [[ "${COLORTERM:-}" == "truecolor" || "${COLORTERM:-}" == "24bit" ]]; then
        AIT_TERMINAL_CAPABLE=1
        return 0
    fi

    # Check 2: Windows Terminal session ID
    if [[ -n "${WT_SESSION:-}" ]]; then
        AIT_TERMINAL_CAPABLE=1
        return 0
    fi

    # Check 3: Known modern terminal emulators via TERM_PROGRAM
    case "${TERM_PROGRAM:-}" in
        WezTerm|Alacritty|iTerm.app|vscode|Hyper|tmux|Tabby)
            AIT_TERMINAL_CAPABLE=1
            return 0
            ;;
    esac

    # Check 4: TERM value hints at an advanced terminal
    case "${TERM:-}" in
        xterm-256color|xterm-kitty|alacritty|tmux-256color|screen-256color)
            AIT_TERMINAL_CAPABLE=1
            return 0
            ;;
    esac

    # Check 5: Running inside tmux or screen (they handle rendering)
    if [[ -n "${TMUX:-}" || -n "${STY:-}" ]]; then
        AIT_TERMINAL_CAPABLE=1
        return 0
    fi

    # None of the checks passed
    return 1
}

# --- WSL detection ---
ait_is_wsl() {
    [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null
}

# --- Print terminal warning with fix suggestions ---
# Call from interactive scripts after batch-mode has been ruled out.
# Always returns 0 (warns but never blocks).
ait_warn_if_incapable_terminal() {
    # Allow suppression via env var
    [[ "${AIT_SKIP_TERMINAL_CHECK:-}" == "1" ]] && return 0

    if ait_check_terminal_capable; then
        return 0
    fi

    echo "" >&2
    warn "Your terminal may not fully support TUI features (fzf, colors, interactive board)."
    echo "" >&2

    if ait_is_wsl; then
        echo -e "  ${YELLOW}You appear to be running WSL in a legacy console (conhost.exe).${NC}" >&2
        echo -e "  ${BLUE}For the best experience, use Windows Terminal:${NC}" >&2
        echo -e "    1. Install from Microsoft Store: ${BLUE}https://aka.ms/terminal${NC}" >&2
        echo -e "    2. Set it as default: Settings > Privacy & Security > For developers > Terminal" >&2
        echo -e "    3. Or launch WSL from Windows Terminal directly" >&2
    else
        echo -e "  ${BLUE}For the best experience, use a modern terminal emulator that supports${NC}" >&2
        echo -e "  ${BLUE}true color (e.g., Windows Terminal, Alacritty, WezTerm, iTerm2).${NC}" >&2
    fi

    echo "" >&2
    echo -e "  ${YELLOW}To suppress this warning: export AIT_SKIP_TERMINAL_CHECK=1${NC}" >&2
    echo "" >&2
    return 0
}
